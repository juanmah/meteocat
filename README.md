# `meteo.cat` wallpaper generator

Generates a desktop wallpaper by fetching radar images from meteo.cat and overlaying them on a background map of Catalonia (also fetched from meteo.cat). Sets the wallpaper as the desktop background (light and dark variants) on GNOME, Cinnamon, MATE, KDE, XFCE, LXQt, Sway, Hyprland, and i3.

## How it works

1. Downloads the latest radar tiles from meteo.cat and assembles them into a single radar image.
2. Overlays the radar image on top of a 4K background map of Catalonia.
3. Generates both light and dark wallpapers and sets them as the desktop background.

## Requirements

- Python 3.14 or higher
- [uv](https://docs.astral.sh/uv/)
- A supported desktop environment (see [Desktop environments](#desktop-environments))
- `systemd` user session or `cron` to run periodically

## Installation

### Option 1: From source (git clone)

```console
> git clone https://github.com/juanmah/meteocat.git
> cd meteocat
> uv sync
```

This creates a virtual environment in `.venv` and installs dependencies from `uv.lock`. Run commands with `uv run meteocat <command>`.

### Option 2: Arch Linux AUR

```console
> yay -S meteocat
```

## Usage

| Command | Description |
|---|---|
| `background` | Generate the 4K background map of Catalonia. |
| `wallpaper` | Generate a wallpaper with the latest radar map. |
| `desktop-environment` | Set the desktop environment for the wallpaper. |
| `scheduler` | Manage the periodic scheduler. |
| `dependencies` | Check required system packages. |


The `wallpaper` command generates the background map automatically if it is missing.

## Run periodically

Install the scheduler (runs every 6 minutes):

```console
> uv run meteocat scheduler install systemd
```

Replace `systemd` with `cron` if no systemd user session is available.

Other scheduler commands:

| Command | Description |
|---|---|
| `scheduler status` | Show the scheduler status. |
| `scheduler uninstall` | Uninstall the scheduler. |

## Desktop environments

The desktop environment is auto-detected from the current session. Supported environments: GNOME, Cinnamon, MATE, KDE, XFCE, LXQt, Sway, Hyprland, and i3.

Override the detection with:

```console
> uv run meteocat desktop-environment kde
```

## Configuration

Config files are loaded in order (last one wins):

- Package default: `<package>/meteocat/config.yaml`
- System-wide: `/etc/meteocat/config.yaml`
- User: `~/.local/share/meteocat/config.yaml`

The user config can override any setting. Example `~/.local/share/meteocat/config.yaml`:

```yaml
desktop_environment: kde
scheduler: systemd
log_level: INFO
```

Edit with:

```console
> sudo make edit-global-config
> make edit-user-config
```

Generated files (background maps and wallpapers) are written relative to the working directory (`~/.local/share/meteocat` by default when run via the scheduler).

## Disclaimer

This script is provided "as is" without warranty of any kind, express or implied. Use it at your own risk.
