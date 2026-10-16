import logging
import os
import shutil
import subprocess  # ruff: ignore[suspicious-subprocess-import] # nosec B404

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

_GSETTINGS_DESKTOPS = {'gnome', 'cinnamon', 'mate'}


def _detect_desktop() -> str | None:
    for env_var in ('XDG_CURRENT_DESKTOP', 'XDG_SESSION_DESKTOP', 'DESKTOP_SESSION'):
        value = os.environ.get(env_var)
        if not value:
            continue
        for token in value.split(':'):
            if token.strip().lower() in _GSETTINGS_DESKTOPS:
                return token.strip().lower()
    return None


def _run_sync(extra: str | None) -> None:
    uv = shutil.which('uv') or 'uv'
    command = [uv, 'sync']
    if extra is not None:
        command.extend(['--extra', extra])
    subprocess.run(command, check=True)  # ruff: ignore[subprocess-without-shell-equals-true] # nosec B603


def main() -> None:
    desktop = _detect_desktop()
    if desktop in _GSETTINGS_DESKTOPS:
        logger.info('Desktop environment "%s" detected: installing gsettings extra.', desktop)
        _run_sync('gsettings')
    else:
        logger.info('No gsettings-required desktop environment detected: syncing base dependencies.')
        _run_sync(None)


if __name__ == '__main__':
    main()
