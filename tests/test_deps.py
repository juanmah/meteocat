import logging

import pytest

from meteocat.config import settings
from meteocat.deps import (
    _check_binary,
    _check_de_dependencies,
    _check_pygobject,
    _check_scheduler_dependencies,
    _detect_distro,
    _get_package_name,
    _is_windows,
    check_dependencies,
)
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


def test_is_windows(monkeypatch: pytest.MonkeyPatch) -> None:
    import sys

    monkeypatch.setattr(sys, 'platform', 'win32')
    assert _is_windows() is True
    monkeypatch.setattr(sys, 'platform', 'linux')
    assert _is_windows() is False


def test_detect_distro_reads_os_release(monkeypatch: pytest.MonkeyPatch) -> None:
    import sys

    monkeypatch.setattr(sys, 'platform', 'linux')
    monkeypatch.setattr('meteocat.deps.Path.read_text', lambda _self: 'ID=ubuntu\nID_LIKE=debian\n')
    assert _detect_distro() == 'ubuntu'


def test_detect_distro_os_error_falls_back_to_arch(monkeypatch: pytest.MonkeyPatch) -> None:
    import sys

    monkeypatch.setattr(sys, 'platform', 'linux')
    monkeypatch.setattr('meteocat.deps.Path.read_text', lambda _self: (_ for _ in ()).throw(OSError()))
    assert _detect_distro() == 'arch'


def test_detect_distro_windows(monkeypatch: pytest.MonkeyPatch) -> None:
    import sys

    monkeypatch.setattr(sys, 'platform', 'win32')
    assert _detect_distro() == 'windows'


def test_get_package_name_distro_mapping(monkeypatch: pytest.MonkeyPatch) -> None:
    import sys

    monkeypatch.setattr(sys, 'platform', 'linux')
    monkeypatch.setattr('meteocat.deps.Path.read_text', lambda _self: 'ID=debian\n')
    assert _get_package_name('gsettings') == 'libglib2.0-bin'


def test_get_package_name_unknown_distro_falls_back_to_arch(monkeypatch: pytest.MonkeyPatch) -> None:
    import sys

    monkeypatch.setattr(sys, 'platform', 'linux')
    monkeypatch.setattr('meteocat.deps.Path.read_text', lambda _self: 'ID=distroless\n')
    assert _get_package_name('gsettings') == 'glib2'


def test_get_package_name_no_mapping_returns_binary(monkeypatch: pytest.MonkeyPatch) -> None:
    import sys

    monkeypatch.setattr(sys, 'platform', 'linux')
    monkeypatch.setattr('meteocat.deps.Path.read_text', lambda _self: 'ID=distroless\n')
    assert _get_package_name('nonexistent-binary') == 'nonexistent-binary'


def test_check_binary_found(monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture) -> None:
    monkeypatch.setattr('meteocat.deps.which', lambda binary: f'/usr/bin/{binary}')
    with caplog.at_level(logging.INFO, logger='meteocat'):
        assert _check_binary('gsettings', verbose=True) is True
    assert '[green]gsettings[/green] found' in caplog.text


def test_check_binary_not_found_non_fatal(monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture) -> None:
    monkeypatch.setattr('meteocat.deps.which', lambda _binary: None)
    with caplog.at_level(logging.ERROR, logger='meteocat'):
        assert _check_binary('gsettings', verbose=True) is False
    assert '[bold]gsettings[/bold] not found' in caplog.text


def test_check_binary_fatal(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr('meteocat.deps.which', lambda _binary: None)
    with pytest.raises(SystemExit):
        _check_binary('gsettings', fatal=True, verbose=True)


def test_check_pygobject_import_error(monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture) -> None:
    import sys

    class _FakeGi:
        def require_version(self, *_args: object, **_kwargs: object) -> None:
            msg = 'no gi'
            raise ImportError(msg)

    monkeypatch.setitem(sys.modules, 'gi', _FakeGi())
    monkeypatch.setitem(sys.modules, 'gi.repository', None)
    with caplog.at_level(logging.ERROR, logger='meteocat'):
        assert _check_pygobject() is False
    assert 'pygobject' in caplog.text


def test_check_de_dependencies_win32(monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture) -> None:
    import sys

    monkeypatch.setattr(sys, 'platform', 'win32')
    with caplog.at_level(logging.INFO, logger='meteocat'):
        _check_de_dependencies('windows', verbose=True)
    assert 'ctypes' in caplog.text


def test_check_de_dependencies_gnome(monkeypatch: pytest.MonkeyPatch) -> None:
    import sys

    monkeypatch.setattr(sys, 'platform', 'linux')
    monkeypatch.setattr('meteocat.deps.which', lambda binary: f'/usr/bin/{binary}')
    monkeypatch.setattr('meteocat.deps._check_pygobject', lambda **_kwargs: True)
    _check_de_dependencies('gnome', verbose=True)


def test_check_de_dependencies_kde_tool_map(monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture) -> None:
    import sys

    monkeypatch.setattr(sys, 'platform', 'linux')
    monkeypatch.setattr('meteocat.deps.which', lambda _binary: None)
    with caplog.at_level(logging.WARNING, logger='meteocat'):
        _check_de_dependencies('kde', verbose=True)
    assert 'qdbus not found for DE "kde". Some features may not work.' in caplog.text


def test_check_scheduler_dependencies_cron(monkeypatch: pytest.MonkeyPatch) -> None:
    import sys

    monkeypatch.setattr(sys, 'platform', 'linux')
    monkeypatch.setattr('meteocat.deps.which', lambda binary: f'/usr/bin/{binary}')
    _check_scheduler_dependencies('cron', verbose=True)


def test_check_scheduler_dependencies_systemd(monkeypatch: pytest.MonkeyPatch) -> None:
    import sys

    monkeypatch.setattr(sys, 'platform', 'linux')
    monkeypatch.setattr('meteocat.deps.which', lambda binary: f'/usr/bin/{binary}')
    _check_scheduler_dependencies('systemd', verbose=True)


def test_check_scheduler_dependencies_windows_off_platform_warning(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    import sys

    monkeypatch.setattr(sys, 'platform', 'linux')
    monkeypatch.setattr('meteocat.deps.which', lambda _binary: None)
    with caplog.at_level(logging.WARNING, logger='meteocat'):
        _check_scheduler_dependencies('windows', verbose=True)
    assert 'Windows scheduler selected but not on Windows platform.' in caplog.text
