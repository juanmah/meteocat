from datetime import datetime
from logging import getLogger
from pathlib import Path
from random import uniform
from time import sleep

import requests

from meteocat.config import settings

logger = getLogger('meteocat')


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
        sleep(uniform(0, cap))  # ruff: ignore[suspicious-non-cryptographic-random-usage]  # nosec B311
    else:
        if last_response is not None:
            last_response.raise_for_status()
        msg = f'Failed to download {url} after {settings.max_retries} attempts'
        raise RuntimeError(msg)


def _download_background_tile(args: tuple[int, int, str]) -> None:
    x, y, temp_dir = args
    url = f'https://static-m.meteo.cat/tiles/fons/GoogleMapsCompatible/10/000/000/{x}/000/000/{y}.png'
    dest = (
        Path(temp_dir) / f'background-'
        f'{-(y - settings.background_tile_max_y):02}-'
        f'{(x - settings.background_tile_offset_x):02}.png'
    )
    _download_tile(url, dest)


def _download_radar_tile(args: tuple[int, int, str, datetime]) -> None:
    x, y, temp_dir, now = args
    date = f'{now.year}/{now.month:02}/{now.day:02}/{now.hour:02}/{now.minute // 6 * 6:02}'
    url = f'https://static-m.meteo.cat/tiles/radar/{date}/07/000/000/0{x}/000/000/0{y}.png'
    dest = Path(temp_dir) / f'radar-{-(y - settings.radar_offset_y)}-{(x - settings.radar_offset_x)}.png'
    _download_tile(url, dest)
