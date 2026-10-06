import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import inat_corridor as ic
from shapely.geometry import Point

GPX = """<?xml version="1.0"?>
<gpx xmlns="http://www.topografix.com/GPX/1/1" version="1.1">
  <wpt lat="0" lon="0"/>
  <trk><trkseg>
    <trkpt lat="22.30" lon="103.80"/>
    <trkpt lat="22.31" lon="103.81"/>
    <trkpt lat="bad" lon="103.82"/>
  </trkseg></trk>
</gpx>
"""


class ParseGpxTest(unittest.TestCase):
    def test_prefers_track_points_and_skips_malformed(self):
        with tempfile.NamedTemporaryFile("w", suffix=".gpx", delete=False) as f:
            f.write(GPX)
        self.assertEqual(ic.parse_gpx(f.name), [(22.30, 103.80), (22.31, 103.81)])

    def test_exits_when_no_points(self):
        with tempfile.NamedTemporaryFile("w", suffix=".gpx", delete=False) as f:
            f.write('<gpx xmlns="http://www.topografix.com/GPX/1/1"/>')
        with self.assertRaises(SystemExit):
            ic.parse_gpx(f.name)


class CorridorTest(unittest.TestCase):
    def test_utm_epsg(self):
        self.assertEqual(ic.utm_epsg(22.3, 103.8), 32648)
        self.assertEqual(ic.utm_epsg(-33.9, 151.2), 32756)

    def test_corridor_buffer_is_metric(self):
        coords = [(22.30, 103.80), (22.30, 103.90)]
        corridor, to_utm = ic.build_corridor(coords, buffer_km=1.0)
        inside = Point(*to_utm(103.85, 22.305))  # ~0.55 km north of the line
        outside = Point(*to_utm(103.85, 22.32))  # ~2.2 km north of the line
        self.assertTrue(corridor.contains(inside))
        self.assertFalse(corridor.contains(outside))

    def test_bbox_pads_route_extent(self):
        sw_lat, sw_lon, ne_lat, ne_lon = ic.corridor_bbox([(22.3, 103.8), (22.4, 103.9)], 1.5)
        self.assertLess(sw_lat, 22.3)
        self.assertLess(sw_lon, 103.8)
        self.assertGreater(ne_lat, 22.4)
        self.assertGreater(ne_lon, 103.9)


class ObservationTest(unittest.TestCase):
    def test_coords_from_geojson(self):
        self.assertEqual(ic.obs_coords({"geojson": {"coordinates": [103.8, 22.3]}}), (22.3, 103.8))

    def test_coords_fall_back_to_location_string(self):
        self.assertEqual(ic.obs_coords({"location": "22.3,103.8"}), (22.3, 103.8))

    def test_coords_missing_or_malformed(self):
        self.assertIsNone(ic.obs_coords({}))
        self.assertIsNone(ic.obs_coords({"location": "nowhere"}))

    def test_photo_url_resizes_square(self):
        obs = {"photos": [{"url": "https://x/photos/1/square.jpg"}]}
        self.assertEqual(ic.photo_url(obs), "https://x/photos/1/large.jpg")
        self.assertEqual(ic.photo_url({}), "")


if __name__ == "__main__":
    unittest.main()
