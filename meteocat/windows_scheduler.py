import subprocess  # ruff: ignore[suspicious-subprocess-import] # nosec B404
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from shutil import which

from meteocat.config import settings
from meteocat.logger import logger

_TASK_NAME = 'MeteocatWallpaperGenerator'
_PROJECT_ROOT = Path(__file__).parent.parent


def _run(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, capture_output=True, text=True)  # ruff: ignore[subprocess-without-shell-equals-true] # nosec B603


def _windows_scheduler_available() -> bool:
    return sys.platform == 'win32' and which('schtasks.exe') is not None


def _next_valid_start_time() -> str:
    now = datetime.now(UTC).astimezone()
    # Round up to next 6-minute boundary
    minutes_to_add = 6 - (now.minute % 6)
    if minutes_to_add == 0:
        minutes_to_add = 6
    next_time = (now + timedelta(minutes=minutes_to_add)).replace(second=0, microsecond=0)
    return next_time.strftime('%H:%M')


def install() -> None:
    if not _windows_scheduler_available():
        logger.error('Windows Task Scheduler not available (schtasks.exe not found).')
        raise SystemExit(1)

    settings.working_directory.mkdir(parents=True, exist_ok=True)

    working_path = settings.working_directory.resolve()
    wrapper_path = working_path / 'meteocat_wallpaper.vbs'
    cmd = f'cmd /c cd /d {working_path} && {settings.service_exec} wallpaper'
    vbs_content = f'CreateObject("WScript.Shell").Run "{cmd}", 0, False\n'
    wrapper_path.write_text(vbs_content)

    # Run the VBScript hidden
    task_command = f'wscript.exe "{wrapper_path}"'

    start_time = _next_valid_start_time()

    result = _run(
        [
            'schtasks.exe',
            '/Create',
            '/SC',
            'MINUTE',
            '/MO',
            '6',
            '/ST',
            start_time,
            '/TN',
            _TASK_NAME,
            '/TR',
            task_command,
            '/RL',
            'HIGHEST',
            '/F',
        ]
    )

    if result.returncode != 0:
        logger.error(f'Failed to create scheduled task: {result.stderr}')
        raise SystemExit(1)

    logger.info(f'Installed Windows Task Scheduler task: {_TASK_NAME}')


def uninstall() -> None:
    if not _windows_scheduler_available():
        logger.info('Windows Task Scheduler not available.')
        return

    result = _run(
        [
            'schtasks.exe',
            '/Delete',
            '/TN',
            _TASK_NAME,
            '/F',
        ]
    )

    if result.returncode != 0:
        if 'cannot find' in result.stderr.lower() or 'not found' in result.stderr.lower():
            logger.info('No meteocat scheduled task found.')
            return
        logger.error(f'Failed to delete scheduled task: {result.stderr}')
        raise SystemExit(1)

    logger.info(f'Uninstalled Windows Task Scheduler task: {_TASK_NAME}')


def status() -> None:
    if not _windows_scheduler_available():
        logger.error('Windows Task Scheduler not available (schtasks.exe not found).')
        raise SystemExit(1)

    result = _run(
        [
            'schtasks.exe',
            '/Query',
            '/TN',
            _TASK_NAME,
            '/V',
            '/FO',
            'LIST',
        ]
    )

    if result.returncode != 0:
        logger.error(f'No meteocat scheduled task found: {result.stderr}')
        raise SystemExit(1)

    logger.info(result.stdout)
