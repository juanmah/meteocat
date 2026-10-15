import sys
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
}

_DE_GSETTINGS_DEPS = {'gnome', 'cinnamon', 'mate'}


def _is_windows() -> bool:
    return sys.platform == 'win32'


def _detect_distro() -> str:
    if _is_windows():
        return 'windows'
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


def _check_binary(
    binary: str,
    *,
    fatal: bool = False,
    verbose: bool = False,
    reason: str | None = None,
) -> bool:
    suffix = f' ({reason})' if reason else ''
    if which(binary) is not None:
        if verbose:
            logger.info(f'[green]{binary}[/green] found{suffix}.')
        return True
    pkg = _get_package_name(binary)
    msg = f'[bold]{binary}[/bold] not found{suffix}. Install [bold]{pkg}[/bold].'
    logger.error(msg)
    if fatal:
        logger.error('[red]Exiting[/red].')
        raise SystemExit
    return False


def _check_pygobject(*, verbose: bool = False) -> bool:
    try:
        import gi

        gi.require_version('Gio', '2.0')
        from gi.repository import Gio  # ruff: ignore[unused-import]
    except ImportError:
        msg = (
            '[bold]pygobject[/bold] not found. '
            'Install [bold]pygobject[/bold] (pip install pygobject) or system package.'
        )
        logger.error(msg)
        return False
    else:
        if verbose:
            logger.info('[green]pygobject (gi.repository.Gio)[/green] available.')
        return True


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
    'windows': '',  # Uses ctypes (stdlib), no external binary needed
}


def _check_de_dependencies(de: str, *, verbose: bool = False) -> None:
    if _is_windows():
        if verbose:
            logger.info('[green]ctypes[/green] available (stdlib).')
    elif de and de in _DE_GSETTINGS_DEPS:
        _check_binary('gsettings', fatal=True, verbose=verbose, reason=f'required for DE: {de}')
        _check_pygobject(verbose=verbose)
    else:
        de_tool = _DE_TOOL_MAP.get(de)
        if de_tool:
            found = _check_binary(de_tool, verbose=verbose, reason=f'required for DE: {de}')
            if not found and verbose:
                logger.warning(f'{de_tool} not found for DE "{de}". Some features may not work.')


def _check_scheduler_dependencies(scheduler: str, *, verbose: bool = False) -> None:
    if scheduler == 'cron':
        _check_binary('crontab', fatal=True, verbose=verbose, reason=f'required for scheduler: {scheduler}')
    elif scheduler == 'systemd':
        _check_binary('systemctl', fatal=True, verbose=verbose, reason=f'required for scheduler: {scheduler}')
    elif scheduler == 'windows':
        if _is_windows():
            _check_binary('schtasks.exe', fatal=True, verbose=verbose, reason=f'required for scheduler: {scheduler}')
        else:
            logger.warning('Windows scheduler selected but not on Windows platform.')


def check_dependencies(*, verbose: bool = False) -> None:
    from meteocat.scheduler import _resolve_scheduler_detailed
    from meteocat.wallpaper import _resolve_de_detailed

    de_resolution = _resolve_de_detailed()
    scheduler_resolution = _resolve_scheduler_detailed()

    if verbose:
        logger.info(f'Desktop environment: [bold]{de_resolution.de}[/bold] ({de_resolution.source})')
        logger.info(f'Scheduler: [bold]{scheduler_resolution.scheduler}[/bold] ({scheduler_resolution.source})')

    _check_de_dependencies(de_resolution.de, verbose=verbose)
    _check_scheduler_dependencies(scheduler_resolution.scheduler, verbose=verbose)

    if verbose:
        logger.info('All dependencies checked.')
