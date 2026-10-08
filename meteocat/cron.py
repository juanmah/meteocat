import os
import re
import subprocess  # ruff: ignore[suspicious-subprocess-import] # nosec B404
from datetime import UTC, datetime, timedelta
from pathlib import Path

from meteocat.config import settings
from meteocat.logger import logger

_METEOCAT_MARKER = 'METEOCAT=1'
_CRON_SCHEDULE = '*/6 * * * *'
_LOG_TIMESTAMP_RE = re.compile(r'^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})')


def _run(args: list[str], stdin_data: str | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, capture_output=True, text=True, input=stdin_data)  # ruff: ignore[subprocess-without-shell-equals-true] # nosec B603


def _read_crontab() -> str:
    result = _run(['crontab', '-l'])
    if result.returncode != 0:
        return ''
    return result.stdout


def _write_crontab(content: str) -> None:
    _run(['crontab', '-'], stdin_data=content)


def _has_dbus() -> bool:
    return Path(f'/run/user/{os.getuid()}/bus').exists()


def _cron_entry(uid: str) -> str:
    dbus_prefix = f'export DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/{uid}/bus && ' if _has_dbus() else ''
    return (
        f'{_CRON_SCHEDULE} {dbus_prefix}'
        f'METEOCAT=1 cd {settings.working_directory} && '
        f'{settings.service_exec} wallpaper '
        f'>> {settings.working_directory}/cron.log 2>&1\n'
    )


def install() -> None:
    settings.working_directory.mkdir(parents=True, exist_ok=True)

    uid = str(os.getuid())

    current = _read_crontab()
    lines = current.splitlines(keepends=True) if current else []

    if _cron_entry(uid).strip() in current.strip():
        logger.info('Crontab entry already exists.')
        return

    filtered = [line for line in lines if _METEOCAT_MARKER not in line]
    while filtered and filtered[-1].strip() == '':
        filtered.pop()

    new_content = ''.join(filtered)
    if new_content and not new_content.endswith('\n'):
        new_content += '\n'
    new_content += _cron_entry(uid)

    _write_crontab(new_content)
    logger.info('Installed crontab entry for meteocat.')


def uninstall() -> None:
    current = _read_crontab()
    if _METEOCAT_MARKER not in current:
        logger.info('No meteocat crontab entry found.')
        return

    lines = current.splitlines(keepends=True)
    filtered = [line for line in lines if _METEOCAT_MARKER not in line]
    while filtered and filtered[-1].strip() == '':
        filtered.pop()

    _write_crontab(''.join(filtered))
    logger.info('Removed meteocat crontab entry.')


def status() -> None:
    current = _read_crontab()
    if _METEOCAT_MARKER in current:
        for line in current.splitlines():
            if _METEOCAT_MARKER in line:
                logger.info(line)
        log_file = settings.working_directory / 'cron.log'
        if log_file.exists():
            cutoff = datetime.now(UTC) - timedelta(minutes=6)
            for line in log_file.read_text().splitlines():
                match = _LOG_TIMESTAMP_RE.match(line)
                if match:
                    try:
                        ts = datetime.strptime(match.group(1), '%Y-%m-%d %H:%M:%S').replace(tzinfo=UTC)
                        if ts >= cutoff:
                            logger.info(line)
                    except ValueError:
                        pass
        logger.info('Cron scheduler is active.')
    else:
        logger.error('No meteocat crontab entry found.')
        raise SystemExit(1)
