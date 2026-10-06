import os
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path
from shutil import which

from tqdm import tqdm

from meteocat.config import settings
from meteocat.deps import check_dependencies
from meteocat.download import _download_background_tile, _download_radar_tile
from meteocat.image import _apply_background_overlays, _assemble_tiles, _composite_radar, _make_dark_variant
from meteocat.logging import logger

_tqdm_disable = not sys.stderr.isatty()


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


def _match_env_var(env_name: str, token_map: dict[str, str]) -> str | None:
    value = os.environ.get(env_name, '')
    if not value:
        return None
    for token, de in token_map.items():
        if token in value:
            return de
    return None


def _detect_de() -> str:
    result = _match_env_var('XDG_CURRENT_DESKTOP', _XDG_TOKEN_MAP)
    if result:
        return result
    result = _match_env_var('XDG_SESSION_DESKTOP', _XDG_SESSION_TOKEN_MAP)
    if result:
        return result
    result = _match_env_var('DESKTOP_SESSION', _DESKTOP_SESSION_TOKEN_MAP)
    if result:
        return result
    for prog, de in _FALLBACK_DETECTORS:
        if which(prog) is not None:
            return de
    return 'none'


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


def _resolve_de() -> str:
    de = settings.desktop_environment
    if de in _SETTERS or de == 'none':
        return de
    return _detect_de()


def _set_wallpaper(path: Path, *, dark: bool = False) -> None:
    de = _resolve_de()
    if de == 'none':
        return
    setter = _SETTERS.get(de)
    if setter is None:
        logger.warning(f'No wallpaper setter for DE: {de}')
        return
    setter(path, dark=dark)


def generate_background() -> None:
    check_dependencies()

    with tempfile.TemporaryDirectory() as temp_dir:
        tasks = [(x, y, temp_dir) for x in settings.background_tile_range_x for y in settings.background_tile_range_y]
        with ThreadPoolExecutor(max_workers=settings.max_workers) as executor:
            list(tqdm(executor.map(_download_background_tile, tasks), total=len(tasks), disable=_tqdm_disable))
        tiles = sorted(Path(temp_dir).glob('background-*.png'))
        expected = len(settings.background_tile_range_x) * len(settings.background_tile_range_y)
        if len(tiles) != expected:
            logger.error(f'Expected {expected} background tiles, got {len(tiles)}')
            raise SystemExit(1)
        canvas = _assemble_tiles(tiles, columns=settings.background_columns)
        settings.background_raw.parent.mkdir(parents=True, exist_ok=True)
        canvas.save(settings.background_raw)
        crop_left = settings.crop_left
        crop_top = settings.crop_top
        crop_width = settings.crop_width
        crop_height = settings.crop_height
        img = canvas.crop((crop_left, crop_top, crop_left + crop_width, crop_top + crop_height))
        _apply_background_overlays(img)
        img.save(settings.background_4k)
        img_dark = _make_dark_variant(img)
        img_dark.save(settings.background_4k_dark)


def archive_wallpaper(date: str) -> None:
    year, month, day, hour, minute = date.split('/')
    timestamp = f'{year}-{month}-{day}_{hour}-{minute}'
    for suffix, subdir in (('', 'light'), ('_dark', 'dark')):
        target_dir = settings.wallpaper_history / subdir
        target_dir.mkdir(parents=True, exist_ok=True)
        src = settings.wallpaper if suffix == '' else settings.wallpaper_dark
        dst = target_dir / f'wallpaper{suffix}_{timestamp}.png'
        dst.write_bytes(src.read_bytes())
        logger.info(f'Archived {dst}')


def generate_wallpaper() -> None:
    check_dependencies()
    if not settings.background_4k.is_file():
        logger.info("> Background doesn't exist.")
        logger.info('> Generating a background map of Catalonia from meteo.cat sources.')
        generate_background()

    now = datetime.now(UTC) - timedelta(minutes=settings.radar_delay_minutes)
    date = f'{now.year}/{now.month:02}/{now.day:02}/{now.hour:02}/{now.minute // 6 * 6:02}'

    with tempfile.TemporaryDirectory() as temp_dir:
        tasks = [(x, y, temp_dir, date) for x in settings.radar_tile_range_x for y in settings.radar_tile_range_y]
        with ThreadPoolExecutor(max_workers=settings.max_workers) as executor:
            list(tqdm(executor.map(_download_radar_tile, tasks), total=len(tasks), disable=_tqdm_disable))
        tiles = sorted(Path(temp_dir).glob('radar-*.png'))
        expected = len(settings.radar_tile_range_x) * len(settings.radar_tile_range_y)
        if len(tiles) != expected:
            logger.error(f'Expected {expected} radar tiles, got {len(tiles)}')
            raise SystemExit(1)
        canvas = _assemble_tiles(tiles, columns=settings.radar_columns)
        radar = Path(temp_dir) / settings.radar
        canvas.save(radar)
        settings.wallpaper.parent.mkdir(parents=True, exist_ok=True)
        _composite_radar(settings.background_4k, radar, settings.wallpaper, settings.opacity_radar)
        _composite_radar(settings.background_4k_dark, radar, settings.wallpaper_dark, settings.opacity_radar_dark)

    _set_wallpaper(settings.wallpaper.resolve())
    _set_wallpaper(settings.wallpaper_dark.resolve(), dark=True)
    logger.info('Updated meteo.cat radar background.')
    if settings.historic_enabled:
        archive_wallpaper(date)
