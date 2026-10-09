import logging
from datetime import UTC, datetime
from enum import StrEnum

import typer
import yaml
from typer.core import TyperGroup

from meteocat.config import settings
from meteocat.logger import logger, setup


class _OrderedTyperGroup(TyperGroup):
    def list_commands(self, ctx: typer.Context) -> list[str]:
        cmds = super().list_commands(ctx)
        if 'scheduler' in cmds:
            cmds.remove('scheduler')
            idx = next((i for i, c in enumerate(cmds) if c == 'dependencies'), len(cmds))
            cmds.insert(idx, 'scheduler')
        return cmds


class Scheduler(StrEnum):
    AUTO = 'auto'
    SYSTEMD = 'systemd'
    CRON = 'cron'


class DesktopEnvironment(StrEnum):
    AUTO = 'auto'
    GNOME = 'gnome'
    CINNAMON = 'cinnamon'
    MATE = 'mate'
    KDE = 'kde'
    XFCE = 'xfce'
    LXQT = 'lxqt'
    SWAY = 'sway'
    HYPRLAND = 'hyprland'
    I3 = 'i3'
    NONE = 'none'


app = typer.Typer(help='Set the desktop wallpaper by fetching radar images from meteo.cat.', cls=_OrderedTyperGroup)


@app.callback(invoke_without_command=True)
def main(ctx: typer.Context) -> None:
    level = getattr(logging, settings.log_level.upper(), logging.INFO)
    setup(level=level)
    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help())
        raise typer.Exit


@app.command()
def background() -> None:
    """Generate the background map of Catalonia from meteo.cat sources, and adapt it to 4K."""
    from meteocat.wallpaper import generate_background

    generate_background()


@app.command()
def radar() -> None:
    """Download the latest meteo.cat radar map."""
    from meteocat.radar import download_radar

    download_radar()


@app.command()
def wallpaper() -> None:
    """Generate a wallpaper with an updated meteo.cat radar map."""
    from meteocat.wallpaper import generate_wallpaper

    generate_wallpaper()


_DE_SET_ARGUMENT = typer.Argument(DesktopEnvironment.AUTO, help='Desktop environment to set.')


@app.command()
def desktop_environment(
    desktop_environment: DesktopEnvironment = _DE_SET_ARGUMENT,
) -> None:
    """Set the desktop environment."""
    settings.desktop_environment = desktop_environment
    from meteocat.config import save_config

    save_config('desktop_environment')
    typer.echo(f'Desktop environment set to: {desktop_environment}')


scheduler_app = typer.Typer(help='Manage the scheduler.')

_SCHEDULER_ARGUMENT = typer.Argument(..., help='Scheduler to use.')


@scheduler_app.callback(invoke_without_command=True)
def _scheduler_main(ctx: typer.Context) -> None:
    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help())
        raise typer.Exit


@scheduler_app.command('install')
def _install_scheduler(
    scheduler: Scheduler = _SCHEDULER_ARGUMENT,
) -> None:
    """Install the scheduler (systemd or cron)."""
    from meteocat.scheduler import install as _install

    settings.scheduler = scheduler
    from meteocat.config import save_config as _save

    _save('scheduler')
    _install()


@scheduler_app.command('uninstall')
def _uninstall_scheduler() -> None:
    """Uninstall the scheduler (systemd and cron)."""
    from meteocat.scheduler import uninstall as _uninstall

    _uninstall()


@scheduler_app.command('status')
def _status_scheduler() -> None:
    """Show the scheduler status."""
    from meteocat.scheduler import status as _status

    _status()


@app.command()
def dependencies() -> None:
    """Check for required system packages dependencies."""
    from meteocat.deps import check_dependencies

    check_dependencies(verbose=True)


@app.command(hidden=True)
def save_config() -> None:
    """Save the current config to the user config file."""
    from meteocat.config import save_config as _save

    _save()
    typer.echo('Config saved.')


@app.command(hidden=True)
def set_config(
    field: str = typer.Argument(..., help='Config field name.'),
    value: str = typer.Argument(..., help='Config field value.'),
) -> None:
    """Set a config field and save."""
    from meteocat.config import save_config as _save

    setattr(settings, field, yaml.safe_load(value))
    _save(field)
    logger.info(f'[bold]{field}[/bold] set to [bold]{getattr(settings, field)}[/bold]')


@app.command()
def video(
    from_: str = typer.Argument(
        lambda: datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0).isoformat(),
        help='Start datetime (ISO format, e.g. 2027-01-01T00:00).',
    ),
    to: str = typer.Argument(
        lambda: datetime.now(UTC).isoformat(),
        help='End datetime (ISO format, e.g. 2027-01-02T00:00).',
    ),
    profile: str = typer.Option('mkv', help='Video profile name from config.'),
    *,
    dark: bool = True,
    light: bool = True,
) -> None:
    """Generate a video from historical wallpaper frames."""
    from meteocat.video import create_video

    from_dt = datetime.fromisoformat(from_)
    to_dt = datetime.fromisoformat(to)
    create_video(from_dt, to_dt, profile_name=profile, light=light, dark=dark)


app.add_typer(scheduler_app, name='scheduler')
