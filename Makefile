.PHONY: all test help install update logs edit-global-config edit-user-config clean bump tag

PROJECT_ROOT := $(shell dirname $(realpath $(firstword $(MAKEFILE_LIST))))
USER := $(shell whoami)

VERSION := $(shell sed -n 's/^version = "\(.*\)"/\1/p' pyproject.toml)

GREEN := \033[32m
CYAN := \033[36m
BOLD := \033[1m
RED := \033[31m
RESET := \033[0m

EDITOR := $(shell if [ -n "$$EDITOR" ]; then echo $$EDITOR; elif command -v nano >/dev/null 2>&1; then echo nano; else echo vi; fi)

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

logs: ## Show journalctl logs for the meteocat service
	@journalctl --user -u meteocat_wallpaper_generator.service -n 20 --no-pager

BUMP ?= patch
bump: ## Bump version in pyproject.toml (BUMP=patch|minor|major)
	@uv run python scripts/bump.py $(BUMP)
	@uv lock

tag: ## Tag the current version as a release and push the tag
	@git tag -a v$(VERSION) -m "Release v$(VERSION)"
	@git push origin v$(VERSION)

edit-global-config: ## Edit the global config.yaml (/etc/meteocat/config.yaml)
	@$(EDITOR) /etc/meteocat/config.yaml

edit-user-config: ## Edit the user config.yaml (~/.local/share/meteocat/config.yaml)
	@$(EDITOR) ~/.local/share/meteocat/config.yaml

clean: ## Remove output and background files
	@rm -rf background
	@rm -rf wallpaper
