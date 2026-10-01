#!/usr/bin/env python3

"""
Set the desktop wallpaper by fetching radar images from meteo.cat.

This script automates the creation of a desktop background combining radar maps with background map of Catalonia,
also sourced from meteo.cat.
"""

import glob
import logging
import os
import subprocess
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path
from shutil import which

import requests
import typer
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


@app.command()
def check_dependencies():
    """Check for required system packages dependencies and give information if any are missing."""
    dependencies = {'montage': 'imagemagick', 'magick': 'imagemagick', 'inkscape': 'inkscape', 'gsettings': 'glib2'}
    missing_dependency = False
    for command, package in dependencies.items():
        if which(command) is None:
            logger.error(
                f'[red]ERROR[/red]: [black][bold]{command}[/bold] command not found. '
                f'Please install [bold]{package}[/bold][/black].'
            )
            missing_dependency = True
    if missing_dependency:
        logger.error('[red]Exiting[/red].')
        raise SystemExit


@app.command()
def generate_background():
    """Generate the background map of Catalonia from meteo.cat sources, and adapt it to 4K."""

    def _download_background_tile(args):
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
        subprocess.run(
            ['montage', '-tile', '18x', '-geometry', '+0+0', *tiles, settings.background_raw],
            check=True,
        )
        subprocess.run(
            [
                'magick',
                settings.background_raw,
                '-crop',
                '3840x2160+300+300',
                '-fill',
                '#9c9c9c',
                '-draw',
                'rectangle 2266,2029 2340,2078',
                settings.background_4k,
            ],
            check=True,
        )
        subprocess.run(
            ['magick', settings.background_4k, '-alpha', 'off', '-negate', settings.background_4k_dark],
            check=True,
        )
        subprocess.run(
            [
                'magick',
                settings.background_4k_dark,
                '-fill',
                '#292929',
                '-fuzz',
                '9000',
                '-draw',
                'color 3839,2159 floodfill',
                settings.background_4k_dark,
            ],
            check=True,
        )


@app.command()
@app.callback(invoke_without_command=True)
def generate_wallpaper():
    """Generate a wallpaper with an updated meteo.cat radar map."""
    check_dependencies()
    if not os.path.isfile('background/background_4K.png'):
        logger.info("> Background doesn't exist.")
        logger.info('> Generating a background map of Catalonia from meteo.cat sources.')
        generate_background()

    def _download_radar_tile(args):
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
        subprocess.run(
            ['montage', '-tile', '3x', '-geometry', '+0+0', '-background', 'none', *tiles, settings.radar],
            check=True,
        )
    subprocess.run(
        ['inkscape', '--export-type=png', settings.composite, '--export-filename', settings.wallpaper],
        check=True,
    )
    subprocess.run(
        ['inkscape', '--export-type=png', settings.composite_dark, '--export-filename', settings.wallpaper_dark],
        check=True,
    )
    wallpaper = os.path.abspath(settings.wallpaper)
    subprocess.run(
        ['dbus-launch', 'gsettings', 'set', 'org.gnome.desktop.background', 'picture-uri', wallpaper],
        check=True,
    )
    wallpaper_dark = os.path.abspath(settings.wallpaper_dark)
    subprocess.run(
        ['dbus-launch', 'gsettings', 'set', 'org.gnome.desktop.background', 'picture-uri-dark', wallpaper_dark],
        check=True,
    )
    logger.info('Updated meteo.cat radar background.')


if __name__ == '__main__':
    app()
