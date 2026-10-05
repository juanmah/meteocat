import logging
import sys
from pathlib import Path

logger = logging.getLogger('meteocat')


def setup(level: int = logging.INFO) -> None:
    logger.setLevel(level)
    if logger.handlers:
        return
    if sys.stderr.isatty():
        from rich.logging import RichHandler

        rich_handler = RichHandler(rich_tracebacks=True, markup=True)
        rich_handler.setFormatter(logging.Formatter('%(message)s', datefmt='[%X]'))
        logger.addHandler(rich_handler)
    else:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter('%(message)s'))
        logger.addHandler(handler)
    if level <= logging.DEBUG:
        logger.debug('Command: %s', ' '.join(sys.argv))
        logger.debug('Working directory: %s', Path.cwd())
