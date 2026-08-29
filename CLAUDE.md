# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A tool that pulls iNaturalist observations along a race route (GPX corridor) for the Vietnam
Mountain Marathon 100-miler around Sa Pa / Hoàng Liên National Park, plus a static site
(published via GitHub Pages) that browses the results.

## Commands

```bash
make install                                    # uv sync
make run GPX=vmm_100mi.gpx [TAXON=birds] [BUFFER=1.5]   # clip to a GPX corridor
make lint                                       # ruff check
make fmt                                        # ruff format
make clean                                      # rm pages/data/ and stray *_observations.csv
```

`scripts/inat_corridor.py` also supports a raw `--bbox SWLAT SWLON NELAT NELON` query with no
GPX, run directly (not wired into a make target).

`TAXON` must be one of the keys in `TAXA` in `scripts/inat_corridor.py` (`snakes`, `reptiles`,
`amphibians`, `birds`, `mammals`, `insects`, `plants`, `fungi`). Omit it to pull all taxa.

There is no test suite.

## Architecture

`scripts/inat_corridor.py` is the entire data pipeline, run as a one-shot CLI (no server, no
scheduling):

1. Parse the GPX track into `(lat, lon)` points (`parse_gpx`).
2. Reproject to the local UTM zone and buffer the route line into a corridor polygon
   (`build_corridor`) — this keeps the buffer distance in real metres instead of degrees.
3. Query the iNaturalist API for the route's bounding box, cursor-paginated by observation id
   to bypass the API's 10k-result cap (`iter_observations`).
4. Clip each observation into the corridor with shapely; skip anything with obscured
   coordinates (iNat randomises location ~20km for many threatened taxa) since those can't be
   clipped honestly — they're flagged `coords_obscured` in the output instead of dropped.
5. Write `<prefix>_observations.csv` under `pages/data/`, one row per sighting.

`pages/data/vmm_observations.csv` is the committed, checked-in output for the race route —
`.gitignore` excludes everything else under `pages/data/` but whitelists this file
specifically, since it's consumed by the published site rather than being a throwaway build
artifact.

`pages/index.html` is a static, buildless single-page app: PapaParse loads
`data/vmm_observations.csv` (relative, so `pages/data/...` once served) client-side, then
`dedupeByName` collapses it to one row per species (keyed on scientific name, falling back to
common name), keeping only the most recent `observed_on`, before rendering into a
sortable/filterable table (`CONFIG` in the inline `<script>` drives columns, labels, and
per-column renderers).

GitHub Pages is configured as an Actions-built site (not branch/root), since branch-based
Pages can only serve the repo root or `/docs`. `.github/workflows/pages.yml` uploads the
`pages/` directory as the Pages artifact and deploys on every push to `main` that touches
`pages/**`.
