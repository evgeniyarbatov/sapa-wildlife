# sapa-wildlife --- iNaturalist corridor tool
UV     ?= uv
BUFFER ?= 1.5
OUT    ?= pages/data/vmm
GPX    ?=
TAXON  ?=

TAXON_ARG := $(if $(TAXON),--taxon $(TAXON),)

.DEFAULT_GOAL := help

.PHONY: help install run lint fmt clean

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | \
		awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-10s\033[0m %s\n", $$1, $$2}'

install: ## Create the venv and install deps with uv
	$(UV) sync

run: install ## Route corridor: make run GPX=vmm_100mi.gpx [TAXON=birds] [BUFFER=1.5]
	@test -n "$(GPX)" || { echo "Set GPX=path/to/route.gpx"; exit 1; }
	$(UV) run python scripts/inat_corridor.py --gpx "$(GPX)" --buffer $(BUFFER) $(TAXON_ARG) --out-prefix "$(OUT)"

lint: ## Lint with ruff
	$(UV) run ruff check .

fmt: ## Format with ruff
	$(UV) run ruff format .

clean: ## Remove generated outputs
	rm -rf pages/data *_observations.csv
