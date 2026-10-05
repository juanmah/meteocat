import logging
from shutil import which

from meteocat.logging import setup

logger = logging.getLogger('meteocat')
setup()


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
