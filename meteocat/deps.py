from shutil import which

from meteocat.logging import logger

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
    """Check for required system packages dependencies and give information if any are missing."""
    for name, pkg in (('uv', 'uv'), ('gsettings', 'glib2')):
        if which(name) is None:
            logger.error(f'[red]ERROR[/red]: [bold]{pkg}[/bold] not found. Install [bold]{pkg}[/bold].')
            logger.error('[red]Exiting[/red].')
            raise SystemExit
        if verbose:
            logger.info(f'[green]{pkg}[/green] found.')
    from meteocat.wallpaper import _resolve_de

    de = _resolve_de()
    de_tool = _DE_TOOL_MAP.get(de)
    if de_tool and which(de_tool) is None:
        logger.error(f'[red]ERROR[/red]: [bold]{de_tool}[/bold] not found for DE "{de}". Install the required package.')
        logger.error('[red]Exiting[/red].')
        raise SystemExit
    if verbose:
        if de_tool:
            logger.info(f'[green]{de_tool}[/green] found for DE "{de}".')
        logger.info('All dependencies found.')


def check_scheduler_dependencies(*, verbose: bool = False) -> None:
    """Check for scheduler-specific dependencies."""
    from meteocat.scheduler import _resolve_scheduler

    scheduler = _resolve_scheduler()
    if scheduler == 'cron':
        if which('crontab') is None:
            logger.error(
                '[red]ERROR[/red]: [bold]cronie/crond[/bold] not found. '
                'Install [bold]cronie[/bold] or [bold]crond[/bold].'
            )
            logger.error('[red]Exiting[/red].')
            raise SystemExit
        if verbose:
            logger.info('[green]crontab[/green] found.')
