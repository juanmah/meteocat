import os
import tempfile
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from shutil import which

from rich.progress import Progress

from meteocat.config import settings
from meteocat.deps import check_dependencies
from meteocat.download import _download_background_tile
from meteocat.image import (
    _BACKGROUND_TILE_RANGE_X,
    _BACKGROUND_TILE_RANGE_Y,
    _CROP_HEIGHT,
    _CROP_LEFT,
    _CROP_TOP,
    _CROP_WIDTH,
    _apply_background_overlays,
    _assemble_tiles,
    _composite_radar,
    _make_dark_variant,
)
from meteocat.logger import logger
from meteocat.progress import PROGRESS_COLUMNS, progress_console, progress_disable
from meteocat.radar import fetch_radar

_CRON_SCHEDULE = '*/6 * * * *'
_BACKGROUND_RAW = Path('background/background_raw.png')
BACKGROUND_4K = Path('background/background_4K.png')
BACKGROUND_4K_DARK = Path('background/background_4K_dark.png')
_WALLPAPER = Path('wallpaper/wallpaper.png')
_WALLPAPER_DARK = Path('wallpaper/wallpaper_dark.png')

_BACKGROUND_TILE_OFFSET_X = 510
_BACKGROUND_TILE_OFFSET_Y = 638
_BACKGROUND_TILE_MAX_Y = 647

_BACKGROUND_COLUMNS = 18
_MAX_WORKERS = 10

OPACITY_RADAR = 0.8
OPACITY_RADAR_DARK = 0.3


_XDG_TOKEN_MAP: dict[str, str] = {
    'GNOME': 'gnome',
    'Cinnamon': 'cinnamon',
    'MATE': 'mate',
    'KDE': 'kde',
    'Plasma': 'kde',
    'XFCE': 'xfce',
    'LXQt': 'lxqt',
}

_XDG_SESSION_TOKEN_MAP: dict[str, str] = {
    'gnome': 'gnome',
    'cinnamon': 'cinnamon',
    'mate': 'mate',
    'kde': 'kde',
    'xfce': 'xfce',
    'lxqt': 'lxqt',
    'sway': 'sway',
    'hyprland': 'hyprland',
    'i3': 'i3',
}

_DESKTOP_SESSION_TOKEN_MAP: dict[str, str] = {
    'gnome': 'gnome',
    'cinnamon': 'cinnamon',
    'mate': 'mate',
    'kde': 'kde',
    'xfce': 'xfce',
    'lxqt': 'lxqt',
}

_FALLBACK_DETECTORS: list[tuple[str, str]] = [
    ('plasmashell', 'kde'),
    ('xfce4-session', 'xfce'),
    ('swaymsg', 'sway'),
    ('hyprctl', 'hyprland'),
    ('i3', 'i3'),
    ('i3-gaps', 'i3'),
]


@dataclass(frozen=True)
class DeResolution:
    de: str
    source: str


def _match_env_var(env_name: str, token_map: dict[str, str]) -> str | None:
    value = os.environ.get(env_name, '')
    if not value:
        return None
    for token, de in token_map.items():
        if token in value:
            return de
    return None


def _detect_de() -> DeResolution:
    for env_name, token_map in (
        ('XDG_CURRENT_DESKTOP', _XDG_TOKEN_MAP),
        ('XDG_SESSION_DESKTOP', _XDG_SESSION_TOKEN_MAP),
        ('DESKTOP_SESSION', _DESKTOP_SESSION_TOKEN_MAP),
    ):
        de = _match_env_var(env_name, token_map)
        if de is not None:
            return DeResolution(de, f'auto-detected via {env_name}={os.environ[env_name]}')
    for prog, de in _FALLBACK_DETECTORS:
        if which(prog) is not None:
            return DeResolution(de, f'auto-detected via {prog} process')
    return DeResolution('none', 'auto-detected (no desktop environment detected)')


def _set_gnome(path: Path, *, dark: bool = False) -> None:
    import gi

    gi.require_version('Gio', '2.0')
    from gi.repository import Gio

    key = 'picture-uri-dark' if dark else 'picture-uri'
    gsettings = Gio.Settings.new('org.gnome.desktop.background')
    gsettings.set_string(key, f'file://{path}')


def _set_cinnamon(path: Path, *, dark: bool = False) -> None:
    import gi

    gi.require_version('Gio', '2.0')
    from gi.repository import Gio

    key = 'picture-uri-dark' if dark else 'picture-uri'
    gsettings = Gio.Settings.new('org.cinnamon.desktop.background')
    gsettings.set_string(key, f'file://{path}')


def _set_mate(path: Path, *, _dark: bool = False) -> None:
    import gi

    gi.require_version('Gio', '2.0')
    from gi.repository import Gio

    gsettings = Gio.Settings.new('org.mate.background')
    gsettings.set_string('picture-filename', f'file://{path}')


def _set_kde(path: Path, *, _dark: bool = False) -> None:
    import subprocess  # ruff: ignore[suspicious-subprocess-import] # nosec B404

    qdbus = which('qdbus')
    script = (
        'var allDesktops = desktops();\n'
        'for (i=0; i<allDesktops.length; i++) {\n'
        '  d = allDesktops[i];\n'
        '  d.wallpaperPlugin = "org.kde.image";\n'
        '  d.currentConfigGroup = Array("Wallpaper", "org.kde.image", "General");\n'
        '  d.writeConfig("image", "file://' + str(path) + '");\n'
        '}\n'
    )
    subprocess.run(  # ruff: ignore[subprocess-without-shell-equals-true] # nosec B603
        [qdbus, 'org.kde.plasmashell', '/PlasmaShell', 'evaluateScript', script],
        check=True,
    )


def _set_xfce(path: Path, *, _dark: bool = False) -> None:
    import subprocess  # ruff: ignore[suspicious-subprocess-import] # nosec B404

    backdrop = '/backdrop/screen0/monitor0/image-path'
    xfconf = which('xfconf-query')
    subprocess.run(  # ruff: ignore[subprocess-without-shell-equals-true] # nosec B603
        [xfconf, '-c', 'xfce4-desktop', '-p', backdrop, '-s', str(path)],
        check=True,
    )


def _set_lxqt(path: Path, *, _dark: bool = False) -> None:
    import subprocess  # ruff: ignore[suspicious-subprocess-import] # nosec B404

    pcmanfm = which('pcmanfm')
    subprocess.run(  # ruff: ignore[subprocess-without-shell-equals-true] # nosec B603
        [pcmanfm, '--set-wallpaper', str(path)],
        check=True,
    )


def _set_sway(path: Path, *, _dark: bool = False) -> None:
    import subprocess  # ruff: ignore[suspicious-subprocess-import] # nosec B404

    swaymsg = which('swaymsg')
    subprocess.run(  # ruff: ignore[subprocess-without-shell-equals-true] # nosec B603
        [swaymsg, 'output', '*', 'bg', str(path), 'fill'],
        check=True,
    )


def _set_hyprland(path: Path, *, _dark: bool = False) -> None:
    import subprocess  # ruff: ignore[suspicious-subprocess-import] # nosec B404

    hyprctl = which('hyprctl')
    subprocess.run(  # ruff: ignore[subprocess-without-shell-equals-true] # nosec B603
        [hyprctl, 'hyprpaper', 'wallpaper', ','.join(['*', str(path)])],
        check=True,
    )


def _set_i3(path: Path, *, _dark: bool = False) -> None:
    import subprocess  # ruff: ignore[suspicious-subprocess-import] # nosec B404

    feh = which('feh')
    subprocess.run(  # ruff: ignore[subprocess-without-shell-equals-true] # nosec B603
        [feh, '--bg-scale', str(path)],
        check=True,
    )


_SETTERS: dict[str, callable] = {
    'gnome': _set_gnome,
    'cinnamon': _set_cinnamon,
    'mate': _set_mate,
    'kde': _set_kde,
    'xfce': _set_xfce,
    'lxqt': _set_lxqt,
    'sway': _set_sway,
    'hyprland': _set_hyprland,
    'i3': _set_i3,
}


def _resolve_de_detailed() -> DeResolution:
    de = settings.desktop_environment
    if de in _SETTERS or de == 'none':
        return DeResolution(de, 'from configuration')
    return _detect_de()


def _resolve_de() -> str:
    return _resolve_de_detailed().de


def _set_wallpaper(path: Path, *, dark: bool = False) -> None:
    de = _resolve_de()
    if de == 'none':
        return
    setter = _SETTERS.get(de)
    if setter is None:
        logger.warning(f'No wallpaper setter for DE: {de}')
        return
    setter(path, dark=dark)


def generate_background(*, check_deps: bool = True) -> None:
    if check_deps:
        check_dependencies()

    with tempfile.TemporaryDirectory() as temp_dir:
        tasks = [(x, y, temp_dir) for x in _BACKGROUND_TILE_RANGE_X for y in _BACKGROUND_TILE_RANGE_Y]
        with (
            ThreadPoolExecutor(max_workers=_MAX_WORKERS) as executor,
            Progress(
                *PROGRESS_COLUMNS,
                console=progress_console,
                disable=progress_disable,
            ) as progress,
        ):
            task = progress.add_task('Downloading background tiles', total=len(tasks))
            for _ in executor.map(_download_background_tile, tasks):
                progress.update(task, advance=1)
        tiles = sorted(Path(temp_dir).glob('background-*.png'))
        expected = len(_BACKGROUND_TILE_RANGE_X) * len(_BACKGROUND_TILE_RANGE_Y)
        if len(tiles) != expected:
            logger.error(f'Expected {expected} background tiles, got {len(tiles)}')
            raise SystemExit(1)
        canvas = _assemble_tiles(tiles, columns=_BACKGROUND_COLUMNS)
        _BACKGROUND_RAW.parent.mkdir(parents=True, exist_ok=True)
        canvas.save(_BACKGROUND_RAW)
        crop_left = _CROP_LEFT
        crop_top = _CROP_TOP
        crop_width = _CROP_WIDTH
        crop_height = _CROP_HEIGHT
        img = canvas.crop((crop_left, crop_top, crop_left + crop_width, crop_top + crop_height))
        _apply_background_overlays(img)
        img.save(BACKGROUND_4K)
        img_dark = _make_dark_variant(img)
        img_dark.save(BACKGROUND_4K_DARK)


def generate_wallpaper(*, check_deps: bool = True) -> None:
    if check_deps:
        check_dependencies()
    if not BACKGROUND_4K.is_file():
        logger.info("> Background doesn't exist.")
        logger.info('> Generating a background map of Catalonia from meteo.cat sources.')
        generate_background(check_deps=check_deps)

    radar = fetch_radar()

    _WALLPAPER.parent.mkdir(parents=True, exist_ok=True)
    _composite_radar(BACKGROUND_4K, radar, _WALLPAPER, OPACITY_RADAR)
    _composite_radar(BACKGROUND_4K_DARK, radar, _WALLPAPER_DARK, OPACITY_RADAR_DARK)

    _set_wallpaper(_WALLPAPER.resolve())
    _set_wallpaper(_WALLPAPER_DARK.resolve(), dark=True)
    logger.info('Updated meteo.cat radar background.')
