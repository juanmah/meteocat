import logging
import signal
import time
from datetime import UTC, datetime

from meteocat.config import settings
from meteocat.logger import logger, setup
from meteocat.radar import download_radar

INTERVAL_MINUTES = 6

_shutdown = False


def _handle_signal(signum: int, _frame: object) -> None:
    global _shutdown
    logger.info('Received signal %s, shutting down...', signum)
    _shutdown = True


def _seconds_until_next_interval() -> float:
    now = datetime.now(UTC)
    elapsed = (now.minute * 60) + now.second + now.microsecond / 1e6
    next_tick = ((elapsed // (INTERVAL_MINUTES * 60)) + 1) * (INTERVAL_MINUTES * 60)
    return next_tick - elapsed


def run() -> None:
    level = getattr(logging, settings.log_level.upper(), logging.INFO)
    setup(level=level)
    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)

    logger.info(
        'scheduler=%s log_level=%s historic_enabled=%s',
        settings.scheduler,
        settings.log_level,
        settings.historic_enabled,
    )

    logger.info('Radar archive loop started (interval: %d min)', INTERVAL_MINUTES)

    while not _shutdown:
        try:
            download_radar(check_deps=False, archive_only=True)
        except SystemExit:
            raise
        except Exception:  # ruff: ignore[blind-except]
            logger.exception('download_radar() failed')

        if _shutdown:
            break

        wait = _seconds_until_next_interval()
        logger.info('Next run in %.0f seconds', wait)
        end = time.monotonic() + wait
        while time.monotonic() < end and not _shutdown:
            time.sleep(min(1, end - time.monotonic()))

    logger.info('Radar archive loop stopped.')


if __name__ == '__main__':
    run()
