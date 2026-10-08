from pathlib import Path
from random import uniform
from time import sleep

import requests

from meteocat.logger import logger

_BACKGROUND_TILE_MAX_Y = 647
_BACKGROUND_TILE_OFFSET_X = 510
_MAX_RETRIES = 5
_RADAR_OFFSET_X = 63
_RADAR_OFFSET_Y = 80
_REQUEST_TIMEOUT = 30
_RETRY_BACKOFF_BASE = 4


def _download_tile(url: str, dest: Path) -> None:
    last_response: requests.Response | None = None
    for attempt in range(_MAX_RETRIES):
        try:
            response = requests.get(url, timeout=_REQUEST_TIMEOUT)
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
                _MAX_RETRIES,
            )
        cap = _RETRY_BACKOFF_BASE ** (attempt + 1)
        sleep(uniform(0, cap))  # ruff: ignore[suspicious-non-cryptographic-random-usage]  # nosec B311
    else:
        if last_response is not None:
            last_response.raise_for_status()
        msg = f'Failed to download {url} after {_MAX_RETRIES} attempts'
        raise RuntimeError(msg)


def _download_background_tile(args: tuple[int, int, str]) -> None:
    x, y, temp_dir = args
    url = f'https://static-m.meteo.cat/tiles/fons/GoogleMapsCompatible/10/000/000/{x}/000/000/{y}.png'
    dest = Path(temp_dir) / f'background-{-(y - _BACKGROUND_TILE_MAX_Y):02}-{(x - _BACKGROUND_TILE_OFFSET_X):02}.png'
    _download_tile(url, dest)


def _download_radar_tile(args: tuple[int, int, str, str]) -> None:
    x, y, temp_dir, date = args
    url = f'https://static-m.meteo.cat/tiles/radar/{date}/07/000/000/0{x}/000/000/0{y}.png'
    dest = Path(temp_dir) / f'radar-{-(y - _RADAR_OFFSET_Y)}-{(x - _RADAR_OFFSET_X)}.png'
    _download_tile(url, dest)
