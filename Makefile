.PHONY: all test help install update install-service uninstall-service status check-dependencies generate-background generate-wallpaper logs clean

PROJECT_ROOT := $(shell dirname $(realpath $(firstword $(MAKEFILE_LIST))))
USER := $(shell whoami)

GREEN := \033[32m
CYAN := \033[36m
BOLD := \033[1m
RED := \033[31m
RESET := \033[0m

all: ## Default target (show help)
	@$(MAKE) help

test: ## Run tests
	@uv run pytest

help: ## Show this help message
	@printf "$(BOLD)Available targets:$(RESET)\n\n"
	@grep -E '^[a-zA-Z_-]+:.*## ' $(MAKEFILE_LIST) | awk -F': ## ' '{printf "\033[32m%-20s\033[36m%s\033[0m\n", $$1, $$2}'

install: ## Install Python dependencies
	@uv sync

update: ## Upgrade Python dependencies
	@uv sync --upgrade

install-service: ## Install systemd user service and timer
	@mkdir -p ~/.config/systemd/user
	@sed -e "s|{{WORKING_DIRECTORY}}|$(PROJECT_ROOT)|g" systemd/meteocat_wallpaper_generator.service.in > ~/.config/systemd/user/meteocat_wallpaper_generator.service
	@sed -e "s|{{WORKING_DIRECTORY}}|$(PROJECT_ROOT)|g" systemd/meteocat_wallpaper_generator.timer.in > ~/.config/systemd/user/meteocat_wallpaper_generator.timer
	@systemctl --user daemon-reload
	@systemctl --user enable meteocat_wallpaper_generator.timer
	@systemctl --user start meteocat_wallpaper_generator.timer

uninstall-service: ## Uninstall systemd user service and timer
	@systemctl --user stop meteocat_wallpaper_generator.timer
	@systemctl --user disable meteocat_wallpaper_generator.timer
	@rm -f ~/.config/systemd/user/meteocat_wallpaper_generator.service
	@rm -f ~/.config/systemd/user/meteocat_wallpaper_generator.timer
	@systemctl --user daemon-reload

status: ## Verify systemd timer status and generated files
	@printf "$(CYAN)=== Timer Status ===$(RESET)\n\n"
	@systemctl --user list-timers --no-pager | grep -q meteocat_wallpaper_generator.timer && printf "$(GREEN)Timer is active$(RESET)\n" || (printf "$(BOLD)Timer not found$(RESET)\n" && exit 1)
	@printf "$(BOLD)Next run:$(RESET) " && systemctl show meteocat_wallpaper_generator.timer --property=NextElapseUSecRealtime --value | awk '{if ($$1 != "" && $$1 != "0") { printf "%s", strftime("%Y-%m-%d %H:%M:%S", $$1/1000000); exit } } END { if (NR == 0 || $$1 == "" || $$1 == "0") printf "$(RED)not scheduled$(RESET)\n" }'
	@systemctl --user status --no-pager meteocat_wallpaper_generator.timer
	@printf "\n$(CYAN)=== Generated Files ===$(RESET)\n\n"
	@test -f background/background_4K.png && printf "$(GREEN)background/background_4K.png exists$(RESET)\n" || printf "$(RED)background/background_4K.png missing$(RESET)\n"
	@test -f output/wallpaper.png && (find output/wallpaper.png -mmin -6 >/dev/null 2>&1 && printf "$(GREEN)output/wallpaper.png is newer than 6 minutes$(RESET)\n" || printf "$(BOLD)WARNING: output/wallpaper.png is older than 6 minutes$(RESET)\n") || (printf "$(RED)output/wallpaper.png missing$(RESET)\n")

check-dependencies: ## Check for required system dependencies
	@uv run ./meteocat.py check-dependencies

generate-background: ## Generate the background map of Catalonia
	@uv run ./meteocat.py generate-background

generate-wallpaper: ## Generate a wallpaper with updated radar map
	@uv run ./meteocat.py generate-wallpaper

logs: ## Show journalctl logs for the meteocat service
	@journalctl --user -u meteocat_wallpaper_generator.service -n 20 --no-pager

clean: ## Remove output and background files but keep directories
	@rm -f output/*
	@rm -f background/*