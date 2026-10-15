import os
import subprocess  # ruff: ignore[suspicious-subprocess-import] # nosec B404
import sys
from dataclasses import dataclass
from shutil import which

from meteocat.config import settings
from meteocat.logger import logger


def _systemd_available() -> bool:
    systemctl = which('systemctl')
    if systemctl is None or os.environ.get('XDG_RUNTIME_DIR') is None:
        return False
    result = subprocess.run(  # ruff: ignore[subprocess-without-shell-equals-true] # nosec B603
        [systemctl, '--user', 'show-environment'],
        capture_output=True,
        text=True,
    )  # nosec B603
    return result.returncode == 0


def _windows_scheduler_available() -> bool:
    return sys.platform == 'win32' and which('schtasks.exe') is not None


@dataclass(frozen=True)
class SchedulerResolution:
    scheduler: str
    source: str


def _resolve_scheduler_detailed() -> SchedulerResolution:
    if settings.scheduler in ('systemd', 'cron', 'windows'):
        return SchedulerResolution(settings.scheduler, 'from configuration')
    if _windows_scheduler_available():
        return SchedulerResolution('windows', 'auto-detected (Windows Task Scheduler available)')
    if _systemd_available():
        return SchedulerResolution('systemd', 'auto-detected (systemd user session available)')
    return SchedulerResolution('cron', 'auto-detected (systemd unavailable, fallback to cron)')


def _resolve_scheduler() -> str:
    return _resolve_scheduler_detailed().scheduler


def install() -> None:
    scheduler = _resolve_scheduler()
    logger.info('Scheduler: %s', scheduler)
    if scheduler == 'systemd':
        from meteocat.systemd import install as _install
    elif scheduler == 'windows':
        from meteocat.windows_scheduler import install as _install
    else:
        from meteocat.cron import install as _install
    _install()


def uninstall() -> None:
    from meteocat.cron import uninstall as _uninstall_cron
    from meteocat.systemd import uninstall as _uninstall_systemd
    from meteocat.windows_scheduler import uninstall as _uninstall_windows

    _uninstall_systemd()
    _uninstall_cron()
    _uninstall_windows()


def status() -> None:
    scheduler = _resolve_scheduler()
    logger.info('Scheduler: %s', scheduler)
    if scheduler == 'systemd':
        from meteocat.systemd import status as _status
    elif scheduler == 'windows':
        from meteocat.windows_scheduler import status as _status
    else:
        from meteocat.cron import status as _status
    _status()
