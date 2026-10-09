from pathlib import Path

import yaml
from pydantic import BaseModel

_HISTORY_DIR = Path('history')


class ConfigPaths(BaseModel):
    package: Path = Path(__file__).parent / 'config.yaml'
    system: Path = Path('/etc/meteocat/config.yaml')
    user: Path = Path.home() / '.local' / 'share' / 'meteocat' / 'config.yaml'


class VideoProfile(BaseModel):
    model_config = {'arbitrary_types_allowed': True}

    container: str
    codec: str
    crf: int = 23
    fps: int = 25
    preset: str = 'medium'


class VideoSettings(BaseModel):
    model_config = {'arbitrary_types_allowed': True}

    frames_per_radar: int = 10
    output_dir: Path = Path('videos')
    profiles: dict[str, VideoProfile] = {
        'mkv': VideoProfile(container='mkv', codec='libx265', crf=23),
        'mp4': VideoProfile(container='mp4', codec='libx264', crf=23),
        'webm': VideoProfile(container='webm', codec='libvpx-vp9', crf=32),
    }


class WallpaperSettings(BaseModel):
    model_config = {'arbitrary_types_allowed': True}

    service_name: str = 'meteocat_wallpaper_generator'
    systemd_user_dir: Path = Path.home() / '.config' / 'systemd' / 'user'
    working_directory: Path = Path.home() / '.local' / 'share' / 'meteocat'
    service_exec: str = f'/usr/bin/uv run --project {Path(__file__).parent.parent} meteocat'

    scheduler: str = 'auto'
    desktop_environment: str = 'auto'

    log_level: str = 'INFO'

    historic_enabled: bool = False

    video: VideoSettings = VideoSettings()


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
