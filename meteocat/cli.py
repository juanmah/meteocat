import logging
from enum import StrEnum

import typer

from meteocat.config import settings
from meteocat.logging import setup


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


app = typer.Typer(help='Set the desktop wallpaper by fetching radar images from meteo.cat.')


@app.callback(invoke_without_command=True)
def main(ctx: typer.Context) -> None:
    level = getattr(logging, settings.log_level.upper(), logging.INFO)
    setup(level=level)
    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help())
        raise typer.Exit


@app.command()
def check_dependencies() -> None:
    """Check for required system packages dependencies and give information if any are missing."""
    from meteocat.deps import check_dependencies

    check_dependencies(verbose=True)


@app.command()
def generate_background() -> None:
    """Generate the background map of Catalonia from meteo.cat sources, and adapt it to 4K."""
    from meteocat.wallpaper import generate_background

    generate_background()


_DE_OPTION = typer.Option('--desktop-environment', help='Desktop environment to use.')


@app.command()
def generate_wallpaper(
    desktop_environment: DesktopEnvironment = _DE_OPTION,
) -> None:
    """Generate a wallpaper with an updated meteo.cat radar map."""
    from meteocat.wallpaper import generate_wallpaper

    settings.desktop_environment = desktop_environment
    generate_wallpaper()


_DE_SET_ARGUMENT = typer.Argument(DesktopEnvironment.AUTO, help='Desktop environment to set.')


@app.command()
def set_de(
    desktop_environment: DesktopEnvironment = _DE_SET_ARGUMENT,
) -> None:
    """Set the desktop environment in the config."""
    settings.desktop_environment = desktop_environment
    from meteocat.config import save_config

    save_config('desktop_environment')
    typer.echo(f'Desktop environment set to: {desktop_environment}')


@app.command(hidden=True)
def save_config() -> None:
    """Save the current config to the user config file."""
    from meteocat.config import save_config as _save

    _save()
    typer.echo('Config saved.')


_SCHEDULER_OPTION = typer.Option('--scheduler', help='Scheduler to use.')


@app.command()
def install_scheduler(
    scheduler: Scheduler = _SCHEDULER_OPTION,
) -> None:
    """Install the scheduler (systemd or cron) for the wallpaper generator."""
    from meteocat.scheduler import install as _install

    settings.scheduler = scheduler
    from meteocat.config import save_config as _save

    _save('scheduler')
    _install()


@app.command()
def uninstall_scheduler() -> None:
    """Uninstall the scheduler (systemd and cron) for the wallpaper generator."""
    from meteocat.scheduler import uninstall as _uninstall

    _uninstall()


@app.command()
def scheduler_status() -> None:
    """Show the scheduler status."""
    from meteocat.scheduler import status as _status

    _status()
