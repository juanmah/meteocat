from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import pytest

SCRIPT_PATH = Path(__file__).resolve().parents[1] / 'scripts' / 'post_install.py'


def _load_post_install() -> ModuleType:
    spec = importlib.util.spec_from_file_location('meteocat_post_install_tests', SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


post_install = _load_post_install()
_detect_name = '_detect_desktop'
_run_name = '_run_sync'
_detect_desktop = getattr(post_install, _detect_name)
_run_sync = getattr(post_install, _run_name)


def test_detect_desktop_xdg_current_desktop(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv('XDG_CURRENT_DESKTOP', 'GNOME')
    monkeypatch.delenv('XDG_SESSION_DESKTOP', raising=False)
    monkeypatch.delenv('DESKTOP_SESSION', raising=False)
    assert _detect_desktop() == 'gnome'


def test_detect_desktop_xdg_session_desktop(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv('XDG_CURRENT_DESKTOP', raising=False)
    monkeypatch.setenv('XDG_SESSION_DESKTOP', 'cinnamon')
    monkeypatch.delenv('DESKTOP_SESSION', raising=False)
    assert _detect_desktop() == 'cinnamon'


def test_detect_desktop_desktop_session(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv('XDG_CURRENT_DESKTOP', raising=False)
    monkeypatch.delenv('XDG_SESSION_DESKTOP', raising=False)
    monkeypatch.setenv('DESKTOP_SESSION', 'MATE')
    assert _detect_desktop() == 'mate'


def test_detect_desktop_colon_separated_first_match_wins(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv('XDG_CURRENT_DESKTOP', raising=False)
    monkeypatch.delenv('XDG_SESSION_DESKTOP', raising=False)
    monkeypatch.delenv('DESKTOP_SESSION', raising=False)
    monkeypatch.setenv('XDG_CURRENT_DESKTOP', 'kde:GNOME:xfce')
    assert _detect_desktop() == 'gnome'


def test_detect_desktop_none(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv('XDG_CURRENT_DESKTOP', raising=False)
    monkeypatch.delenv('XDG_SESSION_DESKTOP', raising=False)
    monkeypatch.delenv('DESKTOP_SESSION', raising=False)
    assert _detect_desktop() is None


def test_detect_desktop_unknown_token_ignored(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv('XDG_CURRENT_DESKTOP', raising=False)
    monkeypatch.delenv('XDG_SESSION_DESKTOP', raising=False)
    monkeypatch.delenv('DESKTOP_SESSION', raising=False)
    monkeypatch.setenv('XDG_CURRENT_DESKTOP', 'kde:xfce:LXQt')
    assert _detect_desktop() is None


def test_run_sync_with_extra(monkeypatch: pytest.MonkeyPatch) -> None:
    called: list[list[str]] = []

    def fake_run(command: list[str], *, check: bool) -> None:
        called.append(command)
        assert check is True

    monkeypatch.setattr(post_install.shutil, 'which', lambda _prog: '/usr/bin/uv')
    monkeypatch.setattr(post_install.subprocess, 'run', fake_run)
    _run_sync('gsettings')
    assert called == [['/usr/bin/uv', 'sync', '--extra', 'gsettings']]


def test_run_sync_without_extra(monkeypatch: pytest.MonkeyPatch) -> None:
    called: list[list[str]] = []

    def fake_run(command: list[str], *, check: bool) -> None:
        called.append(command)
        assert check is True

    monkeypatch.setattr(post_install.shutil, 'which', lambda _prog: None)
    monkeypatch.setattr(post_install.subprocess, 'run', fake_run)
    _run_sync(None)
    assert called == [['uv', 'sync']]


def test_main_gsettings_desktop_runs_sync_with_extra(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv('XDG_CURRENT_DESKTOP', 'gnome')
    monkeypatch.delenv('XDG_SESSION_DESKTOP', raising=False)
    monkeypatch.delenv('DESKTOP_SESSION', raising=False)
    called: list[list[str]] = []

    def fake_run(command: list[str], *, check: bool) -> None:
        called.append(command)
        assert check is True

    monkeypatch.setattr(post_install.shutil, 'which', lambda _prog: '/usr/bin/uv')
    monkeypatch.setattr(post_install.subprocess, 'run', fake_run)
    post_install.main()
    assert called == [['/usr/bin/uv', 'sync', '--extra', 'gsettings']]


def test_main_non_gsettings_desktop_runs_base_sync(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv('XDG_CURRENT_DESKTOP', raising=False)
    monkeypatch.delenv('XDG_SESSION_DESKTOP', raising=False)
    monkeypatch.delenv('DESKTOP_SESSION', raising=False)
    called: list[list[str]] = []

    def fake_run(command: list[str], *, check: bool) -> None:
        called.append(command)
        assert check is True

    monkeypatch.setattr(post_install.shutil, 'which', lambda _prog: '/usr/bin/uv')
    monkeypatch.setattr(post_install.subprocess, 'run', fake_run)
    post_install.main()
    assert called == [['/usr/bin/uv', 'sync']]
