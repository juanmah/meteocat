import os
import sys
from pathlib import Path
from shutil import which

import yaml
from pydantic import BaseModel


class ConfigPaths(BaseModel):
    package: Path = Path(__file__).parent / 'config.yaml'
    system: Path = Path('/etc/meteocat/config.yaml') if sys.platform != 'win32' else Path()
    user: Path = (
        Path(os.environ.get('LOCALAPPDATA', Path.home())) / 'meteocat' / 'config.yaml'
        if sys.platform == 'win32'
        else Path.home() / '.local' / 'share' / 'meteocat' / 'config.yaml'
    )


def _default_uv_bin() -> str:
    path = which('uv')
    if path is None:
        return 'uv'
    return path


def _default_service_exec() -> str:
    project_root = Path(__file__).parent.parent
    uv_bin = _default_uv_bin()
    return f'{uv_bin} run --project {project_root} meteocat'


class WallpaperSettings(BaseModel):
    model_config = {'arbitrary_types_allowed': True}

    service_name: str = 'meteocat_wallpaper_generator'
    systemd_user_dir: Path = Path.home() / '.config' / 'systemd' / 'user'
    working_directory: Path = (
        Path(os.environ.get('LOCALAPPDATA', Path.home())) / 'meteocat'
        if sys.platform == 'win32'
        else Path.home() / '.local' / 'share' / 'meteocat'
    )
    project_root: Path = Path(__file__).parent.parent
    uv_bin: str = _default_uv_bin()
    service_exec: str = _default_service_exec()

    scheduler: str = 'auto'
    desktop_environment: str = 'auto'

    log_level: str = 'INFO'


def _load_yaml(path: Path) -> dict[str, object] | None:
    if path.is_file():
        return yaml.safe_load(path.read_text())
    return None


def _apply_overrides(base: BaseModel, overrides: dict[str, object]) -> BaseModel:
    model_cls = type(base)
    field_names = set(model_cls.model_fields.keys())
    filtered = {k: v for k, v in overrides.items() if k in field_names}
    for key, val in filtered.items():
        ann = model_cls.model_fields[key].annotation
        if ann is range and isinstance(val, list):
            filtered[key] = range(val[0], val[-1] + 1) if val else range(0)
        elif ann is tuple and isinstance(val, list):
            filtered[key] = tuple(val)
    if not filtered:
        return base
    return model_cls(**{**base.model_dump(), **filtered})


def _load_config(model_cls: type[BaseModel]) -> BaseModel:
    paths = ConfigPaths()
    result = model_cls()
    for path in (paths.package, paths.system, paths.user):
        data = _load_yaml(path)
        if data is not None:
            result = _apply_overrides(result, data)
    return result


def load_settings(model_cls: type[BaseModel]) -> BaseModel:
    return _load_config(model_cls)


settings = load_settings(WallpaperSettings)


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


def save_settings(model: BaseModel, field: str | None = None) -> None:
    paths = ConfigPaths()
    paths.user.parent.mkdir(parents=True, exist_ok=True)
    existing = _load_yaml(paths.user) or {}
    if field is not None:
        existing[field] = _serialize_value(getattr(model, field))
    else:
        existing = {k: _serialize_value(v) for k, v in model.model_dump().items()}
    paths.user.write_text(yaml.dump(existing, default_flow_style=False, sort_keys=False))


def save_config(field: str | None = None) -> None:
    save_settings(settings, field)
