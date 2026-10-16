from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest

from meteocat.cron import _cron_entry, install, status, uninstall


@dataclass
class FakeCompletedProcess:
    returncode: int = 0
    stdout: str = ''
    stderr: str = ''


def _make_settings(tmp_path: Path) -> SimpleNamespace:
    return SimpleNamespace(
        working_directory=tmp_path / 'meteocat',
        service_exec='uv run --project /x meteocat',
    )


def test_cron_entry_no_dbus(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr('os.getuid', lambda: '1000')
    settings = SimpleNamespace(
        working_directory=Path('/nonexistent'),
        service_exec='uv run --project /x meteocat',
    )
    monkeypatch.setattr('meteocat.cron.settings', settings)
    monkeypatch.setattr('meteocat.cron._has_dbus', lambda: False)
    entry = _cron_entry('1000')
    assert '*/6 * * * *' in entry
    assert 'METEOCAT=1' in entry
    assert 'uv run --project /x meteocat wallpaper' in entry
    assert '>> /nonexistent/cron.log 2>&1' in entry
    assert 'DBUS_SESSION_BUS_ADDRESS' not in entry


def test_cron_entry_with_dbus(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr('os.getuid', lambda: '1000')
    settings = SimpleNamespace(
        working_directory=Path('/nonexistent'),
        service_exec='uv run --project /x meteocat',
    )
    monkeypatch.setattr('meteocat.cron.settings', settings)
    monkeypatch.setattr('meteocat.cron._has_dbus', lambda: True)
    entry = _cron_entry('1000')
    assert 'DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus' in entry


def test_install(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    settings = _make_settings(tmp_path)
    monkeypatch.setattr('meteocat.cron.settings', settings)
    monkeypatch.setattr('os.getuid', lambda: '1000')
    monkeypatch.setattr('meteocat.cron._has_dbus', lambda: False)
    calls: list[tuple] = []

    def fake_run(args: list[str], stdin_data: str | None = None) -> FakeCompletedProcess:
        calls.append((args, stdin_data))
        return FakeCompletedProcess(0, '', '')

    monkeypatch.setattr('meteocat.cron._run', fake_run)
    install()

    assert settings.working_directory.is_dir()
    write_calls = [c for c in calls if c[0] == ['crontab', '-']]
    assert len(write_calls) == 1
    content = write_calls[0][1]
    assert 'METEOCAT=1' in content
    assert '*/6 * * * *' in content


def test_install_entry_exists_noop(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    settings = _make_settings(tmp_path)
    monkeypatch.setattr('meteocat.cron.settings', settings)
    monkeypatch.setattr('os.getuid', lambda: '1000')
    monkeypatch.setattr('meteocat.cron._has_dbus', lambda: False)
    entry = _cron_entry('1000').strip()
    calls: list[tuple] = []

    def fake_run(args: list[str], stdin_data: str | None = None) -> FakeCompletedProcess:
        if args == ['crontab', '-l']:
            return FakeCompletedProcess(0, entry + '\n', '')
        calls.append((args, stdin_data))
        return FakeCompletedProcess(0, '', '')

    monkeypatch.setattr('meteocat.cron._run', fake_run)
    install()
    write_calls = [c for c in calls if c[0] == ['crontab', '-']]
    assert write_calls == []


def test_uninstall(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    settings = _make_settings(tmp_path)
    monkeypatch.setattr('meteocat.cron.settings', settings)
    monkeypatch.setattr('os.getuid', lambda: '1000')
    monkeypatch.setattr('meteocat.cron._has_dbus', lambda: False)
    entry = _cron_entry('1000')
    written: list[str] = []

    def fake_run(args: list[str], stdin_data: str | None = None) -> FakeCompletedProcess:
        if args == ['crontab', '-l']:
            return FakeCompletedProcess(0, entry, '')
        if args == ['crontab', '-']:
            written.append(stdin_data or '')
            return FakeCompletedProcess(0, '', '')
        return FakeCompletedProcess(0, '', '')

    monkeypatch.setattr('meteocat.cron._run', fake_run)
    uninstall()
    assert 'METEOCAT=1' not in written[0]


def test_uninstall_no_marker(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    settings = _make_settings(tmp_path)
    monkeypatch.setattr('meteocat.cron.settings', settings)
    monkeypatch.setattr('os.getuid', lambda: '1000')
    monkeypatch.setattr('meteocat.cron._has_dbus', lambda: False)
    monkeypatch.setattr('meteocat.cron._run', lambda _args: FakeCompletedProcess(0, 'other\n', ''))
    uninstall()  # no marker -> info + return


def test_status_no_marker_exits(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    settings = _make_settings(tmp_path)
    monkeypatch.setattr('meteocat.cron.settings', settings)
    monkeypatch.setattr('os.getuid', lambda: '1000')
    monkeypatch.setattr('meteocat.cron._has_dbus', lambda: False)
    monkeypatch.setattr('meteocat.cron._run', lambda _args: FakeCompletedProcess(0, '', ''))
    with pytest.raises(SystemExit):
        status()


def test_status_active_with_recent_log(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    import logging

    settings = _make_settings(tmp_path)
    settings.working_directory.mkdir(parents=True)
    monkeypatch.setattr('meteocat.cron.settings', settings)
    monkeypatch.setattr('os.getuid', lambda: '1000')
    monkeypatch.setattr('meteocat.cron._has_dbus', lambda: False)
    entry = _cron_entry('1000')
    now = datetime.now(UTC)
    log_line = now.strftime('%Y-%m-%d %H:%M:%S') + ' something happened\n'
    (settings.working_directory / 'cron.log').write_text(log_line)

    def fake_run(args: list[str], _stdin_data: str | None = None) -> FakeCompletedProcess:
        if args == ['crontab', '-l']:
            return FakeCompletedProcess(0, entry, '')
        return FakeCompletedProcess(0, '', '')

    monkeypatch.setattr('meteocat.cron._run', fake_run)
    with caplog.at_level(logging.INFO):
        status()
    assert 'Cron scheduler is active.' in caplog.text
