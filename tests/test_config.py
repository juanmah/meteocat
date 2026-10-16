from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import pytest

import yaml
from pydantic import BaseModel

import meteocat.config as config_module
from meteocat.config import (
    WallpaperSettings,
    _apply_overrides,
    _default_service_exec,
    _default_uv_bin,
    _load_config,
    _load_yaml,
    _serialize_value,
    load_settings,
    save_settings,
    settings,
)


@dataclass
class _FakePaths:
    package: Path
    system: Path
    user: Path


def _install_fake_paths(monkeypatch: pytest.MonkeyPatch, package: Path, system: Path, user: Path) -> None:
    paths = _FakePaths(package=package, system=system, user=user)
    monkeypatch.setattr(config_module, 'ConfigPaths', lambda: paths)


def test_default_uv_bin_found(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(config_module, 'which', lambda _cmd: '/usr/bin/uv')
    assert _default_uv_bin() == '/usr/bin/uv'


def test_default_uv_bin_not_found(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(config_module, 'which', lambda _cmd: None)
    assert _default_uv_bin() == 'uv'


def test_default_service_exec(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(config_module, 'which', lambda _cmd: '/usr/bin/uv')
    root = Path(__file__).resolve().parents[1]
    assert _default_service_exec() == f'/usr/bin/uv run --project {root} meteocat'


def test_load_yaml_existing(tmp_path: Path) -> None:
    p = tmp_path / 'config.yaml'
    p.write_text('key: value\n')
    assert _load_yaml(p) == {'key': 'value'}


def test_load_yaml_missing(tmp_path: Path) -> None:
    assert _load_yaml(tmp_path / 'missing.yaml') is None


def test_apply_overrides_filters_unknown_keys() -> None:
    base = WallpaperSettings()
    result = _apply_overrides(base, {'desktop_environment': 'gnome', 'unknown_field': 'x'})
    assert result.desktop_environment == 'gnome'


class _OverrideModel(BaseModel):
    model_config = {'arbitrary_types_allowed': True}

    numbers: range = range(0)
    pair: tuple[int, int] = (1, 2)
    name: str = 'x'


def test_apply_overrides_range_from_list() -> None:
    base = _OverrideModel()
    result = _apply_overrides(base, {'numbers': [1, 2, 3]})
    assert result.numbers == range(1, 4)


def test_apply_overrides_tuple_from_list() -> None:
    base = _OverrideModel()
    result = _apply_overrides(base, {'pair': [9, 8]})
    assert result.pair == (9, 8)


def test_apply_overrides_returns_base_when_nothing_filtered() -> None:
    base = WallpaperSettings()
    result = _apply_overrides(base, {'unknown_field': 'x'})
    assert result is base


def test_load_config_merges_last_wins(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    package = tmp_path / 'config.yaml'
    system = tmp_path / 'system.yaml'
    user = tmp_path / 'user.yaml'
    package.write_text('desktop_environment: gnome\nlog_level: INFO\n')
    system.write_text('log_level: DEBUG\n')
    user.write_text('scheduler: cron\n')
    _install_fake_paths(monkeypatch, package, system, user)
    result = _load_config(WallpaperSettings)
    assert result.desktop_environment == 'gnome'
    assert result.log_level == 'DEBUG'
    assert result.scheduler == 'cron'


def test_load_config_missing_files_are_absent(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _install_fake_paths(monkeypatch, tmp_path / 'pkg.yaml', tmp_path / 'sys.yaml', tmp_path / 'user.yaml')
    result = _load_config(WallpaperSettings)
    assert isinstance(result, WallpaperSettings)


def test_load_settings_delegates_to_load_config(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[type[BaseModel]] = []

    def fake_load_config(model_cls: type[BaseModel]) -> BaseModel:
        calls.append(model_cls)
        return WallpaperSettings()

    monkeypatch.setattr(config_module, '_load_config', fake_load_config)
    load_settings(WallpaperSettings)
    assert calls == [WallpaperSettings]


def test_settings_module_level_instance() -> None:
    assert isinstance(settings, WallpaperSettings)


def test_serialize_value() -> None:
    assert _serialize_value(Path('/foo')) == '/foo'
    assert _serialize_value(range(1, 4)) == [1, 2, 3]
    assert _serialize_value((1, 2)) == [1, 2]
    assert _serialize_value(42) == 42


def test_save_settings_creates_dir_and_writes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    user = tmp_path / 'user.yaml'
    _install_fake_paths(monkeypatch, tmp_path / 'pkg.yaml', tmp_path / 'sys.yaml', user)
    model = WallpaperSettings()
    save_settings(model)
    assert user.is_file()
    data = yaml.safe_load(user.read_text())
    assert data['desktop_environment'] == 'auto'


def test_save_settings_single_field_preserves_existing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    user = tmp_path / 'user.yaml'
    user.write_text('desktop_environment: gnome\nlog_level: INFO\n')
    _install_fake_paths(monkeypatch, tmp_path / 'pkg.yaml', tmp_path / 'sys.yaml', user)
    model = WallpaperSettings()
    model.log_level = 'DEBUG'
    save_settings(model, field='log_level')
    data = yaml.safe_load(user.read_text())
    assert data['desktop_environment'] == 'gnome'
    assert data['log_level'] == 'DEBUG'


def test_save_config_delegates(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []
    monkeypatch.setattr(config_module, 'save_settings', lambda _model, field=None: calls.append(field))
    config_module.save_config('desktop_environment')
    assert calls == ['desktop_environment']
