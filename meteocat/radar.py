import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING

from tqdm import tqdm

from meteocat.config import _RADAR_DIR, settings
from meteocat.deps import check_dependencies
from meteocat.download import _download_radar_tile
from meteocat.image import _assemble_tiles
from meteocat.logger import logger

if TYPE_CHECKING:
    from PIL import Image

_tqdm_disable = not sys.stderr.isatty()

_RADAR = Path('wallpaper/radar.png')

_RADAR_TILE_RANGE_X = range(63, 66)
_RADAR_TILE_RANGE_Y = range(79, 81)
_RADAR_OFFSET_X = 63
_RADAR_OFFSET_Y = 80

_RADAR_COLUMNS = 3
_MAX_WORKERS = 10
_RADAR_DELAY_MINUTES = 15


def _current_radar_date() -> str:
    now = datetime.now(UTC) - timedelta(minutes=_RADAR_DELAY_MINUTES)
    return f'{now.year}/{now.month:02}/{now.day:02}/{now.hour:02}/{now.minute // 6 * 6:02}'


def _radar_archive_path(date: str) -> Path:
    year, month, day, hour, minute = date.split('/')
    timestamp = f'{year}-{month}-{day}_{hour}-{minute}'
    return _RADAR_DIR / f'radar_{timestamp}.png'


def _fetch_radar_canvas(date: str) -> Image.Image:
    with tempfile.TemporaryDirectory() as temp_dir:
        tasks = [(x, y, temp_dir, date) for x in _RADAR_TILE_RANGE_X for y in _RADAR_TILE_RANGE_Y]
        with ThreadPoolExecutor(max_workers=_MAX_WORKERS) as executor:
            list(tqdm(executor.map(_download_radar_tile, tasks), total=len(tasks), disable=_tqdm_disable))
        tiles = sorted(Path(temp_dir).glob('radar-*.png'))
        expected = len(_RADAR_TILE_RANGE_X) * len(_RADAR_TILE_RANGE_Y)
        if len(tiles) != expected:
            logger.error(f'Expected {expected} radar tiles, got {len(tiles)}')
            raise SystemExit(1)
        return _assemble_tiles(tiles, columns=_RADAR_COLUMNS)


def archive_radar(date: str, radar_path: Path) -> None:
    dst = _radar_archive_path(date)
    dst.write_bytes(radar_path.read_bytes())
    logger.info(f'Archived {dst}')


def download_radar(*, check_deps: bool = True, archive_only: bool = False) -> Path:
    """Download the latest radar map; with archive_only, save straight to the radar archive."""
    if check_deps:
        check_dependencies()

    date = _current_radar_date()
    canvas = _fetch_radar_canvas(date)
    _RADAR_DIR.mkdir(parents=True, exist_ok=True)
    if archive_only:
        dst = _radar_archive_path(date)
        canvas.save(dst)
        logger.info(f'Archived {dst}')
        return dst
    _RADAR.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(_RADAR)
    if settings.historic_enabled:
        archive_radar(date, _RADAR)
    return _RADAR
