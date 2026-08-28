#!/usr/bin/env python3
"""
inat_corridor.py — pull iNaturalist observations that fall along a running route.

iNaturalist's public API has no polygon/linestring geo-filter, so the strategy is:
  1. Parse a GPX track into a list of (lat, lon) points.
  2. Build a buffered corridor around that line (reprojected to local UTM for
     honest metric distances), e.g. "everything within 1.5 km of my route".
  3. Query the route's bounding box from the iNat API (cursor-paginated, no 10k cap).
  4. Clip every returned observation to the corridor with shapely.
  5. Write a per-observation CSV and a species-summary CSV (with month histogram,
     so you can see what's actually seen in September).

Deps:  pip install requests shapely pyproj
Usage:
  python inat_corridor.py --gpx vmm_100mi.gpx --buffer 1.5 --taxon snakes --out-prefix vmm_snakes
  python inat_corridor.py --gpx vmm_100mi.gpx --buffer 1.5                 # all taxa
  python inat_corridor.py --bbox 22.25 103.70 22.42 103.90 --taxon reptiles  # no GPX, raw box

Notes:
  * quality_grade defaults to "research" and captive/cultivated records are excluded.
  * iNat OBSCURES coordinates for many threatened taxa (rare snakes, orchids, etc.) by
    randomising them within ~0.2 deg (~20 km). Those points won't sit truly on your line —
    the script flags them via `coords_obscured` so you can treat them as "in the region,
    not on the trail". Filtering strictly to the corridor will drop most obscured records.
"""

import argparse
import csv
import math
import os
import sys
import time
from collections import Counter, defaultdict

import requests
from pyproj import Transformer
from shapely.geometry import LineString, Point
from shapely.ops import transform as shp_transform

INAT = "https://api.inaturalist.org/v1/observations"
# Put your email in the UA — iNat asks for a way to contact heavy users.
USER_AGENT = "inat_corridor.py (personal trail-species reference; contact: you@example.com)"

# Common iNaturalist taxon IDs, for the --taxon convenience flag.
TAXA = {
    "snakes": 85553,      # Serpentes
    "reptiles": 26036,    # Reptilia
    "amphibians": 20978,  # Amphibia
    "birds": 3,           # Aves
    "mammals": 40151,     # Mammalia
    "insects": 47158,     # Insecta
    "plants": 47126,      # Plantae
    "fungi": 47170,       # Fungi
}
MONTHS = ["", "Jan", "Feb", "Mar", "Apr", "May", "Jun",
          "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


# ----------------------------------------------------------------------------- GPX

def parse_gpx(path):
    """Return [(lat, lon), ...] from a GPX file. Namespace-agnostic; handles both
    <trkpt> tracks and <rtept> routes. No gpxpy dependency."""
    import xml.etree.ElementTree as ET
    root = ET.parse(path).getroot()
    pts = []
    for tag in ("trkpt", "rtept", "wpt"):
        for el in root.iter():
            if el.tag.split("}")[-1] == tag:  # strip namespace
                try:
                    pts.append((float(el.attrib["lat"]), float(el.attrib["lon"])))
                except (KeyError, ValueError):
                    continue
        if pts:  # prefer track points; stop at the first tag that yields any
            break
    if not pts:
        sys.exit(f"No track/route points found in {path}")
    return pts


def utm_epsg(lat, lon):
    """EPSG code for the UTM zone containing (lat, lon)."""
    zone = int((lon + 180) // 6) + 1
    return (32600 if lat >= 0 else 32700) + zone


def build_corridor(coords, buffer_km):
    """Return (corridor_polygon_utm, to_utm_fn). Line reprojected to local UTM,
    buffered by buffer_km, so distances are real metres not degrees."""
    lat0, lon0 = coords[0]
    epsg = utm_epsg(lat0, lon0)
    to_utm = Transformer.from_crs(4326, epsg, always_xy=True).transform
    # shapely wants (x, y) = (lon, lat)
    line_wgs = LineString([(lon, lat) for lat, lon in coords])
    line_utm = shp_transform(to_utm, line_wgs)
    corridor = line_utm.buffer(buffer_km * 1000.0)
    return corridor, to_utm


def corridor_bbox(coords, buffer_km):
    """Padded lat/lon bounding box (sw_lat, sw_lon, ne_lat, ne_lon) around the route."""
    lats = [c[0] for c in coords]
    lons = [c[1] for c in coords]
    pad_lat = buffer_km / 111.0
    midlat = sum(lats) / len(lats)
    pad_lon = buffer_km / (111.0 * max(0.1, math.cos(math.radians(midlat))))
    return (min(lats) - pad_lat, min(lons) - pad_lon,
            max(lats) + pad_lat, max(lons) + pad_lon)


# ----------------------------------------------------------------------------- iNat

def iter_observations(bbox, taxon_id=None, quality_grade="research",
                      exclude_captive=True, per_page=200, pause=0.7, verbose=True):
    """Yield observation dicts inside bbox, cursor-paginated by id (no 10k cap)."""
    sw_lat, sw_lon, ne_lat, ne_lon = bbox
    params = {
        "swlat": sw_lat, "swlng": sw_lon, "nelat": ne_lat, "nelng": ne_lon,
        "quality_grade": quality_grade,
        "geo": "true", "geoprivacy": "open",   # ask for un-hidden coords where possible
        "per_page": per_page, "order_by": "id", "order": "asc",
    }
    if taxon_id:
        params["taxon_id"] = taxon_id
    if exclude_captive:
        params["captive"] = "false"

    session = requests.Session()
    session.headers["User-Agent"] = USER_AGENT
    id_above, fetched = 0, 0
    while True:
        params["id_above"] = id_above
        r = session.get(INAT, params=params, timeout=60)
        r.raise_for_status()
        results = r.json().get("results", [])
        if not results:
            break
        for obs in results:
            yield obs
        fetched += len(results)
        id_above = max(o["id"] for o in results)
        if verbose:
            print(f"  fetched {fetched} observations (last id {id_above})", file=sys.stderr)
        if len(results) < per_page:
            break
        time.sleep(pause)  # be a good API citizen


def obs_coords(obs):
    """(lat, lon) or None from an observation record."""
    geo = obs.get("geojson")
    if geo and geo.get("coordinates"):
        lon, lat = geo["coordinates"]
        return lat, lon
    loc = obs.get("location")
    if loc:
        try:
            lat, lon = map(float, loc.split(","))
            return lat, lon
        except ValueError:
            pass
    return None


def photo_url(obs, size="medium"):
    photos = obs.get("photos") or []
    if photos and photos[0].get("url"):
        return photos[0]["url"].replace("square", size)
    return ""


# ----------------------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser(description="Clip iNaturalist observations to a running route corridor.")
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--gpx", help="GPX file of the route")
    src.add_argument("--bbox", nargs=4, type=float, metavar=("SWLAT", "SWLON", "NELAT", "NELON"),
                     help="raw bounding box instead of a GPX corridor")
    ap.add_argument("--buffer", type=float, default=1.5, help="corridor half-width in km (default 1.5)")
    ap.add_argument("--taxon", choices=sorted(TAXA), help="restrict to a taxonomic group")
    ap.add_argument("--quality", default="research", choices=["research", "needs_id", "casual", "any"])
    ap.add_argument("--include-captive", action="store_true", help="keep captive/cultivated records")
    ap.add_argument("--out-prefix", default="inat_corridor", help="output filename prefix")
    args = ap.parse_args()

    taxon_id = TAXA.get(args.taxon)
    quality = None if args.quality == "any" else args.quality

    if args.gpx:
        coords = parse_gpx(args.gpx)
        print(f"Route: {len(coords)} points", file=sys.stderr)
        corridor, to_utm = build_corridor(coords, args.buffer)
        bbox = corridor_bbox(coords, args.buffer)
    else:
        bbox = tuple(args.bbox)
        corridor = to_utm = None
    print(f"Query bbox: {bbox}", file=sys.stderr)

    obs_rows, species = [], defaultdict(lambda: {
        "sci": "", "common": "", "group": "", "count": 0,
        "months": Counter(), "obscured": 0, "photo": "", "example": ""})

    kept = 0
    for obs in iter_observations(bbox, taxon_id=taxon_id,
                                 quality_grade=quality or "any",
                                 exclude_captive=not args.include_captive):
        c = obs_coords(obs)
        if not c:
            continue
        lat, lon = c
        obscured = bool(obs.get("obscured") or obs.get("taxon_geoprivacy") in ("obscured", "private"))

        # precise corridor clip (skip for obscured points — their coords are randomised)
        if corridor is not None and not obscured:
            x, y = to_utm(lon, lat)
            if not corridor.contains(Point(x, y)):
                continue

        taxon = obs.get("taxon") or {}
        tid = taxon.get("id", 0)
        sci = taxon.get("name", "")
        common = taxon.get("preferred_common_name", "") or ""
        group = taxon.get("iconic_taxon_name", "") or ""
        month = None
        if obs.get("observed_on"):
            try:
                month = int(obs["observed_on"][5:7])
            except (ValueError, IndexError):
                pass

        obs_rows.append([group, common, sci, f"{lat:.5f}", f"{lon:.5f}",
                         obs.get("observed_on") or "", "yes" if obscured else "no",
                         obs.get("uri", ""), photo_url(obs)])

        s = species[tid]
        s["sci"], s["common"], s["group"] = sci, common, group
        s["count"] += 1
        if month:
            s["months"][month] += 1
        if obscured:
            s["obscured"] += 1
        if not s["photo"]:
            s["photo"] = photo_url(obs)
        if not s["example"]:
            s["example"] = obs.get("uri", "")
        kept += 1

    print(f"Kept {kept} observations across {len(species)} species", file=sys.stderr)

    # ensure the output directory exists
    out_dir = os.path.dirname(args.out_prefix)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)

    # --- per-observation CSV
    obs_path = f"{args.out_prefix}_observations.csv"
    with open(obs_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["group", "common_name", "scientific_name", "lat", "lon",
                    "observed_on", "coords_obscured", "obs_url", "photo_url"])
        w.writerows(obs_rows)

    # --- species-summary CSV (the run-useful one)
    sum_path = f"{args.out_prefix}_species.csv"
    with open(sum_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["group", "common_name", "scientific_name", "observations",
                    "sep_observations", "peak_months", "coords_obscured",
                    "example_photo", "example_obs"])
        for s in sorted(species.values(), key=lambda d: -d["count"]):
            peak = ", ".join(MONTHS[m] for m, _ in s["months"].most_common(3))
            w.writerow([s["group"], s["common"], s["sci"], s["count"],
                        s["months"].get(9, 0), peak, s["obscured"],
                        s["photo"], s["example"]])

    print(f"Wrote {obs_path} and {sum_path}")


if __name__ == "__main__":
    main()
