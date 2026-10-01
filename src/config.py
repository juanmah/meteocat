from pathlib import Path

from pydantic import BaseModel


class WallpaperSettings(BaseModel):
    model_config = {'arbitrary_types_allowed': True}

    background_raw: Path = Path('background/background_raw.png')
    background_4k: Path = Path('background/background_4K.png')
    background_4k_dark: Path = Path('background/background_4K_dark.png')
    radar: Path = Path('output/radar.png')
    wallpaper: Path = Path('output/wallpaper.png')
    wallpaper_dark: Path = Path('output/wallpaper_dark.png')

    background_tile_range_x: range = range(510, 528)
    background_tile_range_y: range = range(638, 648)
    background_tile_offset_x: int = 510
    background_tile_offset_y: int = 638
    background_tile_max_y: int = 647

    radar_tile_range_x: range = range(63, 66)
    radar_tile_range_y: range = range(79, 81)
    radar_offset_x: int = 63
    radar_offset_y: int = 80

    request_timeout: int = 30
    max_retries: int = 5
    retry_backoff_base: int = 4


settings = WallpaperSettings()
