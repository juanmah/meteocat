import contextlib
import io
import subprocess  # ruff: ignore[suspicious-subprocess-import] # nosec B404
import sys
import threading
from collections.abc import Iterator
from datetime import datetime, timedelta
from pathlib import Path

import ffmpeg
from PIL import Image
from rich.console import Console
from rich.progress import (
    BarColumn,
    Progress,
    ProgressColumn,
    TaskID,
    TaskProgressColumn,
    TextColumn,
    TimeRemainingColumn,
)

from meteocat.config import _RADAR_DIR, VideoProfile
from meteocat.image import _composite_radar_image
from meteocat.logger import logger
from meteocat.wallpaper import (
    _BACKGROUND_4K,
    _BACKGROUND_4K_DARK,
    _OPACITY_RADAR,
    _OPACITY_RADAR_DARK,
)

_RADAR_STEP_MINUTES = 6
_progress_console = Console(stderr=True)
_progress_disable = not sys.stderr.isatty()
_FFMPEG_CMD = 'ffmpeg'
_STATS_PERIOD = '0.1'

_PROGRESS_COLUMNS: tuple[ProgressColumn, ...] = (
    TextColumn('[progress.description]{task.description}'),
    BarColumn(),
    TextColumn('{task.completed}/{task.total}'),
    TaskProgressColumn(),
    TimeRemainingColumn(),
)


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


def _split_available_timestamps(
    timestamps: list[datetime],
) -> tuple[list[datetime], list[datetime]]:
    available: list[datetime] = []
    missing: list[datetime] = []
    for ts in timestamps:
        if _radar_frame_path(ts).is_file():
            available.append(ts)
        else:
            missing.append(ts)
    return available, missing


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


class _StreamEncoder:
    def _drain_stderr(self) -> None:
        for line in _iter_progress_lines(self.process.stderr):
            self.stderr_lines.append(line)

    def __init__(
        self,
        output: Path,
        profile: VideoProfile,
        background: Path,
        opacity: float,
    ) -> None:
        self.background = Image.open(background).convert('RGBA')
        self.opacity = opacity
        self.stderr_lines: list[bytes] = []
        self.process: subprocess.Popen[bytes] = (
            ffmpeg.input('pipe:', format='image2pipe', framerate=str(profile.fps))
            .output(
                str(output),
                vcodec=profile.codec,
                crf=str(profile.crf),
                preset=profile.preset,
            )
            .overwrite_output()
            .global_args('-hide_banner', '-stats_period', _STATS_PERIOD)
            .run_async(pipe_stdin=True, pipe_stderr=True)
        )
        self._drain_thread = threading.Thread(target=self._drain_stderr, daemon=True)
        self._drain_thread.start()

    def write_frame(self, radar_src: Path) -> None:
        frame = _composite_radar_image(self.background.copy(), radar_src, self.opacity)
        buffer = io.BytesIO()
        frame.save(buffer, format='PNG')
        self.process.stdin.write(buffer.getvalue())

    def shutdown(self) -> None:
        if self.process.stdin is not None:
            with contextlib.suppress(BrokenPipeError):
                self.process.stdin.close()
        self._drain_thread.join()
        self.process.wait()


def _plan_variants(
    output_dir: Path,
    profile_name: str,
    ext: str,
    range_str: str,
    variants: list[str],
    available: list[datetime],
    missing: list[datetime],
) -> list[tuple[str, Path, Path, float]]:
    planned: list[tuple[str, Path, Path, float]] = []
    for variant in variants:
        variant_output = output_dir / f'video_{profile_name}_{range_str}_{variant}.{ext}'
        if variant_output.is_file():
            logger.info('Video already exists: %s', variant_output)
            continue
        background, opacity = _VARIANT_BACKGROUNDS[variant]
        if not background.is_file():
            logger.warning('Missing background %s, skipping %s video', background, variant)
            continue
        if missing:
            logger.warning(
                'Missing %d %s frames: %s',
                len(missing),
                variant,
                _format_missing_ranges(missing),
            )
        if not available:
            continue
        planned.append((variant, variant_output, background, opacity))
    return planned


def _all_variant_outputs_exist(
    output_dir: Path, profile_name: str, ext: str, range_str: str, variants: list[str]
) -> bool:
    return all((output_dir / f'video_{profile_name}_{range_str}_{variant}.{ext}').is_file() for variant in variants)


def _stream_frames(
    encoder: _StreamEncoder,
    available: list[datetime],
    progress: Progress,
    task: TaskID,
) -> None:
    for ts in available:
        radar_src = _radar_frame_path(ts)
        try:
            encoder.write_frame(radar_src)
        except BrokenPipeError:
            break
        progress.update(task, advance=1)


def _encode_variant(
    variant: str,
    variant_output: Path,
    profile: VideoProfile,
    background: Path,
    opacity: float,
    available: list[datetime],
) -> None:
    logger.info('Encoding %s video: %s', variant, variant_output)
    encoder = _StreamEncoder(variant_output, profile, background, opacity)
    total_frames = len(available)
    with Progress(
        *_PROGRESS_COLUMNS,
        console=_progress_console,
        disable=_progress_disable,
    ) as progress:
        task = progress.add_task(f'Encoding {variant}', total=total_frames)
        try:
            _stream_frames(encoder, available, progress, task)
        finally:
            encoder.shutdown()
            progress.update(task, completed=total_frames)
    if encoder.process.returncode != 0:
        raise ffmpeg.Error(_FFMPEG_CMD, b'', b'\n'.join(encoder.stderr_lines))


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

    output_dir = settings.video.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    timestamps = _iter_radar_timestamps(from_dt, to_dt)
    if not timestamps:
        logger.error(
            'No radar timestamps in range %s → %s',
            from_dt.strftime('%Y-%m-%d %H:%M'),
            to_dt.strftime('%Y-%m-%d %H:%M'),
        )
        raise SystemExit(1)

    available, missing = _split_available_timestamps(timestamps)

    range_str = f'{timestamps[0].strftime("%Y%m%d_%H%M")}_{timestamps[-1].strftime("%Y%m%d_%H%M")}'
    ext = profile.container
    output = output_dir / f'video_{profile_name}_{range_str}.{ext}'
    if output.is_file():
        logger.info('Video already exists: %s', output)
        return output

    variants = [variant for variant, enabled in (('light', light), ('dark', dark)) if enabled]
    planned = _plan_variants(output_dir, profile_name, ext, range_str, variants, available, missing)
    if not planned:
        if variants and _all_variant_outputs_exist(output_dir, profile_name, ext, range_str, variants):
            logger.info('Video already exists: %s', output)
            return output
        logger.error(
            'No frames found in range %s → %s',
            timestamps[0].strftime('%Y-%m-%d %H:%M'),
            timestamps[-1].strftime('%Y-%m-%d %H:%M'),
        )
        raise SystemExit(1)

    for variant, variant_output, background, opacity in planned:
        _encode_variant(variant, variant_output, profile, background, opacity, available)

    logger.info('Video created: %s', output)
    return output
