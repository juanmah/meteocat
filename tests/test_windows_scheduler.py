from __future__ import annotations

import logging
import sys
import time
from dataclasses import dataclass
from datetime import UTC, datetime, tzinfo
from pathlib import Path
from types import SimpleNamespace

import pytest

from meteocat.windows_scheduler import (
    _next_valid_start_time,
    install,
    status,
    uninstall,
)


@dataclass
class FakeCompletedProcess:
    returncode: int = 0
    stdout: str = ''
    stderr: str = ''


_fixed_now_win: datetime = datetime(2026, 1, 1, 12, 1, 30, tzinfo=UTC)


class _FakeDateTime:
    @classmethod
    def now(cls, _tz: tzinfo | None = None) -> datetime:
        return _fixed_now_win


def _install_fake_datetime(monkeypatch: pytest.MonkeyPatch, fixed: datetime) -> None:
    global _fixed_now_win
    _fixed_now_win = fixed
    monkeypatch.setenv('TZ', 'UTC')
    time.tzset()
    monkeypatch.setattr('meteocat.windows_scheduler.datetime', _FakeDateTime)


def _make_settings(tmp_path: Path) -> SimpleNamespace:
    return SimpleNamespace(
        working_directory=tmp_path / 'meteocat',
        service_exec='uv run --project /x meteocat',
    )


def test_next_valid_start_time_rounds_up(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_fake_datetime(monkeypatch, datetime(2026, 1, 1, 12, 1, 30, tzinfo=UTC))
    assert _next_valid_start_time() == '12:06'


def test_next_valid_start_time_on_boundary(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_fake_datetime(monkeypatch, datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC))
    assert _next_valid_start_time() == '12:06'


def test_install_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, 'platform', 'linux')
    with pytest.raises(SystemExit):
        install()


def test_install_success(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(sys, 'platform', 'win32')
    monkeypatch.setattr(
        'meteocat.windows_scheduler.which',
        lambda prog: 'schtasks.exe' if prog == 'schtasks.exe' else None,
    )
    settings = _make_settings(tmp_path)
    monkeypatch.setattr('meteocat.windows_scheduler.settings', settings)
    calls: list[list[str]] = []

    def fake_run(args: list[str]) -> FakeCompletedProcess:
        calls.append(args)
        return FakeCompletedProcess(0, '', '')

    monkeypatch.setattr('meteocat.windows_scheduler._run', fake_run)
    _install_fake_datetime(monkeypatch, datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC))
    install()

    wrapper = settings.working_directory.resolve() / 'meteocat_wallpaper.vbs'
    assert wrapper.is_file()
    create_call = next(c for c in calls if c[0] == 'schtasks.exe' and '/Create' in c)
    assert '/SC' in create_call
    assert 'MINUTE' in create_call
    assert '/MO' in create_call
    assert '6' in create_call
    assert '/ST' in create_call
    assert '12:06' in create_call
    assert '/TN' in create_call
    assert 'MeteocatWallpaperGenerator' in create_call
    assert '/RL' in create_call
    assert 'HIGHEST' in create_call
    assert '/F' in create_call


def test_install_failure_exits(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(sys, 'platform', 'win32')
    monkeypatch.setattr('meteocat.windows_scheduler.which', lambda _prog: 'schtasks.exe')
    settings = _make_settings(tmp_path)
    monkeypatch.setattr('meteocat.windows_scheduler.settings', settings)
    monkeypatch.setattr('meteocat.windows_scheduler._run', lambda _args: FakeCompletedProcess(1, '', 'err'))
    _install_fake_datetime(monkeypatch, datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC))
    with pytest.raises(SystemExit):
        install()


def test_uninstall_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, 'platform', 'linux')
    uninstall()  # no-op, no raise


def test_uninstall_task_not_found(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, 'platform', 'win32')
    monkeypatch.setattr('meteocat.windows_scheduler.which', lambda _prog: 'schtasks.exe')
    monkeypatch.setattr(
        'meteocat.windows_scheduler._run',
        lambda _args: FakeCompletedProcess(1, '', 'cannot find the task'),
    )
    uninstall()  # graceful return


def test_uninstall_failure_exits(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, 'platform', 'win32')
    monkeypatch.setattr('meteocat.windows_scheduler.which', lambda _prog: 'schtasks.exe')
    monkeypatch.setattr(
        'meteocat.windows_scheduler._run',
        lambda _args: FakeCompletedProcess(1, '', 'some other error'),
    )
    with pytest.raises(SystemExit):
        uninstall()


def test_status_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, 'platform', 'linux')
    with pytest.raises(SystemExit):
        status()


def test_status_not_found(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, 'platform', 'win32')
    monkeypatch.setattr('meteocat.windows_scheduler.which', lambda _prog: 'schtasks.exe')
    monkeypatch.setattr(
        'meteocat.windows_scheduler._run',
        lambda _args: FakeCompletedProcess(1, '', 'not found'),
    )
    with pytest.raises(SystemExit):
        status()


def test_status_success(monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture) -> None:
    monkeypatch.setattr(sys, 'platform', 'win32')
    monkeypatch.setattr('meteocat.windows_scheduler.which', lambda _prog: 'schtasks.exe')
    monkeypatch.setattr(
        'meteocat.windows_scheduler._run',
        lambda _args: FakeCompletedProcess(0, 'task info\n', ''),
    )
    with caplog.at_level(logging.INFO):
        status()
    assert 'task info' in caplog.text
