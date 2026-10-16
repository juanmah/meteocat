# Changelog

All notable changes to this project will be documented in this file.

## [1.1.1] - 2026-10-16

### Added
- `scripts/post_install.py`: post-install script that detects the desktop environment and installs the `gsettings` extra (`pygobject`) automatically for GNOME, Cinnamon, or MATE
- README installation instructions updated to run `uv run python scripts/post_install.py` after `uv sync`

## [1.1.0] - 2026-10-15

### Added
- Windows support. Scheduler and wallpaper handling

### Changed
- Updated README with Windows installation and usage instructions
- Refactored `pygobject` to optional `gsettings` extra dependency
- Improved scheduler reliability and error handling
- Enhanced wallpaper download and caching logic
- Updated CLI with minor improvements
- Updated configuration handling

### Fixed
- Multiple scheduler fixes and improvements
- Dependency resolution improvements

## [1.0.0] - 2026-10-14

### Added
- Initial release
- Radar image download and processing
- Wallpaper generation and setting
- Systemd service integration
- Cron scheduling support
- Configuration management
- CLI interface with Rich output
- Progress tracking
- Logging system