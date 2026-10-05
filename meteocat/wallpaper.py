import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path

from tqdm import tqdm

from meteocat.config import settings
from meteocat.deps import check_dependencies
from meteocat.download import _download_background_tile, _download_radar_tile
from meteocat.image import _apply_background_overlays, _assemble_tiles, _composite_radar, _make_dark_variant
from meteocat.logging import logger

_tqdm_disable = not sys.stderr.isatty()


def _set_wallpaper(path: Path, *, dark: bool = False) -> None:
    import gi

    gi.require_version('Gio', '2.0')
    from gi.repository import Gio

    key = 'picture-uri-dark' if dark else 'picture-uri'
    gsettings = Gio.Settings.new('org.gnome.desktop.background')
    gsettings.set_string(key, f'file://{path}')


def generate_background() -> None:
    check_dependencies()

    with tempfile.TemporaryDirectory() as temp_dir:
        tasks = [(x, y, temp_dir) for x in settings.background_tile_range_x for y in settings.background_tile_range_y]
        with ThreadPoolExecutor(max_workers=settings.max_workers) as executor:
            list(tqdm(executor.map(_download_background_tile, tasks), total=len(tasks), disable=_tqdm_disable))
        tiles = sorted(Path(temp_dir).glob('background-*.png'))
        expected = len(settings.background_tile_range_x) * len(settings.background_tile_range_y)
        if len(tiles) != expected:
            logger.error(f'Expected {expected} background tiles, got {len(tiles)}')
            raise SystemExit(1)
        canvas = _assemble_tiles(tiles, columns=settings.background_columns)
        settings.background_raw.parent.mkdir(parents=True, exist_ok=True)
        canvas.save(settings.background_raw)
        crop_left = settings.crop_left
        crop_top = settings.crop_top
        crop_width = settings.crop_width
        crop_height = settings.crop_height
        img = canvas.crop((crop_left, crop_top, crop_left + crop_width, crop_top + crop_height))
        _apply_background_overlays(img)
        img.save(settings.background_4k)
        img_dark = _make_dark_variant(img)
        img_dark.save(settings.background_4k_dark)


def archive_wallpaper(date: str) -> None:
    year, month, day, hour, minute = date.split('/')
    timestamp = f'{year}-{month}-{day}_{hour}-{minute}'
    for suffix, subdir in (('', 'light'), ('_dark', 'dark')):
        target_dir = settings.wallpaper_history / subdir
        target_dir.mkdir(parents=True, exist_ok=True)
        src = settings.wallpaper if suffix == '' else settings.wallpaper_dark
        dst = target_dir / f'wallpaper{suffix}_{timestamp}.png'
        dst.write_bytes(src.read_bytes())
        logger.info(f'Archived {dst}')


def generate_wallpaper() -> None:
    check_dependencies()
    if not settings.background_4k.is_file():
        logger.info("> Background doesn't exist.")
        logger.info('> Generating a background map of Catalonia from meteo.cat sources.')
        generate_background()

    now = datetime.now(UTC) - timedelta(minutes=settings.radar_delay_minutes)
    date = f'{now.year}/{now.month:02}/{now.day:02}/{now.hour:02}/{now.minute // 6 * 6:02}'

    with tempfile.TemporaryDirectory() as temp_dir:
        tasks = [(x, y, temp_dir, date) for x in settings.radar_tile_range_x for y in settings.radar_tile_range_y]
        with ThreadPoolExecutor(max_workers=settings.max_workers) as executor:
            list(tqdm(executor.map(_download_radar_tile, tasks), total=len(tasks), disable=_tqdm_disable))
        tiles = sorted(Path(temp_dir).glob('radar-*.png'))
        expected = len(settings.radar_tile_range_x) * len(settings.radar_tile_range_y)
        if len(tiles) != expected:
            logger.error(f'Expected {expected} radar tiles, got {len(tiles)}')
            raise SystemExit(1)
        canvas = _assemble_tiles(tiles, columns=settings.radar_columns)
        radar = Path(temp_dir) / settings.radar
        canvas.save(radar)
        settings.wallpaper.parent.mkdir(parents=True, exist_ok=True)
        _composite_radar(settings.background_4k, radar, settings.wallpaper, settings.opacity_radar)
        _composite_radar(settings.background_4k_dark, radar, settings.wallpaper_dark, settings.opacity_radar_dark)

    _set_wallpaper(settings.wallpaper.resolve())
    _set_wallpaper(settings.wallpaper_dark.resolve(), dark=True)
    logger.info('Updated meteo.cat radar background.')
    if settings.historic_enabled:
        archive_wallpaper(date)
