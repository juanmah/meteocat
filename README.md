# `meteo.cat` wallpaper generator

This script generates a wallpaper by fetching radar images and combining them with background maps of Catalonia, all sourced from meteo.cat. The wallpaper is then set as the desktop background.

## How it works

- Downloads the latest radar tiles from meteo.cat and assembles them into a single radar image.
- Overlays the radar image on top of a background map of Catalonia.
- Generates both light and dark wallpapers and sets them as the desktop background.

## Requirements

- Python 3.14 or higher
- uv
- GNOME: gsettings

## Installation

The project uses `uv` for dependency management. To set up the environment and install dependencies:

```console
> uv sync
```
This command will automatically create a virtual environment in the `.venv` directory if one doesn't exist, and then install the dependencies specified in `uv.lock` to ensure reproducible builds.

You can prefix your commands with `uv run`, e.g., `uv run meteocat`.

## Usage

To generate the wallpaper and set it as your desktop background, simply run:

```console
> uv run meteocat generate-wallpaper
```

### Commands

- `check-dependencies`: Checks if all required dependencies are installed.
- `generate-background`: Downloads and generates the 4K background map of Catalonia.
- `generate-wallpaper`: Generates the wallpaper with the latest radar data (primary command).

## Run periodically

To schedule this script to run every 6 minutes using a user systemd timer, you can use the Makefile:

```console
> make install-service
```

This will:

1. Install `meteocat_wallpaper_generator.service` and `meteocat_wallpaper_generator.timer` in `~/.config/systemd/user/`
2. Reload the user systemd daemon
3. Enable and start the timer

## Disclaimer

This script is provided "as is" without warranty of any kind, express or implied. Use it at your own risk.
