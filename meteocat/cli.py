import logging
from enum import StrEnum

import typer

from meteocat.config import settings
from meteocat.logging import setup


class Scheduler(StrEnum):
    AUTO = 'auto'
    SYSTEMD = 'systemd'
    CRON = 'cron'


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


@app.command()
def generate_wallpaper() -> None:
    """Generate a wallpaper with an updated meteo.cat radar map."""
    from meteocat.wallpaper import generate_wallpaper

    generate_wallpaper()


_SCHEDULER_OPTION = typer.Option('--scheduler', help='Scheduler to use.')


@app.command()
def install_scheduler(
    scheduler: Scheduler = _SCHEDULER_OPTION,
) -> None:
    """Install the scheduler (systemd or cron) for the wallpaper generator."""
    from meteocat.scheduler import install as _install

    settings.scheduler = scheduler
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
