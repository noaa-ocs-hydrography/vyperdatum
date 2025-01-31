import pyproj as pp
from vyperdatum.utils import crs_utils as cu
import pytest


@pytest.mark.parametrize("crs_from, crs_to, vshift", [
    ("EPSG:6318", "EPSG:6319", False),
    ("EPSG:26919", "EPSG:6319", False),
    ("EPSG:26919", "EPSG:26919+EPSG:5703", True),
    ("EPSG:6318", "EPSG:9989", False),
    ("EPSG:6319", "EPSG:9989", False),
    ("EPSG:6319", "EPSG:4269", False),
    ("EPSG:6319", "EPSG:6318+NOAA:98", True),
    ("NOAA:1096", "NOAA:1098", True),
    ("EPSG:6318+EPSG:5703", "EPSG:9990+NOAA:101", True),
    ("EPSG:9755", "EPSG:6318", True),  # Is this a vertical shift? ellipsoids are not the same, therefore I suppose it should be considered as vertical shift
    ("EPSG:32618", "EPSG:9755", False),
    ])
def test_verical_shift(crs_from: str, crs_to: str, vshift: bool):
    ok = cu.vertical_shift(pp.CRS(crs_from), pp.CRS(crs_to)) == vshift
    assert ok, f"Vertical shift function for {crs_from} --> {crs_to} should be {not ok}"
