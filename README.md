# sapa-wildlife

Field wildlife reference for the **Vietnam Mountain Marathon 100-miler** (161 km, 8,800 m,
around Sa Pa / Hoàng Liên National Park) — plus a small tool that pulls **iNaturalist
observations along your actual race line** so you know what you might spot, and when.

Two things live here:

- **`reference/sapa_wildlife_field_reference.csv`** — a hand-curated, run-usable list of
  birds, mammals, snakes, trees, flowers and more, each with field marks, habitat/elevation
  band, notability, and an honest `spot_chance` tuned to a runner moving at pace (not a
  patient birder). Snakes lead with venom status.
- **`inat_corridor.py`** — clips iNaturalist observations to a buffered corridor around a
  GPX route, so you get "what's on my trail" instead of "what's in the province".

## Quickstart (uv)

```bash
# zero-config: pull observations recorded in the Sa Pa bounding box (no GPX needed)
make bbox TAXON=birds

# the real thing: clip to your race GPX (from VMM registration)
make run GPX=vmm_100mi.gpx TAXON=birds BUFFER=2.0
```

`uv` handles the Python version and dependencies — no manual venv.

## Make targets

| target        | what it does |
|---------------|--------------|
| `make help`   | list targets |
| `make install`| create the venv + install deps (`uv sync`) |
| `make bbox`   | query the whole Sa Pa box — no GPX required |
| `make run`    | clip observations to a GPX corridor |
| `make lint` / `make fmt` | ruff |
| `make clean`  | delete generated CSVs |

Each run writes two files under `data/`: a raw `*_observations.csv` and a
`*_species.csv` summary sorted by frequency, with a **`sep_observations`** column
(the race is mid-September) and month histogram.

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
before reuse). The curated reference draws on Hoàng Liên National Park / NW-Vietnam
herpetofauna and biodiversity records. A GBIF variant of the corridor query (DOI-citable
occurrence downloads) is a straightforward endpoint swap.
