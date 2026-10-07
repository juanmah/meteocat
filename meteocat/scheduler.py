import os
import subprocess  # ruff: ignore[suspicious-subprocess-import] # nosec B404
from shutil import which

from meteocat.config import settings
from meteocat.logger import logger


def _systemd_available() -> bool:
    systemctl = which('systemctl')
    if systemctl is None or os.environ.get('XDG_RUNTIME_DIR') is None:
        return False
    result = subprocess.run(  # ruff: ignore[subprocess-without-shell-equals-true] # nosec B603 B604
        [systemctl, '--user', 'is-active', f'{settings.service_name}.timer'],
        capture_output=True,
        text=True,
    )  # nosec B603
    return result.stdout.strip() == 'active'


def _resolve_scheduler() -> str:
    if settings.scheduler in ('systemd', 'cron'):
        return settings.scheduler
    if _systemd_available():
        return 'systemd'
    return 'cron'


def install() -> None:
    scheduler = _resolve_scheduler()
    logger.info('Scheduler: %s', scheduler)
    if scheduler == 'systemd':
        from meteocat.systemd import install as _install
    else:
        from meteocat.cron import install as _install
    _install()


def uninstall() -> None:
    from meteocat.cron import uninstall as _uninstall_cron
    from meteocat.systemd import uninstall as _uninstall_systemd

    _uninstall_systemd()
    _uninstall_cron()


def status() -> None:
    scheduler = _resolve_scheduler()
    logger.info('Scheduler: %s', scheduler)
    if scheduler == 'systemd':
        from meteocat.systemd import status as _status
    else:
        from meteocat.cron import status as _status
    _status()
