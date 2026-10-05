import logging
import sys

logger = logging.getLogger('meteocat')


def setup() -> None:
    logger.setLevel(logging.INFO)
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


setup()
