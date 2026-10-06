from pathlib import Path

import yaml
from pydantic import BaseModel


class ConfigPaths(BaseModel):
    package: Path = Path(__file__).parent / 'config.yaml'
    system: Path = Path('/etc/meteocat/config.yaml')
    user: Path = Path.home() / '.local' / 'share' / 'meteocat' / 'config.yaml'


class WallpaperSettings(BaseModel):
    model_config = {'arbitrary_types_allowed': True}

    service_name: str = 'meteocat_wallpaper_generator'
    systemd_user_dir: Path = Path.home() / '.config' / 'systemd' / 'user'
    working_directory: Path = Path.home() / '.local' / 'share' / 'meteocat'
    service_exec: str = f'/usr/bin/uv run --project {Path(__file__).parent.parent} meteocat'

    scheduler: str = 'auto'
    desktop_environment: str = 'auto'
    cron_schedule: str = '*/6 * * * *'

    background_raw: Path = Path('background/background_raw.png')
    background_4k: Path = Path('background/background_4K.png')
    background_4k_dark: Path = Path('background/background_4K_dark.png')
    radar: Path = Path('radar.png')
    wallpaper: Path = Path('wallpaper/wallpaper.png')
    wallpaper_dark: Path = Path('wallpaper/wallpaper_dark.png')
    wallpaper_history: Path = Path('history')
    historic_enabled: bool = False

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

    log_level: str = 'INFO'

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


def _load_yaml(path: Path) -> dict[str, object] | None:
    if path.is_file():
        return yaml.safe_load(path.read_text())
    return None


def _apply_overrides(base: WallpaperSettings, overrides: dict[str, object]) -> WallpaperSettings:
    field_names = set(base.model_fields.keys())
    filtered = {k: v for k, v in overrides.items() if k in field_names}
    for key, val in filtered.items():
        ann = base.model_fields[key].annotation
        if ann is range and isinstance(val, list):
            filtered[key] = range(val[0], val[-1] + 1) if val else range(0)
        elif ann is tuple and isinstance(val, list):
            filtered[key] = tuple(val)
    if not filtered:
        return base
    return WallpaperSettings(**{**base.model_dump(), **filtered})


def _load_config() -> WallpaperSettings:
    paths = ConfigPaths()
    result = WallpaperSettings()
    for path in (paths.package, paths.system, paths.user):
        data = _load_yaml(path)
        if data is not None:
            result = _apply_overrides(result, data)
    return result


settings = _load_config()


def _serialize_value(v: object) -> object:
    if isinstance(v, Path):
        return str(v)
    if isinstance(v, range):
        return list(v)
    if isinstance(v, tuple):
        return list(v)
    if hasattr(v, 'value'):
        return v.value
    return v


def save_config(field: str | None = None) -> None:
    paths = ConfigPaths()
    paths.user.parent.mkdir(parents=True, exist_ok=True)
    existing = _load_yaml(paths.user) or {}
    if field is not None:
        existing[field] = _serialize_value(getattr(settings, field))
    else:
        existing = {k: _serialize_value(v) for k, v in settings.model_dump().items()}
    paths.user.write_text(yaml.dump(existing, default_flow_style=False, sort_keys=False))
