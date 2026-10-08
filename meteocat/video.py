import tempfile
from datetime import datetime, timedelta
from pathlib import Path

import ffmpeg

from meteocat.config import _HISTORY_DIR
from meteocat.logger import logger

_RADAR_STEP_MINUTES = 6


def _iter_radar_timestamps(from_dt: datetime, to_dt: datetime) -> list[datetime]:
    timestamps: list[datetime] = []
    current = from_dt
    while current < to_dt:
        timestamps.append(current)
        current += timedelta(minutes=_RADAR_STEP_MINUTES)
    return timestamps


def _frame_path(timestamp: datetime, *, dark: bool) -> Path:
    ts = timestamp.strftime('%Y-%m-%d_%H-%M')
    subdir = 'dark' if dark else 'light'
    suffix = '_dark' if dark else ''
    return _HISTORY_DIR / subdir / f'wallpaper{suffix}_{ts}.png'


def generate_frames(
    from_dt: datetime,
    to_dt: datetime,
    *,
    light: bool = True,
    dark: bool = True,
) -> tuple[Path, list[datetime]]:
    timestamps = _iter_radar_timestamps(from_dt, to_dt)
    if not timestamps:
        logger.error(
            'No radar timestamps in range %s → %s',
            from_dt.strftime('%Y-%m-%d %H:%M'),
            to_dt.strftime('%Y-%m-%d %H:%M'),
        )
        raise SystemExit(1)

    tmp = Path(tempfile.mkdtemp())

    for variant, enabled in (('light', light), ('dark', dark)):
        if not enabled:
            continue
        variant_index = 0
        for ts in timestamps:
            src = _frame_path(ts, dark=(variant == 'dark'))
            if not src.is_file():
                logger.warning(
                    'Missing frame for %s at %s, skipping',
                    variant,
                    ts.strftime('%Y-%m-%d %H:%M'),
                )
                continue
            dst = tmp / f'frame_{variant_index:04d}_{variant}.png'
            dst.symlink_to(src.resolve())
            variant_index += 1

    if not any(
        tmp.glob(f'frame_*_{variant}.png')
        for variant in ('light', 'dark')
        if (variant == 'light' and light) or (variant == 'dark' and dark)
    ):
        logger.error(
            'No frames found in range %s → %s',
            from_dt.strftime('%Y-%m-%d %H:%M'),
            to_dt.strftime('%Y-%m-%d %H:%M'),
        )
        raise SystemExit(1)

    return tmp, timestamps


def encode_video(
    frames_dir: Path,
    timestamps: list[datetime],
    profile_name: str,
    profile: object,
    *,
    light: bool = True,
    dark: bool = True,
) -> Path:
    from meteocat.config import settings

    output_dir = settings.video.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    from_dt = timestamps[0]
    to_dt = timestamps[-1]
    range_str = f'{from_dt.strftime("%Y%m%d_%H%M")}_{to_dt.strftime("%Y%m%d_%H%M")}'

    variants = []
    if light:
        variants.append('light')
    if dark:
        variants.append('dark')

    ext = profile.container
    output = output_dir / f'video_{profile_name}_{range_str}.{ext}'

    if output.is_file():
        logger.info('Video already exists: %s', output)
        return output

    fps = str(profile.fps)
    codec = profile.codec
    crf = str(profile.crf)
    preset = profile.preset

    for variant in variants:
        variant_output = output_dir / f'video_{profile_name}_{range_str}_{variant}.{ext}'
        if variant_output.is_file():
            logger.info('Video already exists: %s', variant_output)
            continue
        pattern = str(frames_dir / f'frame_%04d_{variant}.png')
        logger.info('Encoding %s video: %s', variant, variant_output)
        (
            ffmpeg.input(pattern, framerate=fps)
            .output(str(variant_output), vcodec=codec, crf=crf, preset=preset)
            .overwrite_output()
            .run()
        )

    return output


def create_video(
    from_dt: datetime,
    to_dt: datetime,
    profile_name: str = 'mkv',
    *,
    light: bool = True,
    dark: bool = True,
) -> Path:
    from meteocat.config import settings

    profile = settings.video.profiles.get(profile_name)
    if profile is None:
        logger.error('Unknown video profile: %s', profile_name)
        raise SystemExit(1)

    frames_dir, timestamps = generate_frames(from_dt, to_dt, light=light, dark=dark)
    try:
        output = encode_video(frames_dir, timestamps, profile_name, profile, light=light, dark=dark)
    finally:
        for f in frames_dir.glob('frame_*.png'):
            f.unlink()
        frames_dir.rmdir()

    logger.info('Video created: %s', output)
    return output
