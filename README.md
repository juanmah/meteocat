# `meteo.cat` wallpaper generator

This script generates a wallpaper by fetching radar images and combining them with background maps of Catalonia, all sourced from meteo.cat. The wallpaper is then set as the desktop background.

## How it works

- Downloads the latest radar images from meteo.cat.
- Combines the radar images into a single image.
- Overlays the radar image on top of a background map of Catalonia.
- Sets the resulting image as the desktop wallpaper.

## Requirements

- Python 3.12
- ImageMagick
- Inkscape
- GNOME: gsettings

## Installation

To install required packages, use:

```console
> pipenv install
```

Python virtualenv management tool [pipenv](https://pipenv.pypa.io/en/latest/) is required.

## Usage

To generate the wallpaper and set it as your desktop background, simply run:

```console
> ./meteocat.py
```

### Commands

- `check-dependencies`: Checks if all required dependencies are installed.
- `generate-background`: Downloads and generates the 4K background map of Catalonia.
- `generate-wallpaper`: Generates the wallpaper with the latest radar data (default command).

## Run periodically

To schedule this script to run every 6 minutes using systemd timer, you can follow these steps:

1. Create a `.service` file named `meteocat_wallpaper_generator.service` in the `/etc/systemd/system/` directory with the following contents:

    ```ini
    [Unit]
    Description=meteo.cat wallpaper generator

    [Service]
    Type=oneshot
    WorkingDirectory=/<<path>>/meteocat
    ExecStart=/usr/bin/pipenv run ./meteocat.py
    ```

    - The `WorkingDirectory` directive specifies the absolute path to the directory where the script is located.
    - The `ExecStart` directive specifies the absolute path to the script.

1. Create a `.timer` file named `meteocat_wallpaper_generator.timer` in the `/etc/systemd/system/` directory with the following contents:

    ```ini
    [Unit]
    Description=Run meteo.cat wallpaper generator script every 6 minutes

    [Timer]
    OnCalendar=*:0/6
    Persistent=true

    [Install]
    WantedBy=timers.target
    ```

    - The `OnCalendar` directive specifies the exact time when the service should be run. In this case, every 6 minutes.
    - The `Persistent` directive ensures that the service is run even if the system is restarted.

1. Reload the systemd daemon to recognize the new service and timer:

    ```console
    systemctl daemon-reload
    ```

1. Start the timer:

    ```console
    systemctl start meteocat_wallpaper_generator.timer
    ```

1. Enable the timer so that it starts automatically on boot:

    ```console
    systemctl enable meteocat_wallpaper_generator.timer
    ```

1. You can check the status of the timer using the following command:

    ```console
    systemctl list-timers --all
    ```

    This will show you all the timers that are currently active on your system. You should see your new timer listed there.

## Disclaimer

This script is provided "as is" without warranty of any kind, express or implied. Use it at your own risk.
