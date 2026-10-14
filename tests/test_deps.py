import logging

import pytest

from meteocat.config import settings
from meteocat.deps import check_dependencies
from meteocat.scheduler import SchedulerResolution, _resolve_scheduler_detailed
from meteocat.wallpaper import DeResolution, _detect_de, _resolve_de_detailed


def _clear_de_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv('XDG_CURRENT_DESKTOP', raising=False)
    monkeypatch.delenv('XDG_SESSION_DESKTOP', raising=False)
    monkeypatch.delenv('DESKTOP_SESSION', raising=False)


def test_detect_de_env_var_source(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_de_env(monkeypatch)
    monkeypatch.setenv('XDG_CURRENT_DESKTOP', 'GNOME')
    assert _detect_de() == DeResolution('gnome', 'auto-detected via XDG_CURRENT_DESKTOP=GNOME')


def test_detect_de_fallback_process_source(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_de_env(monkeypatch)
    monkeypatch.setattr('meteocat.wallpaper.which', lambda prog: prog == 'plasmashell')
    assert _detect_de() == DeResolution('kde', 'auto-detected via plasmashell process')


def test_detect_de_no_desktop_source(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_de_env(monkeypatch)
    monkeypatch.setattr('meteocat.wallpaper.which', lambda _prog: None)
    assert _detect_de() == DeResolution('none', 'auto-detected (no desktop environment detected)')


def test_resolve_de_detailed_from_configuration(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, 'desktop_environment', 'gnome')
    assert _resolve_de_detailed() == DeResolution('gnome', 'from configuration')


def test_resolve_scheduler_detailed_from_configuration(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, 'scheduler', 'systemd')
    assert _resolve_scheduler_detailed() == SchedulerResolution('systemd', 'from configuration')


def test_resolve_scheduler_detailed_systemd_auto(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, 'scheduler', 'auto')
    monkeypatch.setattr('meteocat.scheduler._systemd_available', lambda: True)
    assert _resolve_scheduler_detailed() == SchedulerResolution(
        'systemd', 'auto-detected (systemd user session available)'
    )


def test_resolve_scheduler_detailed_cron_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, 'scheduler', 'auto')
    monkeypatch.setattr('meteocat.scheduler._systemd_available', lambda: False)
    assert _resolve_scheduler_detailed() == SchedulerResolution(
        'cron', 'auto-detected (systemd unavailable, fallback to cron)'
    )


def test_check_dependencies_verbose_found(caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, 'desktop_environment', 'gnome')
    monkeypatch.setattr(settings, 'scheduler', 'systemd')
    monkeypatch.setattr('meteocat.deps.which', lambda _binary: f'/usr/bin/{_binary}')
    with caplog.at_level(logging.INFO, logger='meteocat'):
        check_dependencies(verbose=True)
    assert 'Desktop environment: [bold]gnome[/bold] (from configuration)' in caplog.text
    assert 'Scheduler: [bold]systemd[/bold] (from configuration)' in caplog.text
    assert '[green]gsettings[/green] found (required for DE: gnome).' in caplog.text
    assert '[green]systemctl[/green] found (required for scheduler: systemd).' in caplog.text
    assert 'All dependencies checked.' in caplog.text


def test_check_dependencies_verbose_missing_fatal(
    caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, 'desktop_environment', 'gnome')
    monkeypatch.setattr(settings, 'scheduler', 'systemd')
    monkeypatch.setattr('meteocat.deps.which', lambda _binary: None)
    with caplog.at_level(logging.INFO, logger='meteocat'), pytest.raises(SystemExit):
        check_dependencies(verbose=True)
    assert '[bold]gsettings[/bold] not found (required for DE: gnome). Install' in caplog.text


def test_check_dependencies_non_gsettings_tool_warning(
    caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, 'desktop_environment', 'kde')
    monkeypatch.setattr(settings, 'scheduler', 'cron')
    monkeypatch.setattr('meteocat.deps.which', lambda _binary: None)
    with caplog.at_level(logging.INFO, logger='meteocat'), pytest.raises(SystemExit):
        check_dependencies(verbose=True)
    assert 'qdbus not found for DE "kde". Some features may not work.' in caplog.text
    assert '[bold]crontab[/bold] not found (required for scheduler: cron). Install' in caplog.text
