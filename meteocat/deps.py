from pathlib import Path
from shutil import which

from meteocat.logger import logger

_BINARY_TO_PACKAGE: dict[str, dict[str, str]] = {
    'gsettings': {'arch': 'glib2', 'debian': 'libglib2.0-bin', 'ubuntu': 'libglib2.0-bin'},
    'qdbus': {'arch': 'qt5-base', 'debian': 'qt5-default', 'ubuntu': 'qt5-default'},
    'xfconf-query': {'arch': 'xfconf', 'debian': 'xfconf', 'ubuntu': 'xfconf'},
    'pcmanfm': {'arch': 'pcmanfm', 'debian': 'pcmanfm', 'ubuntu': 'pcmanfm'},
    'swaymsg': {'arch': 'sway', 'debian': 'sway', 'ubuntu': 'sway'},
    'hyprctl': {'arch': 'hyprland', 'debian': 'hyprland', 'ubuntu': 'hyprland'},
    'feh': {'arch': 'feh', 'debian': 'feh', 'ubuntu': 'feh'},
    'crontab': {'arch': 'cronie', 'debian': 'cron', 'ubuntu': 'cron'},
    'systemctl': {'arch': 'systemd', 'debian': 'systemd', 'ubuntu': 'systemd'},
    'ffmpeg': {'arch': 'ffmpeg', 'debian': 'ffmpeg', 'ubuntu': 'ffmpeg'},
}

_DE_GSETTINGS_DEPS = {'gnome', 'cinnamon', 'mate'}


def _detect_distro() -> str:
    try:
        id_like = Path('/etc/os-release').read_text()
        for line in id_like.splitlines():
            if line.startswith('ID='):
                return line.split('=', 1)[1].strip().strip('"')
    except OSError:
        return 'arch'


def _get_package_name(binary: str) -> str:
    distro = _detect_distro()
    mapping = _BINARY_TO_PACKAGE.get(binary, {})
    return mapping.get(distro, mapping.get('arch', binary))


def _check_binary(binary: str, *, fatal: bool = False, verbose: bool = False) -> bool:
    if which(binary) is not None:
        if verbose:
            logger.info(f'[green]{binary}[/green] found.')
        return True
    pkg = _get_package_name(binary)
    msg = f'[bold]{binary}[/bold] not found. Install [bold]{pkg}[/bold].'
    logger.error(msg)
    if fatal:
        logger.error('[red]Exiting[/red].')
        raise SystemExit
    return False


_DE_TOOL_MAP: dict[str, str] = {
    'gnome': 'gsettings',
    'cinnamon': 'gsettings',
    'mate': 'gsettings',
    'kde': 'qdbus',
    'xfce': 'xfconf-query',
    'lxqt': 'pcmanfm',
    'sway': 'swaymsg',
    'hyprland': 'hyprctl',
    'i3': 'feh',
}


def check_dependencies(*, verbose: bool = False) -> None:
    """Check for required system binary dependencies and report missing ones."""
    from meteocat.wallpaper import _resolve_de

    de = _resolve_de()
    de_tool = _DE_TOOL_MAP.get(de)

    if de and de in _DE_GSETTINGS_DEPS:
        _check_binary('gsettings', fatal=True, verbose=verbose)
    elif de_tool:
        found = _check_binary(de_tool, verbose=verbose)
        if not found and verbose:
            logger.warning(f'{de_tool} not found for DE "{de}". Some features may not work.')

    from meteocat.scheduler import _resolve_scheduler

    scheduler = _resolve_scheduler()
    if scheduler == 'cron':
        _check_binary('crontab', fatal=True, verbose=verbose)
    elif scheduler == 'systemd':
        _check_binary('systemctl', fatal=True, verbose=verbose)

    if verbose:
        logger.info('All dependencies checked.')
