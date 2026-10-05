# `meteo.cat` wallpaper generator

Generates a desktop wallpaper by fetching radar images from meteo.cat and overlaying them on a background map of Catalonia (also fetched from meteo.cat). Sets the wallpaper as the desktop background (GNOME).

## How it works

1. Downloads the latest radar tiles from meteo.cat and assembles them into a single radar image.
2. Overlays the radar image on top of a 4K background map of Catalonia.
3. Generates both light and dark wallpapers and sets them as the desktop background.

## Requirements

- Python 3.14 or higher
- [uv](https://docs.astral.sh/uv/)
- GNOME: `gsettings`

## Installation

```console
> uv sync
```

This creates a virtual environment in `.venv` and installs dependencies from `uv.lock`.

## Usage

```console
# Generate wallpaper and set as desktop background
> uv run meteocat generate-wallpaper

# Generate only the 4K background map of Catalonia
> uv run meteocat generate-background

# Check that all dependencies are installed
> uv run meteocat check-dependencies
```

### Commands

| Command | Description |
|---|---|
| `check-dependencies` | Checks if all required system dependencies are installed. |
| `generate-background` | Downloads and generates the 4K background map of Catalonia. |
| `generate-wallpaper` | Generates the wallpaper with the latest radar data (primary command). |
| `install-systemd` | Installs the systemd user service and timer. |
| `uninstall-systemd` | Uninstalls the systemd user service and timer. |
| `status-systemd` | Shows the systemd timer status. |

## Run periodically

Install the systemd user service and timer (runs every 6 minutes):

```console
> uv run meteocat install-systemd
```

This will:

1. Install `meteocat_wallpaper_generator.service` and `meteocat_wallpaper_generator.timer` in `~/.config/systemd/user/`
2. Reload the user systemd daemon
3. Enable and start the timer

## Configuration

Config files are loaded in order:

- Package default: `<package>/meteocat/config.yaml`
- System-wide: `/etc/meteocat/config.yaml`
- User: `~/.local/share/meteocat/config.yaml`

Edit with:

```console
> sudo make edit-global-config
> make edit-user-config
```

## Disclaimer

This script is provided "as is" without warranty of any kind, express or implied. Use it at your own risk.