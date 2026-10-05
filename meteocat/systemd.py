import subprocess  # ruff: ignore[suspicious-subprocess-import] # nosec B404
import sys

from meteocat.config import settings
from meteocat.logging import logger


def _run(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, capture_output=True, text=True)  # ruff: ignore[subprocess-without-shell-equals-true] # nosec B603


def install() -> None:
    settings.systemd_user_dir.mkdir(parents=True, exist_ok=True)
    settings.working_directory.mkdir(parents=True, exist_ok=True)

    service_dst = settings.systemd_user_dir / f'{settings.service_name}.service'
    timer_dst = settings.systemd_user_dir / f'{settings.service_name}.timer'

    service_text = settings.service_template.replace('{{WORKING_DIRECTORY}}', str(settings.working_directory)).replace(
        '{{SERVICE_EXEC}}', settings.service_exec
    )
    service_dst.write_text(service_text)
    timer_dst.write_text(settings.timer_template)

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

    service_file = settings.systemd_user_dir / f'{settings.service_name}.service'
    if service_file.exists():
        logger.info(service_file.read_text())

    service_status = _run(
        ['systemctl', '--user', 'status', '--no-pager', '-n', '0', f'{settings.service_name}.service']
    )
    logger.info(service_status.stdout)

    service_status = _run(
        ['journalctl', '--user', '-u', f'{settings.service_name}.service', '--since', '6 minutes ago', '--no-pager']
    )
    logger.info(service_status.stdout)
