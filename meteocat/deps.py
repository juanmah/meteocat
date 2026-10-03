import logging
import sys
from shutil import which

logger = logging.getLogger('meteocat')
logger.setLevel(logging.INFO)
if sys.stderr.isatty():
    from rich.logging import RichHandler

    rich_handler = RichHandler(rich_tracebacks=True, markup=True)
    rich_handler.setFormatter(logging.Formatter('%(message)s', datefmt='[%X]'))
    logger.addHandler(rich_handler)
else:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter('%(message)s'))
    logger.addHandler(handler)


def check_dependencies() -> None:
    """Check for required system packages dependencies and give information if any are missing."""
    for name, pkg in (('uv', 'uv'), ('gsettings', 'glib2')):
        if which(name) is None:
            logger.error(f'[red]ERROR[/red]: [bold]{pkg}[/bold] not found. Install [bold]{pkg}[/bold].')
            logger.error('[red]Exiting[/red].')
            raise SystemExit
        logger.info(f'[green]{pkg}[/green] found.')
    logger.info('All dependencies found.')
