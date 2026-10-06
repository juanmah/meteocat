from shutil import which

from meteocat.logging import logger


def check_dependencies(*, verbose: bool = False) -> None:
    """Check for required system packages dependencies and give information if any are missing."""
    for name, pkg in (('uv', 'uv'), ('gsettings', 'glib2')):
        if which(name) is None:
            logger.error(f'[red]ERROR[/red]: [bold]{pkg}[/bold] not found. Install [bold]{pkg}[/bold].')
            logger.error('[red]Exiting[/red].')
            raise SystemExit
        if verbose:
            logger.info(f'[green]{pkg}[/green] found.')
    if verbose:
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
