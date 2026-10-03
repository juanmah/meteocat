import subprocess  # ruff: ignore[suspicious-subprocess-import] # nosec B404
import sys
from pathlib import Path

from rich.console import Console

from meteocat.config import settings


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

    Console().print(f'Installed {settings.service_name}.service and {settings.service_name}.timer')


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

    Console().print(f'Uninstalled {settings.service_name}.service and {settings.service_name}.timer')


def status() -> None:
    console = Console()

    result = _run(['systemctl', '--user', 'list-timers', '--no-pager'])
    console.print(result.stdout)

    service_result = _run(['systemctl', '--user', 'status', '--no-pager', f'{settings.service_name}.timer'])
    console.print(service_result.stdout)
    if service_result.returncode != 0:
        console.print(f'Timer {settings.service_name}.timer is not active', style='red')
        sys.exit(1)
