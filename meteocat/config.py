from pathlib import Path

from pydantic import BaseModel


class WallpaperSettings(BaseModel):
    model_config = {'arbitrary_types_allowed': True}

    service_name: str = 'meteocat_wallpaper_generator'
    systemd_user_dir: Path = Path.home() / '.config' / 'systemd' / 'user'

    background_raw: Path = Path('background/background_raw.png')
    background_4k: Path = Path('background/background_4K.png')
    background_4k_dark: Path = Path('background/background_4K_dark.png')
    radar: Path = Path('radar.png')
    wallpaper: Path = Path('wallpaper/wallpaper.png')
    wallpaper_dark: Path = Path('wallpaper/wallpaper_dark.png')

    background_tile_range_x: range = range(510, 528)
    background_tile_range_y: range = range(638, 648)
    background_tile_offset_x: int = 510
    background_tile_offset_y: int = 638
    background_tile_max_y: int = 647

    radar_tile_range_x: range = range(63, 66)
    radar_tile_range_y: range = range(79, 81)
    radar_offset_x: int = 63
    radar_offset_y: int = 80

    tile_size: int = 256
    background_columns: int = 18
    radar_columns: int = 3
    max_workers: int = 10
    radar_delay_minutes: int = 15

    request_timeout: int = 30
    max_retries: int = 5
    retry_backoff_base: int = 4

    crop_left: int = 300
    crop_top: int = 300
    crop_width: int = 3840
    crop_height: int = 2160
    rectangle_coords: tuple[int, int, int, int] = (2266, 2029, 2341, 2079)
    floodfill_pos: tuple[int, int] = (3839, 2159)
    floodfill_thresh: int = 140
    resize_factor: float = 1.895
    paste_offset_x: int = -2402
    paste_offset_y: int = -299
    opacity_radar: float = 0.8
    opacity_radar_dark: float = 0.3


settings = WallpaperSettings()
