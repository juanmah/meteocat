import io
import re
import sys
import tempfile
from collections.abc import Iterator
from datetime import datetime, timedelta
from pathlib import Path

import ffmpeg
from tqdm import tqdm

from meteocat.config import _RADAR_DIR
from meteocat.image import _composite_radar
from meteocat.logger import logger
from meteocat.wallpaper import (
    _BACKGROUND_4K,
    _BACKGROUND_4K_DARK,
    _OPACITY_RADAR,
    _OPACITY_RADAR_DARK,
)

_RADAR_STEP_MINUTES = 6
_tqdm_disable = not sys.stderr.isatty()
_FRAME_RE = re.compile(rb'frame=\s*(\d+)')
_FFMPEG_CMD = 'ffmpeg'
_STATS_PERIOD = '0.1'


def _iter_radar_timestamps(from_dt: datetime, to_dt: datetime) -> list[datetime]:
    timestamps: list[datetime] = []
    current = from_dt
    while current < to_dt:
        timestamps.append(current)
        current += timedelta(minutes=_RADAR_STEP_MINUTES)
    return timestamps


def _radar_frame_path(timestamp: datetime) -> Path:
    ts = timestamp.strftime('%Y-%m-%d_%H-%M')
    return _RADAR_DIR / f'radar_{ts}.png'


_VARIANT_BACKGROUNDS: dict[str, tuple[Path, float]] = {
    'light': (_BACKGROUND_4K, _OPACITY_RADAR),
    'dark': (_BACKGROUND_4K_DARK, _OPACITY_RADAR_DARK),
}


def _format_missing_range(start: datetime, end: datetime) -> str:
    if start == end:
        return start.strftime('%Y-%m-%d %H:%M')
    if start.date() == end.date():
        return f'{start.strftime("%Y-%m-%d %H:%M")}-{end.strftime("%H:%M")}'
    return f'{start.strftime("%Y-%m-%d %H:%M")}-{end.strftime("%Y-%m-%d %H:%M")}'


def _format_missing_ranges(missing: list[datetime]) -> str:
    ranges: list[str] = []
    start = prev = missing[0]
    for ts in missing[1:]:
        if ts - prev == timedelta(minutes=_RADAR_STEP_MINUTES):
            prev = ts
            continue
        ranges.append(_format_missing_range(start, prev))
        start = prev = ts
    ranges.append(_format_missing_range(start, prev))
    return ', '.join(ranges)


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
        missing: list[datetime] = []
        for ts in timestamps:
            dst = tmp / f'frame_{variant_index:04d}_{variant}.png'
            radar_src = _radar_frame_path(ts)
            if radar_src.is_file():
                background, opacity = _VARIANT_BACKGROUNDS[variant]
                if not background.is_file():
                    logger.warning(
                        'Missing background %s, skipping %s frame for %s',
                        background,
                        variant,
                        ts.strftime('%Y-%m-%d %H:%M'),
                    )
                    missing.append(ts)
                    continue
                _composite_radar(background, radar_src, dst, opacity)
                variant_index += 1
                continue
            missing.append(ts)
        if missing:
            logger.warning(
                'Missing %d %s frames: %s',
                len(missing),
                variant,
                _format_missing_ranges(missing),
            )

    if not any(
        frame
        for variant in ('light', 'dark')
        if (variant == 'light' and light) or (variant == 'dark' and dark)
        for frame in tmp.glob(f'frame_*_{variant}.png')
    ):
        logger.error(
            'No frames found in range %s → %s',
            from_dt.strftime('%Y-%m-%d %H:%M'),
            to_dt.strftime('%Y-%m-%d %H:%M'),
        )
        raise SystemExit(1)

    return tmp, timestamps


def _iter_progress_lines(stderr: io.BufferedReader) -> Iterator[bytes]:
    buffer = b''
    while True:
        chunk = stderr.read1(8192)
        if not chunk:
            break
        buffer += chunk.replace(b'\r', b'\n')
        *lines, buffer = buffer.split(b'\n')
        yield from lines
    if buffer:
        yield buffer


def _run_ffmpeg(
    stream: ffmpeg.nodes.OutputStream,
    *,
    total_frames: int,
    desc: str,
) -> None:
    process = stream.run_async(pipe_stderr=True)
    stderr_lines: list[bytes] = []
    last_frame = 0
    with tqdm(
        total=total_frames,
        unit='frame',
        desc=desc,
        disable=_tqdm_disable,
    ) as bar:
        for line in _iter_progress_lines(process.stderr):
            stderr_lines.append(line)
            match = _FRAME_RE.search(line)
            if match:
                frame = int(match.group(1))
                if frame > last_frame:
                    bar.update(frame - last_frame)
                    last_frame = frame
        bar.update(total_frames - bar.n)
    process.wait()
    if process.returncode != 0:
        raise ffmpeg.Error(_FFMPEG_CMD, b'', b'\n'.join(stderr_lines))


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
        total_frames = len(list(frames_dir.glob(f'frame_*_{variant}.png')))
        logger.info('Encoding %s video: %s', variant, variant_output)
        _run_ffmpeg(
            ffmpeg.input(pattern, framerate=fps)
            .output(str(variant_output), vcodec=codec, crf=crf, preset=preset)
            .overwrite_output()
            .global_args('-hide_banner', '-stats_period', _STATS_PERIOD),
            total_frames=total_frames,
            desc=f'Encoding {variant}',
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
