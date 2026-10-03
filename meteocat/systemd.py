import logging
import subprocess  # ruff: ignore[suspicious-subprocess-import] # nosec B404
import sys
from pathlib import Path

from meteocat.config import settings
from meteocat.logging import setup

setup()
logger = logging.getLogger('meteocat')


def _run(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, capture_output=True, text=True)  # ruff: ignore[subprocess-without-shell-equals-true] # nosec B603


def install() -> None:
    project_root = Path(__file__).resolve().parent.parent
    settings.systemd_user_dir.mkdir(parents=True, exist_ok=True)

    service_src = project_root / 'systemd' / f'{settings.service_name}.service.in'
    timer_src = project_root / 'systemd' / f'{settings.service_name}.timer.in'

    service_dst = settings.systemd_user_dir / f'{settings.service_name}.service'
    timer_dst = settings.systemd_user_dir / f'{settings.service_name}.timer'

    service_dst.write_text(service_src.read_text().replace('{{WORKING_DIRECTORY}}', str(project_root)))
    timer_dst.write_text(timer_src.read_text().replace('{{WORKING_DIRECTORY}}', str(project_root)))

    _run(['systemctl', '--user', 'daemon-reload'])
    _run(['systemctl', '--user', 'enable', f'{settings.service_name}.timer'])
    _run(['systemctl', '--user', 'start', f'{settings.service_name}.timer'])

    logger.info('Installed %s.service and %s.timer', settings.service_name, settings.service_name)


def uninstall() -> None:
    _run(['systemctl', '--user', 'stop', f'{settings.service_name}.timer'])
    _run(['systemctl', '--user', 'disable', f'{settings.service_name}.timer'])

    service_dst = settings.systemd_user_dir / f'{settings.service_name}.service'
    timer_dst = settings.systemd_user_dir / f'{settings.service_name}.timer'

    if service_dst.exists():
        service_dst.unlink()
    if timer_dst.exists():
        timer_dst.unlink()

    _run(['systemctl', '--user', 'daemon-reload'])

    logger.info('Uninstalled %s.service and %s.timer', settings.service_name, settings.service_name)


def status() -> None:
    result = _run(['systemctl', '--user', 'list-timers', '--no-pager'])
    logger.info(result.stdout)

    service_result = _run(['systemctl', '--user', 'status', '--no-pager', f'{settings.service_name}.timer'])
    logger.info(service_result.stdout)
    if service_result.returncode != 0:
        logger.error('Timer %s.timer is not active', settings.service_name)
        sys.exit(1)
