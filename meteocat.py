#!/usr/bin/env python3

"""
Set the desktop wallpaper by fetching radar images from meteo.cat.

This script automates the creation of a desktop background combining radar maps with background map of Catalonia,
also sourced from meteo.cat.
"""

import logging
import os
import subprocess
import tempfile
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from shutil import which

import requests
import typer
from rich.logging import RichHandler
from tqdm import tqdm

BACKGROUND_RAW = 'background/background_raw.png'
BACKGROUND_4K = 'background/background_4K.png'
BACKGROUND_4K_DARK = 'background/background_4K_dark.png'
RADAR = 'output/radar.png'
COMPOSITE = 'wallpaper.svg'
COMPOSITE_DARK = 'wallpaper_dark.svg'
WALLPAPER = 'output/wallpaper.png'
WALLPAPER_DARK = 'output/wallpaper_dark.png'

logger = logging.getLogger('meteocat')
logger.setLevel(logging.INFO)
rich_handler = RichHandler(rich_tracebacks=True)
rich_handler.setFormatter(logging.Formatter('%(message)s', datefmt='[%X]'))
logger.addHandler(rich_handler)

app = typer.Typer(help='Set the desktop wallpaper by fetching radar images from meteo.cat.')


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

    def _download_tile(args):
        x, y, temp_dir = args
        url = f'https://static-m.meteo.cat/tiles/fons/GoogleMapsCompatible/10/000/000/{x}/000/000/{y}.png'
        response = requests.get(url)
        # Transform 'absolute' coordinates in 'relative' ones. Fixing order.
        with open(f'{temp_dir}/background-{-(y-647):02}-{(x-510):02}.png', 'wb') as f:
            f.write(response.content)

    with tempfile.TemporaryDirectory() as temp_dir:
        tasks = [(x, y, temp_dir) for x in range(510, 528) for y in range(638, 648)]
        with ThreadPoolExecutor(max_workers=10) as executor:
            list(tqdm(executor.map(_download_tile, tasks), total=len(tasks)))
        tiles = f'{temp_dir}/background-*.png'
        # Join background
        subprocess.call(f'montage -tile 18x -geometry +0+0 {tiles} {BACKGROUND_RAW}', shell=True)
        # Crop to 4K
        subprocess.call(
            f'magick {BACKGROUND_RAW} -crop 3840x2160+300+300 '
            '-fill "#9c9c9c" -draw "rectangle 2266,2029 2340,2078" '
            f'{BACKGROUND_4K}',
            shell=True,
        )

        # Crop to 4K dark
        subprocess.call(f'magick {BACKGROUND_4K} -alpha off -negate {BACKGROUND_4K_DARK}', shell=True)
        subprocess.call(
            f'magick {BACKGROUND_4K_DARK} -fill "#292929" -fuzz "9000" -draw "color 3839,2159 floodfill" '
            f'{BACKGROUND_4K_DARK}',
            shell=True,
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

    # Get current radar map
    def _download_radar_tile(args):
        x, y, temp_dir, now = args
        date = f'{now.year}/{now.month:02}/{now.day:02}/{now.hour:02}/{now.minute // 6 * 6:02}'
        url = f'https://static-m.meteo.cat/tiles/radar/{date}/07/000/000/0{x}/000/000/0{y}.png'
        response = requests.get(url)
        # Transform 'absolute' coordinates in 'relative' ones. Fixing order.
        with open(f'{temp_dir}/radar-{(-(y-80))}-{(x-63)}.png', 'wb') as f:
            f.write(response.content)

    with tempfile.TemporaryDirectory() as temp_dir:
        now = datetime.now(UTC) - timedelta(minutes=12)
        tasks = [(x, y, temp_dir, now) for x in range(63, 66) for y in range(79, 81)]
        with ThreadPoolExecutor(max_workers=10) as executor:
            list(tqdm(executor.map(_download_radar_tile, tasks), total=len(tasks)))
        tiles = f'{temp_dir}/radar-*.png'
        # Join radar
        subprocess.call(f'montage -tile 3x -geometry +0+0 -background none {tiles} {RADAR}', shell=True)
    # Generate wallpaper with background and radar
    subprocess.call(f'inkscape --export-type="png" {COMPOSITE} --export-filename={WALLPAPER}', shell=True)
    subprocess.call(f'inkscape --export-type="png" {COMPOSITE_DARK} --export-filename={WALLPAPER_DARK}', shell=True)
    # Set wallpaper as the desktop background
    wallpaper = os.path.abspath(WALLPAPER)
    subprocess.call(f'dbus-launch gsettings set org.gnome.desktop.background picture-uri {wallpaper}', shell=True)
    wallpaper_dark = os.path.abspath(WALLPAPER_DARK)
    subprocess.call(
        f'dbus-launch gsettings set org.gnome.desktop.background picture-uri-dark {wallpaper_dark}', shell=True
    )
    logger.info('Updated meteo.cat radar background.')


if __name__ == '__main__':
    app()
