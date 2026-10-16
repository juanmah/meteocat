from __future__ import annotations

import logging
import sys
from dataclasses import FrozenInstanceError
from pathlib import Path
from types import SimpleNamespace

import pytest

from meteocat.wallpaper import (
    _SETTERS,
    DeResolution,
    _detect_de,
    _match_env_var,
    _resolve_de_detailed,
    _set_wallpaper,
    generate_background,
    generate_wallpaper,
)


def test_de_resolution_is_frozen_dataclass() -> None:
    r = DeResolution(de='gnome', source='from configuration')
    assert r.de == 'gnome'
    assert r.source == 'from configuration'
    with pytest.raises(FrozenInstanceError):
        r.de = 'x'


def test_match_env_var(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv('XDG_CURRENT_DESKTOP', raising=False)
    assert _match_env_var('XDG_CURRENT_DESKTOP', {'GNOME': 'gnome'}) is None
    monkeypatch.setenv('XDG_CURRENT_DESKTOP', 'GNOME')
    assert _match_env_var('XDG_CURRENT_DESKTOP', {'GNOME': 'gnome'}) == 'gnome'
    monkeypatch.setenv('XDG_CURRENT_DESKTOP', 'KDE')
    assert _match_env_var('XDG_CURRENT_DESKTOP', {'GNOME': 'gnome'}) is None


def test_detect_de_win32(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, 'platform', 'win32')
    assert _detect_de() == DeResolution('windows', 'auto-detected (Windows platform)')


def test_detect_de_env_var(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, 'platform', 'linux')
    monkeypatch.delenv('XDG_CURRENT_DESKTOP', raising=False)
    monkeypatch.delenv('XDG_SESSION_DESKTOP', raising=False)
    monkeypatch.delenv('DESKTOP_SESSION', raising=False)
    monkeypatch.setenv('XDG_CURRENT_DESKTOP', 'GNOME')
    assert _detect_de() == DeResolution('gnome', 'auto-detected via XDG_CURRENT_DESKTOP=GNOME')


def test_detect_de_fallback_which(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, 'platform', 'linux')
    monkeypatch.delenv('XDG_CURRENT_DESKTOP', raising=False)
    monkeypatch.delenv('XDG_SESSION_DESKTOP', raising=False)
    monkeypatch.delenv('DESKTOP_SESSION', raising=False)
    monkeypatch.setattr('meteocat.wallpaper.which', lambda prog: prog == 'plasmashell')
    assert _detect_de() == DeResolution('kde', 'auto-detected via plasmashell process')


def test_detect_de_none(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, 'platform', 'linux')
    monkeypatch.delenv('XDG_CURRENT_DESKTOP', raising=False)
    monkeypatch.delenv('XDG_SESSION_DESKTOP', raising=False)
    monkeypatch.delenv('DESKTOP_SESSION', raising=False)
    monkeypatch.setattr('meteocat.wallpaper.which', lambda _prog: None)
    assert _detect_de() == DeResolution('none', 'auto-detected (no desktop environment detected)')


def test_setters_mapping() -> None:
    assert 'gnome' in _SETTERS
    assert 'windows' in _SETTERS
    assert callable(_SETTERS['gnome'])


def test_resolve_de_detailed_from_configuration(monkeypatch: pytest.MonkeyPatch) -> None:
    from meteocat.config import settings

    monkeypatch.setattr(settings, 'desktop_environment', 'gnome')
    assert _resolve_de_detailed() == DeResolution('gnome', 'from configuration')


def test_resolve_de_detailed_from_configuration_none(monkeypatch: pytest.MonkeyPatch) -> None:
    from meteocat.config import settings

    monkeypatch.setattr(settings, 'desktop_environment', 'none')
    assert _resolve_de_detailed() == DeResolution('none', 'from configuration')


def test_resolve_de_detailed_detects(monkeypatch: pytest.MonkeyPatch) -> None:
    from meteocat.config import settings

    monkeypatch.setattr(settings, 'desktop_environment', 'auto')
    monkeypatch.setattr(sys, 'platform', 'linux')
    monkeypatch.delenv('XDG_CURRENT_DESKTOP', raising=False)
    monkeypatch.delenv('XDG_SESSION_DESKTOP', raising=False)
    monkeypatch.delenv('DESKTOP_SESSION', raising=False)
    monkeypatch.setattr('meteocat.wallpaper.which', lambda _prog: None)
    assert _resolve_de_detailed() == DeResolution('none', 'auto-detected (no desktop environment detected)')


def test_set_wallpaper_none_returns(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from meteocat.config import settings

    monkeypatch.setattr(settings, 'desktop_environment', 'none')
    _set_wallpaper(tmp_path / 'x.png')


def test_set_wallpaper_unknown_warns_and_returns(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture, tmp_path: Path
) -> None:
    monkeypatch.setattr('meteocat.wallpaper._resolve_de', lambda: 'weird-de')
    with caplog.at_level(logging.WARNING):
        _set_wallpaper(tmp_path / 'x.png')
    assert 'No wallpaper setter for DE: weird-de' in caplog.text


def test_set_wallpaper_calls_setter(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from meteocat.config import settings

    monkeypatch.setattr(settings, 'desktop_environment', 'gnome')
    called: list[tuple[Path, bool]] = []
    path = tmp_path / 'x.png'
    monkeypatch.setattr(
        'meteocat.wallpaper._SETTERS',
        {'gnome': lambda p, dark=False: called.append((p, dark))},
    )
    _set_wallpaper(path, dark=True)
    assert called == [(path, True)]


def _install_fake_gi(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, str]]:
    import types

    calls: list[tuple[str, str]] = []

    class FakeSettingsInstance:
        def set_string(self, key: str, value: str) -> None:
            calls.append((key, value))

    class FakeSettingsClass:
        def new(self, _schema_id: str) -> FakeSettingsInstance:
            return FakeSettingsInstance()

    fake_gi = types.ModuleType('gi')
    fake_gi.require_version = lambda *_a, **_k: None
    fake_repo = types.ModuleType('gi.repository')
    fake_repo.Gio = SimpleNamespace(Settings=FakeSettingsClass())
    monkeypatch.setitem(sys.modules, 'gi', fake_gi)
    monkeypatch.setitem(sys.modules, 'gi.repository', fake_repo)
    return calls


def test_set_gnome_sets_key(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from meteocat.wallpaper import _set_gnome

    calls = _install_fake_gi(monkeypatch)
    _set_gnome(tmp_path / 'wallpaper.png')
    assert ('picture-uri', f'file://{tmp_path / "wallpaper.png"}') in calls


def test_set_windows_dark_early_return(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from meteocat.wallpaper import _set_windows

    called: list[str] = []
    monkeypatch.setattr('meteocat.wallpaper.logger.debug', lambda msg, *_a: called.append(msg))
    _set_windows(tmp_path / 'x.png', dark=True)
    assert any('Windows does not support separate dark mode' in str(c) for c in called)


class FakeCanvas:
    def __init__(self) -> None:
        self.saved: list[Path] = []
        self.cropped = None

    def save(self, path: Path) -> None:
        self.saved.append(path)

    def crop(self, box: object) -> FakeCanvas:
        self.cropped = box
        return self


def test_generate_background_wrong_tile_count_exits(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    def fake_download(_args: object) -> None:
        pass  # create no tiles

    monkeypatch.setattr('meteocat.wallpaper._download_background_tile', fake_download)
    monkeypatch.setattr('meteocat.wallpaper._assemble_tiles', lambda _tiles, _columns: FakeCanvas())
    monkeypatch.setattr('meteocat.wallpaper._apply_background_overlays', lambda _img: None)
    monkeypatch.setattr('meteocat.wallpaper._make_dark_variant', lambda _img: FakeCanvas())
    monkeypatch.setattr('meteocat.wallpaper._BACKGROUND_RAW', tmp_path / 'raw.png')
    monkeypatch.setattr('meteocat.wallpaper.BACKGROUND_4K', tmp_path / 'bg.png')
    monkeypatch.setattr('meteocat.wallpaper.BACKGROUND_4K_DARK', tmp_path / 'bg_dark.png')

    with pytest.raises(SystemExit):
        generate_background(check_deps=False)


def test_generate_background_happy_path(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    def fake_download(args: tuple[int, int, str]) -> None:
        x, y, temp_dir = args
        dest = Path(temp_dir) / f'background-{-(y - 647):02}-{(x - 510):02}.png'
        dest.write_bytes(b'fake')

    canvas = FakeCanvas()
    overlays: list[object] = []
    dark_variants: list[object] = []

    monkeypatch.setattr('meteocat.wallpaper._download_background_tile', fake_download)
    monkeypatch.setattr('meteocat.wallpaper._assemble_tiles', lambda _tiles, **_kwargs: canvas)
    monkeypatch.setattr('meteocat.wallpaper._apply_background_overlays', lambda img: overlays.append(img))
    monkeypatch.setattr('meteocat.wallpaper._make_dark_variant', lambda img: dark_variants.append(img) or canvas)
    raw = tmp_path / 'raw.png'
    bg = tmp_path / 'bg.png'
    bg_dark = tmp_path / 'bg_dark.png'
    monkeypatch.setattr('meteocat.wallpaper._BACKGROUND_RAW', raw)
    monkeypatch.setattr('meteocat.wallpaper.BACKGROUND_4K', bg)
    monkeypatch.setattr('meteocat.wallpaper.BACKGROUND_4K_DARK', bg_dark)

    generate_background(check_deps=False)

    assert raw in canvas.saved
    assert bg in canvas.saved
    assert bg_dark in canvas.saved
    assert len(overlays) == 1
    assert len(dark_variants) == 1


def test_generate_wallpaper_uses_existing_background(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    radar_path = tmp_path / 'radar.png'
    wallpaper = tmp_path / 'wallpaper.png'
    wallpaper_dark = tmp_path / 'wallpaper_dark.png'
    composite_calls: list[tuple] = []
    set_calls: list[tuple] = []

    monkeypatch.setattr('meteocat.wallpaper.check_dependencies', lambda: None)
    monkeypatch.setattr('meteocat.wallpaper.fetch_radar', lambda: radar_path)
    monkeypatch.setattr(
        'meteocat.wallpaper._composite_radar',
        lambda bg, radar, output, opacity: composite_calls.append((bg, radar, output, opacity)),
    )
    monkeypatch.setattr('meteocat.wallpaper._set_wallpaper', lambda path, dark=False: set_calls.append((path, dark)))
    monkeypatch.setattr('meteocat.wallpaper.BACKGROUND_4K', tmp_path / 'exists.png')
    (tmp_path / 'exists.png').write_bytes(b'bg')
    monkeypatch.setattr('meteocat.wallpaper._WALLPAPER', wallpaper)
    monkeypatch.setattr('meteocat.wallpaper._WALLPAPER_DARK', wallpaper_dark)

    generate_wallpaper(check_deps=False)

    assert len(composite_calls) == 2
    assert set_calls == [(wallpaper, False), (wallpaper_dark, True)]
