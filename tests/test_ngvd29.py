"""
NGVD29 <-> NAVD88 support (GitHub issue #45).

NGVD29 is usually paired with NAD27 horizontally, so these tests also cover
the NAD27 -> NAD83(2011) datum shift (NADCON5) that the automatic step
builder must insert before the vertical (VERTCON) shift.

The point transform tests require PROJ's NADCON5 and VERTCON grids
(``us_noaa_nadcon5_*.tif`` and ``us_noaa_vertcon*.tif``), either locally or
through the PROJ network (cdn.proj.org). They are skipped when the grids
cannot be used.
"""
import math
import numpy as np
import pyproj as pp
import pytest
from vyperdatum.pipeline import nwld_NAD832011_steps
from vyperdatum.transformer import Transformer
from vyperdatum.utils.crs_utils import crs_components

LAT, LON = 38.889389, -77.035603


def _grids_available() -> bool:
    """
    Actually run the two grid-based steps rather than asking PROJ whether they
    are instantiable: with PROJ_NETWORK=ON (set by vyperdatum) PROJ reports CDN
    grids as available even when the CDN cannot be reached.
    """
    try:
        for crs_from, crs_to in [("EPSG:4267", "EPSG:6318"),
                                 ("EPSG:6318+EPSG:7968", "EPSG:6318+EPSG:5703")]:
            t = pp.Transformer.from_crs(crs_from, crs_to, allow_ballpark=False, only_best=True)
            out = t.transform(LAT, LON, 0.0)
            if not all(math.isfinite(v) for v in out) or tuple(out) == (LAT, LON, 0.0):
                return False
        return True
    except Exception:
        return False


needs_grids = pytest.mark.skipif(not _grids_available(),
                                 reason="PROJ NADCON5/VERTCON grids are not available.")


@pytest.mark.parametrize("crs_from, crs_to, expected", [
    # NAD27 geographic + NGVD29 (ftUS) -> NAD83(2011) + NAVD88
    ("EPSG:4267+EPSG:5702", "EPSG:6318+EPSG:5703",
     [{"crs_from": "EPSG:4267", "crs_to": "EPSG:6318", "v_shift": False},
      {"crs_from": "EPSG:6318+EPSG:5702", "crs_to": "EPSG:6318+EPSG:7968", "v_shift": False},
      {"crs_from": "EPSG:6318+EPSG:7968", "crs_to": "EPSG:6318+EPSG:5703", "v_shift": True}]),
    # NAD27 / UTM 18N + NGVD29 (ftUS) -> NAD83 / UTM 18N + NAVD88
    ("EPSG:26718+EPSG:5702", "EPSG:26918+EPSG:5703",
     [{"crs_from": "EPSG:26718", "crs_to": "EPSG:6318", "v_shift": False},
      {"crs_from": "EPSG:6318+EPSG:5702", "crs_to": "EPSG:6318+EPSG:7968", "v_shift": False},
      {"crs_from": "EPSG:6318+EPSG:7968", "crs_to": "EPSG:6318+EPSG:5703", "v_shift": True},
      {"crs_from": "EPSG:6318", "crs_to": "EPSG:26918", "v_shift": False}]),
    # NAD83(2011) + NAVD88 -> NAD27 + NGVD29 (m)
    ("EPSG:6318+EPSG:5703", "EPSG:4267+EPSG:7968",
     [{"crs_from": "EPSG:6318+EPSG:5703", "crs_to": "EPSG:6318+EPSG:7968", "v_shift": True},
      {"crs_from": "EPSG:6318", "crs_to": "EPSG:4267", "v_shift": False}]),
    # NAD83(2011) + NAVD88 -> NAD27 / UTM 18N + NGVD29 (ftUS)
    ("EPSG:6318+EPSG:5703", "EPSG:26718+EPSG:5702",
     [{"crs_from": "EPSG:6318+EPSG:5703", "crs_to": "EPSG:6318+EPSG:5702", "v_shift": True},
      {"crs_from": "EPSG:6318", "crs_to": "EPSG:26718", "v_shift": False}]),
    ])
def test_ngvd29_steps(crs_from, crs_to, expected):
    steps = nwld_NAD832011_steps(*crs_components(crs_from), *crs_components(crs_to))
    assert steps == expected, (f"Unexpected transformation steps for {crs_from} --> {crs_to}:"
                               f" {steps}")


@pytest.mark.parametrize("crs_from, crs_to, expected", [
    ("EPSG:26919", "EPSG:26919+EPSG:5703",
     [{"crs_from": "EPSG:26919", "crs_to": "EPSG:4269", "v_shift": False},
      {"crs_from": "EPSG:6319", "crs_to": "EPSG:6318+EPSG:5703", "v_shift": True},
      {"crs_from": "EPSG:6318", "crs_to": "EPSG:26919", "v_shift": False}]),
    ("EPSG:6349", "EPSG:6318+NOAA:98",
     [{"crs_from": "EPSG:6318+EPSG:5703", "crs_to": "EPSG:6318+NOAA:98", "v_shift": True}]),
    ("EPSG:32618", "EPSG:6318+EPSG:5703",
     [{"crs_from": "EPSG:32618", "crs_to": "EPSG:9755", "v_shift": False},
      {"crs_from": "EPSG:9755", "crs_to": "EPSG:6318", "v_shift": False},
      {"crs_from": "EPSG:6319", "crs_to": "EPSG:6318+EPSG:5703", "v_shift": True}]),
    ])
def test_non_nad27_steps_unchanged(crs_from, crs_to, expected):
    """NAD83 and WGS84 inputs keep exactly the steps they had before NAD27 support."""
    steps = nwld_NAD832011_steps(*crs_components(crs_from), *crs_components(crs_to))
    assert steps == expected, (f"Unexpected transformation steps for {crs_from} --> {crs_to}:"
                               f" {steps}")


@needs_grids
def test_nad27_ngvd29_to_nad83_navd88_point():
    """
    Reference values from PROJ's own NAD27+NGVD29 -> NAD83(2011)+NAVD88 operation
    (NADCON5 + VERTCON), as reported in issue #45. PROJ's direct operation
    transforms (38.889389, -77.035603, 0) to
    (38.88950026013818, -77.03529973563386, -0.2402124582836045).
    """
    tf = Transformer(crs_from="EPSG:4267+EPSG:7968", crs_to="EPSG:6318+EPSG:5703")
    success, x, y, z = tf.transform_points(np.array([LAT]), np.array([LON]), np.array([0.0]))
    assert success, "NGVD29 --> NAVD88 point transformation failed."
    assert pytest.approx(x[0], abs=1e-7) == 38.88950026, "incorrect NAD27 --> NAD83(2011) lat."
    assert pytest.approx(y[0], abs=1e-7) == -77.03529974, "incorrect NAD27 --> NAD83(2011) lon."
    assert pytest.approx(z[0], abs=1e-3) == -0.2402, "incorrect NGVD29 --> NAVD88 height."


@needs_grids
@pytest.mark.parametrize("crs_to", ["EPSG:4267+EPSG:7968", "EPSG:4267+EPSG:5702"])
def test_navd88_to_ngvd29_matches_proj(crs_to):
    """Reverse direction, including the NGVD29 ftUS output unit, against PROJ directly."""
    crs_from = "EPSG:6318+EPSG:5703"
    ref = pp.Transformer.from_crs(crs_from, crs_to).transform(LAT, LON, 1.0)
    success, x, y, z = Transformer(crs_from=crs_from, crs_to=crs_to).transform_points(
        np.array([LAT]), np.array([LON]), np.array([1.0]))
    assert success, f"NAVD88 --> {crs_to} point transformation failed."
    assert pytest.approx(x[0], abs=1e-7) == ref[0]
    assert pytest.approx(y[0], abs=1e-7) == ref[1]
    assert pytest.approx(z[0], abs=1e-3) == ref[2]


@needs_grids
def test_ngvd29_navd88_round_trip():
    lat, lon, h = np.array([LAT]), np.array([LON]), np.array([10.0])
    fwd = Transformer(crs_from="EPSG:4267+EPSG:7968", crs_to="EPSG:6318+EPSG:5703")
    inv = Transformer(crs_from="EPSG:6318+EPSG:5703", crs_to="EPSG:4267+EPSG:7968")
    ok1, x1, y1, z1 = fwd.transform_points(lat, lon, h)
    ok2, x2, y2, z2 = inv.transform_points(x1, y1, z1)
    assert ok1 and ok2, "NGVD29 <--> NAVD88 round trip failed."
    assert pytest.approx(x2[0], abs=1e-6) == lat[0]
    assert pytest.approx(y2[0], abs=1e-6) == lon[0]
    assert pytest.approx(z2[0], abs=1e-3) == h[0]
