#!/usr/bin/env python3

"""
Set the desktop wallpaper by fetching radar images from meteo.cat.

This script automates the creation of a desktop background combining radar maps with background map of Catalonia,
also sourced from meteo.cat.
"""

import glob
import logging
import os
import subprocess  # nosec B404
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path
from shutil import which

import requests
import typer
from PIL import Image, ImageDraw, ImageOps
from rich.logging import RichHandler
from tqdm import tqdm

from src.config import settings

logger = logging.getLogger('meteocat')
logger.setLevel(logging.INFO)
rich_handler = RichHandler(rich_tracebacks=True)
rich_handler.setFormatter(logging.Formatter('%(message)s', datefmt='[%X]'))
logger.addHandler(rich_handler)

app = typer.Typer(help='Set the desktop wallpaper by fetching radar images from meteo.cat.')


def _download_tile(url: str, dest: Path) -> None:
    for attempt in range(settings.max_retries):
        response = requests.get(url, timeout=settings.request_timeout)
        if response.status_code == 200:
            dest.write_bytes(response.content)
            return
        wait = settings.retry_backoff_base**attempt
        logger.warning(f'Download failed ({response.status_code}), retrying in {wait}s...')
        time.sleep(wait)
    else:
        response.raise_for_status()


def _assemble_tiles(tiles: list[Path], columns: int) -> Image.Image:
    images = [Image.open(t) for t in tiles]
    rows = (len(images) + columns - 1) // columns
    width = columns * 256
    height = rows * 256
    canvas = Image.new('RGBA', (width, height), (0, 0, 0, 0))
    for i, img in enumerate(images):
        col = i % columns
        row = i // columns
        canvas.paste(img, (col * 256, row * 256))
    return canvas


def _check_dependencies() -> None:
    for command, package in {'inkscape': 'inkscape', 'gsettings': 'glib2', 'uv': 'uv'}.items():
        if which(command) is None:
            logger.error(
                f'[red]ERROR[/red]: [black][bold]{command}[/bold] command not found. '
                f'Please install [bold]{package}[/bold].'
            )
            logger.error('[red]Exiting[/red].')
            raise SystemExit


@app.command()
def check_dependencies():
    """Check for required system packages dependencies and give information if any are missing."""
    _check_dependencies()


@app.command()
def generate_background():
    """Generate the background map of Catalonia from meteo.cat sources, and adapt it to 4K."""

    def _download_background_tile(args: tuple[int, int, str]) -> None:
        x, y, temp_dir = args
        url = f'https://static-m.meteo.cat/tiles/fons/GoogleMapsCompatible/10/000/000/{x}/000/000/{y}.png'
        dest = (
            Path(temp_dir) / f'background-'
            f'{-(y - settings.background_tile_max_y):02}-'
            f'{(x - settings.background_tile_offset_x):02}.png'
        )
        _download_tile(url, dest)

    with tempfile.TemporaryDirectory() as temp_dir:
        tasks = [(x, y, temp_dir) for x in settings.background_tile_range_x for y in settings.background_tile_range_y]
        with ThreadPoolExecutor(max_workers=10) as executor:
            list(tqdm(executor.map(_download_background_tile, tasks), total=len(tasks)))
        tiles = sorted(glob.glob(f'{temp_dir}/background-*.png'))
        expected = len(settings.background_tile_range_x) * len(settings.background_tile_range_y)
        if len(tiles) != expected:
            logger.error(f'Expected {expected} background tiles, got {len(tiles)}')
            raise SystemExit(1)
        tile_paths = [Path(t) for t in tiles]
        canvas = _assemble_tiles(tile_paths, columns=18)
        canvas.save(settings.background_raw)
        img = Image.open(settings.background_raw)
        img = img.crop((300, 300, 300 + 3840, 300 + 2160))
        draw = ImageDraw.Draw(img)
        draw.rectangle([2266, 2029, 2341, 2079], fill='#9c9c9c')
        img.save(settings.background_4k)
        white = Image.new('RGB', img.size, (255, 255, 255))
        white.paste(img.convert('RGBA'), mask=img.split()[3])
        img_dark = ImageOps.invert(white)
        img_dark.save(settings.background_4k_dark)
        ImageDraw.floodfill(img_dark, (3839, 2159), (41, 41, 41), thresh=140)
        img_dark.save(settings.background_4k_dark)


def _set_wallpaper(path: Path, dark: bool = False) -> None:
    import gi

    gi.require_version('Gio', '2.0')
    from gi.repository import Gio

    key = 'picture-uri-dark' if dark else 'picture-uri'
    gsettings = Gio.Settings.new('org.gnome.desktop.background')
    gsettings.set_string(key, f'file://{path}')


@app.callback(invoke_without_command=True)
def main(ctx: typer.Context):
    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help())
        raise typer.Exit()


@app.command()
def generate_wallpaper():
    """Generate a wallpaper with an updated meteo.cat radar map."""
    _check_dependencies()
    if not os.path.isfile('background/background_4K.png'):
        logger.info("> Background doesn't exist.")
        logger.info('> Generating a background map of Catalonia from meteo.cat sources.')
        generate_background()

    def _download_radar_tile(args: tuple[int, int, str, datetime]) -> None:
        x, y, temp_dir, now = args
        date = f'{now.year}/{now.month:02}/{now.day:02}/{now.hour:02}/{now.minute // 6 * 6:02}'
        url = f'https://static-m.meteo.cat/tiles/radar/{date}/07/000/000/0{x}/000/000/0{y}.png'
        dest = Path(temp_dir) / f'radar-{-(y - settings.radar_offset_y)}-{(x - settings.radar_offset_x)}.png'
        _download_tile(url, dest)

    with tempfile.TemporaryDirectory() as temp_dir:
        now = datetime.now(UTC) - timedelta(minutes=12)
        tasks = [(x, y, temp_dir, now) for x in settings.radar_tile_range_x for y in settings.radar_tile_range_y]
        with ThreadPoolExecutor(max_workers=10) as executor:
            list(tqdm(executor.map(_download_radar_tile, tasks), total=len(tasks)))
        tiles = sorted(glob.glob(f'{temp_dir}/radar-*.png'))
        expected = len(settings.radar_tile_range_x) * len(settings.radar_tile_range_y)
        if len(tiles) != expected:
            logger.error(f'Expected {expected} radar tiles, got {len(tiles)}')
            raise SystemExit(1)
        tile_paths = [Path(t) for t in tiles]
        canvas = _assemble_tiles(tile_paths, columns=3)
        canvas.save(settings.radar)
    inkscape = which('inkscape')
    subprocess.run(  # nosec B603
        [inkscape, '--export-type=png', settings.composite, '--export-filename', settings.wallpaper],
        check=True,
    )
    subprocess.run(  # nosec B603
        [inkscape, '--export-type=png', settings.composite_dark, '--export-filename', settings.wallpaper_dark],
        check=True,
    )
    wallpaper = Path(os.path.abspath(settings.wallpaper))
    _set_wallpaper(wallpaper)
    wallpaper_dark = Path(os.path.abspath(settings.wallpaper_dark))
    _set_wallpaper(wallpaper_dark, dark=True)
    logger.info('Updated meteo.cat radar background.')


if __name__ == '__main__':
    app()
