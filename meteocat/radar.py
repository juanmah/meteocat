import tempfile
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING

from rich.progress import Progress

from meteocat.download import _download_radar_tile
from meteocat.image import _RADAR_TILE_RANGE_X, _RADAR_TILE_RANGE_Y, _assemble_tiles
from meteocat.logger import logger
from meteocat.progress import PROGRESS_COLUMNS, progress_console, progress_disable

if TYPE_CHECKING:
    from PIL import Image

_RADAR = Path('wallpaper/radar.png')

_RADAR_OFFSET_X = 63
_RADAR_OFFSET_Y = 80

_RADAR_COLUMNS = 3
_MAX_WORKERS = 10
_RADAR_DELAY_MINUTES = 15


def current_radar_date() -> str:
    now = datetime.now(UTC) - timedelta(minutes=_RADAR_DELAY_MINUTES)
    return f'{now.year}/{now.month:02}/{now.day:02}/{now.hour:02}/{now.minute // 6 * 6:02}'


def _fetch_radar_canvas(date: str) -> Image.Image:
    with tempfile.TemporaryDirectory() as temp_dir:
        tasks = [(x, y, temp_dir, date) for x in _RADAR_TILE_RANGE_X for y in _RADAR_TILE_RANGE_Y]
        with (
            ThreadPoolExecutor(max_workers=_MAX_WORKERS) as executor,
            Progress(
                *PROGRESS_COLUMNS,
                console=progress_console,
                disable=progress_disable,
            ) as progress,
        ):
            task = progress.add_task('Downloading radar tiles', total=len(tasks))
            for _ in executor.map(_download_radar_tile, tasks):
                progress.update(task, advance=1)
        tiles = sorted(Path(temp_dir).glob('radar-*.png'))
        expected = len(_RADAR_TILE_RANGE_X) * len(_RADAR_TILE_RANGE_Y)
        if len(tiles) != expected:
            logger.error(f'Expected {expected} radar tiles, got {len(tiles)}')
            raise SystemExit(1)
        return _assemble_tiles(tiles, columns=_RADAR_COLUMNS)


def fetch_radar(date: str | None = None) -> Path:
    if date is None:
        date = current_radar_date()
    canvas = _fetch_radar_canvas(date)
    _RADAR.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(_RADAR)
    return _RADAR
