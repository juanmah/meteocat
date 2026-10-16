from __future__ import annotations

import logging
from types import SimpleNamespace
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import pytest

from typer.testing import CliRunner

from meteocat import __version__
from meteocat.cli import DesktopEnvironment, Scheduler, app

runner = CliRunner()


def test_scheduler_enum_values() -> None:
    assert Scheduler.AUTO == 'auto'
    assert Scheduler.SYSTEMD == 'systemd'
    assert Scheduler.CRON == 'cron'
    assert Scheduler.WINDOWS == 'windows'


def test_desktop_environment_enum_values() -> None:
    assert DesktopEnvironment.AUTO == 'auto'
    assert DesktopEnvironment.GNOME == 'gnome'
    assert DesktopEnvironment.NONE == 'none'


def test_command_ordering_scheduler_adjacent_to_dependencies() -> None:
    result = runner.invoke(app, ['--help'])
    assert result.exit_code == 0
    output = result.output
    # The ordered group places 'scheduler' immediately before 'dependencies'.
    sched_idx = output.index('scheduler')
    dep_idx = output.index('dependencies')
    assert sched_idx < dep_idx


def test_main_version() -> None:
    result = runner.invoke(app, ['--version'])
    assert result.exit_code == 0
    assert __version__ in result.output


def test_main_no_subcommand_shows_help() -> None:
    result = runner.invoke(app, [])
    assert result.exit_code == 0
    assert 'Set the desktop wallpaper' in result.output


def test_invalid_enum_exits() -> None:
    result = runner.invoke(app, ['desktop-environment', 'not-a-de'])
    assert result.exit_code == 2


def test_background(monkeypatch: pytest.MonkeyPatch) -> None:
    called: list[bool] = []
    monkeypatch.setattr('meteocat.wallpaper.generate_background', lambda: called.append(True))
    result = runner.invoke(app, ['background'])
    assert result.exit_code == 0
    assert called == [True]


def test_wallpaper(monkeypatch: pytest.MonkeyPatch) -> None:
    called: list[bool] = []
    monkeypatch.setattr('meteocat.wallpaper.generate_wallpaper', lambda: called.append(True))
    result = runner.invoke(app, ['wallpaper'])
    assert result.exit_code == 0
    assert called == [True]


def test_desktop_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_settings = SimpleNamespace(log_level='INFO', desktop_environment='auto')
    saved: list[str] = []
    monkeypatch.setattr('meteocat.cli.settings', fake_settings)
    monkeypatch.setattr('meteocat.config.save_config', lambda field: saved.append(field))
    result = runner.invoke(app, ['desktop-environment', 'gnome'])
    assert result.exit_code == 0
    assert fake_settings.desktop_environment == DesktopEnvironment.GNOME
    assert saved == ['desktop_environment']
    assert 'Desktop environment set to:' in result.output


def test_scheduler_install(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_settings = SimpleNamespace(log_level='INFO', scheduler='auto')
    saved: list[str] = []
    installed: list[bool] = []
    monkeypatch.setattr('meteocat.cli.settings', fake_settings)
    monkeypatch.setattr('meteocat.config.save_config', lambda field: saved.append(field))
    monkeypatch.setattr('meteocat.scheduler.install', lambda: installed.append(True))
    result = runner.invoke(app, ['scheduler', 'install', 'systemd'])
    assert result.exit_code == 0
    assert saved == ['scheduler']
    assert installed == [True]
    assert fake_settings.scheduler == Scheduler.SYSTEMD


def test_scheduler_uninstall(monkeypatch: pytest.MonkeyPatch) -> None:
    uninstalled: list[bool] = []
    monkeypatch.setattr('meteocat.scheduler.uninstall', lambda: uninstalled.append(True))
    result = runner.invoke(app, ['scheduler', 'uninstall'])
    assert result.exit_code == 0
    assert uninstalled == [True]


def test_scheduler_status(monkeypatch: pytest.MonkeyPatch) -> None:
    statused: list[bool] = []
    monkeypatch.setattr('meteocat.scheduler.status', lambda: statused.append(True))
    result = runner.invoke(app, ['scheduler', 'status'])
    assert result.exit_code == 0
    assert statused == [True]


def test_dependencies(monkeypatch: pytest.MonkeyPatch) -> None:
    called: list[bool] = []
    monkeypatch.setattr('meteocat.deps.check_dependencies', lambda verbose=False: called.append(verbose))
    result = runner.invoke(app, ['dependencies'])
    assert result.exit_code == 0
    assert called == [True]


def test_hidden_save_config(monkeypatch: pytest.MonkeyPatch) -> None:
    saved: list[str | None] = []
    monkeypatch.setattr('meteocat.config.save_config', lambda field=None: saved.append(field))
    result = runner.invoke(app, ['save-config'])
    assert result.exit_code == 0
    assert saved == [None]
    assert 'Config saved.' in result.output


def test_set_config(monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture) -> None:
    fake_settings = SimpleNamespace(log_level='INFO')
    saved: list[str] = []
    monkeypatch.setattr('meteocat.cli.settings', fake_settings)
    monkeypatch.setattr('meteocat.config.save_config', lambda field: saved.append(field))
    with caplog.at_level(logging.INFO):
        result = runner.invoke(app, ['set-config', 'log_level', '"DEBUG"'])
    assert result.exit_code == 0
    assert fake_settings.log_level == 'DEBUG'
    assert saved == ['log_level']
