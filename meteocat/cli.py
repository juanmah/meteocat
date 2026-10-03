import logging
import random
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path
from shutil import which

import gi
import requests
import typer
from PIL import Image, ImageDraw, ImageOps
from rich.logging import RichHandler
from tqdm import tqdm

from meteocat.config import settings

gi.require_version('Gio', '2.0')
from gi.repository import Gio  # ruff: ignore[module-import-not-at-top-of-file]

logger = logging.getLogger('meteocat')
logger.setLevel(logging.INFO)
if sys.stderr.isatty():
    rich_handler = RichHandler(rich_tracebacks=True, markup=True)
    rich_handler.setFormatter(logging.Formatter('%(message)s', datefmt='[%X]'))
    logger.addHandler(rich_handler)
else:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter('%(message)s'))
    logger.addHandler(handler)

app = typer.Typer(help='Set the desktop wallpaper by fetching radar images from meteo.cat.')


def _download_tile(url: str, dest: Path) -> None:
    last_response: requests.Response | None = None
    for attempt in range(settings.max_retries):
        try:
            response = requests.get(url, timeout=settings.request_timeout)
        except requests.RequestException as exc:
            logger.warning('Download failed (%s), retrying...', exc)
        else:
            last_response = response
            if response.status_code == 200:
                dest.write_bytes(response.content)
                return
            logger.warning(
                'Download failed (%s) for %s, attempt %d/%d, retrying...',
                response.status_code,
                url,
                attempt + 1,
                settings.max_retries,
            )
        cap = settings.retry_backoff_base ** (attempt + 1)
        time.sleep(random.uniform(0, cap))  # ruff: ignore[suspicious-non-cryptographic-random-usage]  # nosec B311
    else:
        if last_response is not None:
            last_response.raise_for_status()
        msg = f'Failed to download {url} after {settings.max_retries} attempts'
        raise RuntimeError(msg)


def _assemble_tiles(tiles: list[Path], columns: int) -> Image.Image:
    tile_size = settings.tile_size
    images = [Image.open(t) for t in tiles]
    rows = (len(images) + columns - 1) // columns
    width = columns * tile_size
    height = rows * tile_size
    canvas = Image.new('RGBA', (width, height), (0, 0, 0, 0))
    for i, img in enumerate(images):
        col = i % columns
        row = i // columns
        canvas.paste(img, (col * tile_size, row * tile_size))
    return canvas


@app.command()
def check_dependencies() -> None:
    """Check for required system packages dependencies and give information if any are missing."""
    for name, pkg in (('uv', 'uv'), ('gsettings', 'glib2')):
        if which(name) is None:
            logger.error(f'[red]ERROR[/red]: [bold]{pkg}[/bold] not found. Install [bold]{pkg}[/bold].')
            logger.error('[red]Exiting[/red].')
            raise SystemExit


def _download_background_tile(args: tuple[int, int, str]) -> None:
    x, y, temp_dir = args
    url = f'https://static-m.meteo.cat/tiles/fons/GoogleMapsCompatible/10/000/000/{x}/000/000/{y}.png'
    dest = (
        Path(temp_dir) / f'background-'
        f'{-(y - settings.background_tile_max_y):02}-'
        f'{(x - settings.background_tile_offset_x):02}.png'
    )
    _download_tile(url, dest)


@app.command()
def generate_background() -> None:
    """Generate the background map of Catalonia from meteo.cat sources, and adapt it to 4K."""
    check_dependencies()

    with tempfile.TemporaryDirectory() as temp_dir:
        tasks = [(x, y, temp_dir) for x in settings.background_tile_range_x for y in settings.background_tile_range_y]
        with ThreadPoolExecutor(max_workers=settings.max_workers) as executor:
            list(tqdm(executor.map(_download_background_tile, tasks), total=len(tasks)))
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
        draw = ImageDraw.Draw(img)
        draw.rectangle(settings.rectangle_coords, fill='#9c9c9c')
        img.save(settings.background_4k)
        white = Image.new('RGB', img.size, (255, 255, 255))
        white.paste(img.convert('RGBA'), mask=img.split()[3])
        img_dark = ImageOps.invert(white)
        img_dark.save(settings.background_4k_dark)
        ImageDraw.floodfill(img_dark, settings.floodfill_pos, (41, 41, 41), thresh=settings.floodfill_thresh)
        img_dark.save(settings.background_4k_dark)


def _composite_radar(background_path: Path, radar_path: Path, output_path: Path, opacity: float) -> None:
    background = Image.open(background_path).convert('RGBA')
    radar = Image.open(radar_path).convert('RGBA')
    radar = radar.resize(
        (int(background.width * settings.resize_factor), int(background.height * settings.resize_factor)),
        Image.LANCZOS,
    )
    alpha = radar.split()[3]
    alpha = alpha.point(lambda p: int(p * opacity))
    radar.putalpha(alpha)
    background.paste(radar, (settings.paste_offset_x, settings.paste_offset_y), radar)
    background.convert('RGB').save(output_path)


def _set_wallpaper(path: Path, *, dark: bool = False) -> None:
    key = 'picture-uri-dark' if dark else 'picture-uri'
    gsettings = Gio.Settings.new('org.gnome.desktop.background')
    gsettings.set_string(key, f'file://{path}')


@app.callback(invoke_without_command=True)
def main(ctx: typer.Context) -> None:
    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help())
        raise typer.Exit


def _download_radar_tile(args: tuple[int, int, str, datetime]) -> None:
    x, y, temp_dir, now = args
    date = f'{now.year}/{now.month:02}/{now.day:02}/{now.hour:02}/{now.minute // 6 * 6:02}'
    url = f'https://static-m.meteo.cat/tiles/radar/{date}/07/000/000/0{x}/000/000/0{y}.png'
    dest = Path(temp_dir) / f'radar-{-(y - settings.radar_offset_y)}-{(x - settings.radar_offset_x)}.png'
    _download_tile(url, dest)


@app.command()
def generate_wallpaper() -> None:
    """Generate a wallpaper with an updated meteo.cat radar map."""
    check_dependencies()
    if not settings.background_4k.is_file():
        logger.info("> Background doesn't exist.")
        logger.info('> Generating a background map of Catalonia from meteo.cat sources.')
        generate_background()

    with tempfile.TemporaryDirectory() as temp_dir:
        now = datetime.now(UTC) - timedelta(minutes=settings.radar_delay_minutes)
        tasks = [(x, y, temp_dir, now) for x in settings.radar_tile_range_x for y in settings.radar_tile_range_y]
        with ThreadPoolExecutor(max_workers=settings.max_workers) as executor:
            list(tqdm(executor.map(_download_radar_tile, tasks), total=len(tasks)))
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
