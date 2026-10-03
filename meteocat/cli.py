import typer

from meteocat.deps import check_dependencies as _check_dependencies

app = typer.Typer(help='Set the desktop wallpaper by fetching radar images from meteo.cat.')


@app.callback(invoke_without_command=True)
def main(ctx: typer.Context) -> None:
    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help())
        raise typer.Exit


@app.command()
def check_dependencies() -> None:
    """Check for required system packages dependencies and give information if any are missing."""


_check_dependencies()


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
