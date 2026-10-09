import logging
import signal
import time
from datetime import UTC, datetime, timedelta

from meteocat.config import settings
from meteocat.logger import logger, setup
from meteocat.video import create_video
from meteocat.wallpaper import generate_wallpaper

INTERVAL_MINUTES = 6

_shutdown = False
_last_video_date: datetime.date | None = None


def _handle_signal(signum: int, _frame: object) -> None:
    global _shutdown
    logger.info('Received signal %s, shutting down...', signum)
    _shutdown = True


def _seconds_until_next_interval() -> float:
    now = datetime.now(UTC)
    elapsed = (now.minute * 60) + now.second + now.microsecond / 1e6
    next_tick = ((elapsed // (INTERVAL_MINUTES * 60)) + 1) * (INTERVAL_MINUTES * 60)
    return next_tick - elapsed


def _should_generate_video(now: datetime) -> bool:
    return now.hour == 0 and now.minute <= 5


def _get_yesterday_range(now: datetime) -> tuple[datetime, datetime]:
    yesterday = now.date() - timedelta(days=1)
    from_dt = datetime(yesterday.year, yesterday.month, yesterday.day, 0, 0, tzinfo=UTC)
    to_dt = from_dt + timedelta(days=1)
    return from_dt, to_dt


def _generate_midnight_videos() -> None:
    now = datetime.now(UTC)
    if not _should_generate_video(now):
        return
    today = now.date()
    global _last_video_date
    if _last_video_date == today:
        return
    profile_name = 'mkv'
    profile = settings.video.profiles.get(profile_name)
    if profile is None:
        logger.warning('Video profile %s not found, skipping midnight video', profile_name)
        _last_video_date = today
        return
    from_dt, to_dt = _get_yesterday_range(now)
    for variant, _enabled in (('dark', True), ('light', True)):
        output_dir = settings.video.output_dir
        ext = profile.container
        ts_str = f'{from_dt.strftime("%Y%m%d_%H%M")}_{to_dt.strftime("%Y%m%d_%H%M")}'
        output = output_dir / f'video_{profile_name}_{ts_str}.{ext}'
        if output.is_file():
            logger.info('Video already exists, skipping: %s', output)
            continue
        logger.info('Generating midnight video: %s (%s)', variant, output)
        try:
            create_video(
                from_dt,
                to_dt,
                profile_name=profile_name,
                light=(variant == 'light'),
                dark=(variant == 'dark'),
            )
        except SystemExit:
            logger.exception('Failed to generate %s video', variant)
    _last_video_date = today


def run() -> None:
    level = getattr(logging, settings.log_level.upper(), logging.INFO)
    setup(level=level)
    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)

    logger.info(
        'scheduler=%s desktop_environment=%s log_level=%s historic_enabled=%s',
        settings.scheduler,
        settings.desktop_environment,
        settings.log_level,
        settings.historic_enabled,
    )

    logger.info('Wallpaper loop started (interval: %d min)', INTERVAL_MINUTES)

    while not _shutdown:
        try:
            generate_wallpaper(check_deps=False)
        except SystemExit:
            raise
        except Exception:  # ruff: ignore[blind-except]
            logger.exception('generate_wallpaper() failed')

        _generate_midnight_videos()

        if _shutdown:
            break

        wait = _seconds_until_next_interval()
        logger.info('Next run in %.0f seconds', wait)
        end = time.monotonic() + wait
        while time.monotonic() < end and not _shutdown:
            time.sleep(min(1, end - time.monotonic()))

    logger.info('Wallpaper loop stopped.')


if __name__ == '__main__':
    run()
