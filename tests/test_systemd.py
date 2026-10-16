from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace

import pytest

from meteocat.systemd import (
    SERVICE_TEMPLATE,
    TIMER_TEMPLATE,
    install,
    status,
    uninstall,
)


def test_templates_contain_sections() -> None:
    assert '[Unit]' in SERVICE_TEMPLATE
    assert '[Service]' in SERVICE_TEMPLATE
    assert '[Install]' in SERVICE_TEMPLATE
    assert '{{WORKING_DIRECTORY}}' in SERVICE_TEMPLATE
    assert '{{SERVICE_EXEC}}' in SERVICE_TEMPLATE
    assert '[Timer]' in TIMER_TEMPLATE
    assert 'OnCalendar=*:0/6' in TIMER_TEMPLATE


@dataclass
class FakeCompletedProcess:
    returncode: int = 0
    stdout: str = ''
    stderr: str = ''


def _make_settings(tmp_path: Path) -> SimpleNamespace:
    user_dir = tmp_path / 'systemd' / 'user'
    work_dir = tmp_path / 'meteocat'
    return SimpleNamespace(
        systemd_user_dir=user_dir,
        working_directory=work_dir,
        service_name='meteocat_wallpaper_generator',
        service_exec='uv run --project /x meteocat',
    )


def test_install(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    settings = _make_settings(tmp_path)
    monkeypatch.setattr('meteocat.systemd.settings', settings)
    calls: list[list[str]] = []

    def fake_run(args: list[str]) -> FakeCompletedProcess:
        calls.append(args)
        return FakeCompletedProcess(0, '', '')

    monkeypatch.setattr('meteocat.systemd._run', fake_run)
    install()

    assert (settings.systemd_user_dir / 'meteocat_wallpaper_generator.service').is_file()
    assert (settings.systemd_user_dir / 'meteocat_wallpaper_generator.timer').is_file()
    service_text = (settings.systemd_user_dir / 'meteocat_wallpaper_generator.service').read_text()
    assert str(settings.working_directory) in service_text
    assert settings.service_exec in service_text
    assert ['systemctl', '--user', 'daemon-reload'] in calls
    assert ['systemctl', '--user', 'enable', 'meteocat_wallpaper_generator.timer'] in calls
    assert ['systemctl', '--user', 'start', 'meteocat_wallpaper_generator.timer'] in calls


def test_install_mkdirs(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    settings = _make_settings(tmp_path)
    monkeypatch.setattr('meteocat.systemd.settings', settings)
    monkeypatch.setattr('meteocat.systemd._run', lambda _args: FakeCompletedProcess())
    install()
    assert settings.systemd_user_dir.is_dir()
    assert settings.working_directory.is_dir()


def test_uninstall_removes_files(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    settings = _make_settings(tmp_path)
    settings.systemd_user_dir.mkdir(parents=True)
    (settings.systemd_user_dir / 'meteocat_wallpaper_generator.service').write_text('svc')
    (settings.systemd_user_dir / 'meteocat_wallpaper_generator.timer').write_text('timer')
    monkeypatch.setattr('meteocat.systemd.settings', settings)
    calls: list[list[str]] = []
    monkeypatch.setattr('meteocat.systemd._run', lambda args: (calls.append(args), FakeCompletedProcess())[1])
    uninstall()
    assert not (settings.systemd_user_dir / 'meteocat_wallpaper_generator.service').exists()
    assert not (settings.systemd_user_dir / 'meteocat_wallpaper_generator.timer').exists()
    assert ['systemctl', '--user', 'stop', 'meteocat_wallpaper_generator.timer'] in calls
    assert ['systemctl', '--user', 'disable', 'meteocat_wallpaper_generator.timer'] in calls
    assert ['systemctl', '--user', 'daemon-reload'] in calls


def test_uninstall_missing_files_skipped(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    settings = _make_settings(tmp_path)
    settings.systemd_user_dir.mkdir(parents=True)
    monkeypatch.setattr('meteocat.systemd.settings', settings)
    monkeypatch.setattr('meteocat.systemd._run', lambda _args: FakeCompletedProcess())
    uninstall()  # must not raise when files are absent


def test_status_exits_when_timer_inactive(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    settings = _make_settings(tmp_path)
    monkeypatch.setattr('meteocat.systemd.settings', settings)

    def fake_run(args: list[str]) -> FakeCompletedProcess:
        if args[2] == 'list-timers':
            return FakeCompletedProcess(0, 'timers\n')
        if args[2] == 'status' and len(args) == 5 and args[4].endswith('.timer') and '-n' not in args:
            return FakeCompletedProcess(1, '')
        return FakeCompletedProcess(0, '')

    monkeypatch.setattr('meteocat.systemd._run', fake_run)
    with pytest.raises(SystemExit):
        status()


def test_status_success(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    settings = _make_settings(tmp_path)
    settings.systemd_user_dir.mkdir(parents=True)
    (settings.systemd_user_dir / 'meteocat_wallpaper_generator.service').write_text('[Unit]\n')
    monkeypatch.setattr('meteocat.systemd.settings', settings)

    def fake_run(args: list[str]) -> FakeCompletedProcess:
        if args[2] == 'list-timers':
            return FakeCompletedProcess(0, 'timers\n')
        if args[2] == 'status' and 'timer' in args and '-n' not in args:
            return FakeCompletedProcess(0, 'timer status\n')
        if args[2] == 'status' and '-n' in args:
            return FakeCompletedProcess(0, 'service status\n')
        if args[2] == 'journalctl':
            return FakeCompletedProcess(0, 'journal\n')
        return FakeCompletedProcess(0, '')

    monkeypatch.setattr('meteocat.systemd._run', fake_run)
    status()  # must not raise
