from __future__ import annotations

import sys
from dataclasses import FrozenInstanceError, dataclass

import pytest

from meteocat.scheduler import (
    SchedulerResolution,
    _resolve_scheduler,
    _resolve_scheduler_detailed,
    _systemd_available,
    _windows_scheduler_available,
    install,
    status,
    uninstall,
)


@dataclass
class FakeCompletedProcess:
    returncode: int = 0
    stdout: str = ''
    stderr: str = ''


def test_systemd_available_no_binary(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr('meteocat.scheduler.which', lambda _cmd: None)
    assert _systemd_available() is False


def test_systemd_available_no_runtime_dir(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr('meteocat.scheduler.which', lambda _cmd: '/usr/bin/systemctl')
    monkeypatch.setattr('meteocat.scheduler.os.environ.get', lambda _key, _default=None: None)
    assert _systemd_available() is False


def test_systemd_available_true(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr('meteocat.scheduler.which', lambda _cmd: '/usr/bin/systemctl')
    monkeypatch.setattr('meteocat.scheduler.os.environ.get', lambda _key, _default=None: '/run/user/1000/bus')
    monkeypatch.setattr('meteocat.scheduler.subprocess.run', lambda *_a, **_k: FakeCompletedProcess(0))
    assert _systemd_available() is True


def test_windows_scheduler_available(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, 'platform', 'win32')
    monkeypatch.setattr('meteocat.scheduler.which', lambda cmd: 'schtasks.exe' if cmd == 'schtasks.exe' else None)
    assert _windows_scheduler_available() is True


def test_windows_scheduler_available_not_win32(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, 'platform', 'linux')
    assert _windows_scheduler_available() is False


def test_scheduler_resolution_is_frozen_dataclass() -> None:
    r = SchedulerResolution(scheduler='cron', source='auto-detected')
    assert r.scheduler == 'cron'
    assert r.source == 'auto-detected'
    with pytest.raises(FrozenInstanceError):
        r.scheduler = 'x'


def test_resolve_scheduler_detailed_from_configuration(monkeypatch: pytest.MonkeyPatch) -> None:
    from meteocat.config import settings

    monkeypatch.setattr(settings, 'scheduler', 'systemd')
    assert _resolve_scheduler_detailed() == SchedulerResolution('systemd', 'from configuration')


def test_resolve_scheduler_detailed_systemd_auto(monkeypatch: pytest.MonkeyPatch) -> None:
    from meteocat.config import settings

    monkeypatch.setattr(settings, 'scheduler', 'auto')
    monkeypatch.setattr('meteocat.scheduler._systemd_available', lambda: True)
    monkeypatch.setattr(sys, 'platform', 'linux')
    assert _resolve_scheduler_detailed() == SchedulerResolution(
        'systemd', 'auto-detected (systemd user session available)'
    )


def test_resolve_scheduler_detailed_windows_auto(monkeypatch: pytest.MonkeyPatch) -> None:
    from meteocat.config import settings

    monkeypatch.setattr(settings, 'scheduler', 'auto')
    monkeypatch.setattr(sys, 'platform', 'win32')
    monkeypatch.setattr('meteocat.scheduler.which', lambda cmd: 'schtasks.exe' if cmd == 'schtasks.exe' else None)
    assert _resolve_scheduler_detailed() == SchedulerResolution(
        'windows', 'auto-detected (Windows Task Scheduler available)'
    )


def test_resolve_scheduler_detailed_cron_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    from meteocat.config import settings

    monkeypatch.setattr(settings, 'scheduler', 'auto')
    monkeypatch.setattr('meteocat.scheduler._systemd_available', lambda: False)
    monkeypatch.setattr(sys, 'platform', 'linux')
    assert _resolve_scheduler_detailed() == SchedulerResolution(
        'cron', 'auto-detected (systemd unavailable, fallback to cron)'
    )


def test_resolve_scheduler_returns_scheduler(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        'meteocat.scheduler._resolve_scheduler_detailed',
        lambda: SchedulerResolution('cron', 'x'),
    )
    assert _resolve_scheduler() == 'cron'


def test_install_dispatches_to_systemd(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []
    monkeypatch.setattr('meteocat.scheduler._resolve_scheduler', lambda: 'systemd')
    monkeypatch.setattr('meteocat.systemd.install', lambda: calls.append('systemd'))
    monkeypatch.setattr('meteocat.cron.install', lambda: calls.append('cron'))
    monkeypatch.setattr('meteocat.windows_scheduler.install', lambda: calls.append('windows'))
    install()
    assert calls == ['systemd']


def test_install_dispatches_to_cron(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []
    monkeypatch.setattr('meteocat.scheduler._resolve_scheduler', lambda: 'cron')
    monkeypatch.setattr('meteocat.cron.install', lambda: calls.append('cron'))
    install()
    assert calls == ['cron']


def test_install_dispatches_to_windows(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []
    monkeypatch.setattr('meteocat.scheduler._resolve_scheduler', lambda: 'windows')
    monkeypatch.setattr('meteocat.windows_scheduler.install', lambda: calls.append('windows'))
    install()
    assert calls == ['windows']


def test_uninstall_calls_all_backends(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []
    monkeypatch.setattr('meteocat.systemd.uninstall', lambda: calls.append('systemd'))
    monkeypatch.setattr('meteocat.cron.uninstall', lambda: calls.append('cron'))
    monkeypatch.setattr('meteocat.windows_scheduler.uninstall', lambda: calls.append('windows'))
    uninstall()
    assert calls == ['systemd', 'cron', 'windows']


def test_status_dispatches_to_systemd(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []
    monkeypatch.setattr('meteocat.scheduler._resolve_scheduler', lambda: 'systemd')
    monkeypatch.setattr('meteocat.systemd.status', lambda: calls.append('systemd'))
    status()
    assert calls == ['systemd']
