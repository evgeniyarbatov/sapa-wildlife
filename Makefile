# sapa-wildlife --- iNaturalist corridor tool
UV     ?= uv
BUFFER ?= 1.5
OUT    ?= data/vmm
GPX    ?=
TAXON  ?=
BBOX   ?= 22.25 103.70 22.42 103.90

TAXON_ARG := $(if $(TAXON),--taxon $(TAXON),)

.DEFAULT_GOAL := help

.PHONY: help install run bbox lint fmt clean

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | \
		awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-10s\033[0m %s\n", $$1, $$2}'

install: ## Create the venv and install deps with uv
	$(UV) sync

run: install ## Route corridor: make run GPX=vmm_100mi.gpx [TAXON=birds] [BUFFER=1.5]
	@test -n "$(GPX)" || { echo "Set GPX=path/to/route.gpx  (or try 'make bbox' — no GPX needed)"; exit 1; }
	$(UV) run python inat_corridor.py --gpx "$(GPX)" --buffer $(BUFFER) $(TAXON_ARG) --out-prefix "$(OUT)"

bbox: install ## No GPX needed --- pull the whole Sa Pa box: make bbox [TAXON=reptiles]
	$(UV) run python inat_corridor.py --bbox $(BBOX) $(TAXON_ARG) --out-prefix "$(OUT)"

lint: ## Lint with ruff
	$(UV) run ruff check .

fmt: ## Format with ruff
	$(UV) run ruff format .

clean: ## Remove generated outputs
	rm -rf data *_observations.csv *_species.csv
