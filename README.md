# sapa-wildlife

A small tool that pulls **iNaturalist observations along your actual race line** for the
**Vietnam Mountain Marathon 100-miler** (161 km, 8,800 m, around Sa Pa / Hoàng Liên National
Park), so you know what you might spot, and when.

**`scripts/inat_corridor.py`** clips iNaturalist observations to a buffered corridor around a
GPX route, so you get "what's on my trail" instead of "what's in the province". **`pages/`**
holds the published site (GitHub Pages, deployed by `.github/workflows/pages.yml`) and the
CSV data it reads.

## Quickstart (uv)

```bash
make run GPX=vmm_100mi.gpx BUFFER=2.0
```

`uv` handles the Python version and dependencies — no manual venv.

## Make targets

| target        | what it does |
|---------------|--------------|
| `make help`   | list targets |
| `make install`| create the venv + install deps (`uv sync`) |
| `make run`    | clip observations to a GPX corridor |
| `make lint` / `make fmt` | ruff |
| `make clean`  | delete generated CSVs |

Each run writes a raw `*_observations.csv` under `pages/data/`, one row per sighting.

## How the corridor works

iNaturalist's public API has no polygon filter, so the script:

1. parses the GPX track,
2. buffers the line in local UTM (real metres) to a corridor,
3. queries the route's bounding box (cursor-paginated, no 10k cap),
4. clips every observation to the corridor with shapely.

## Caveats

- **Obscured coordinates.** iNaturalist randomises locations (~20 km) for many threatened
  taxa — exactly the rare snakes and orchids. Those are flagged `coords_obscured` and skipped
  from the strict clip; treat them as "in the region", not "on the trail".
- Set your email in the `USER_AGENT` string before a large pull — it's the polite thing.

## Data & attribution

Observation data from **iNaturalist** (contributor-licensed; check per-observation licences
before reuse). A GBIF variant of the corridor query (DOI-citable occurrence downloads) is a
straightforward endpoint swap.
