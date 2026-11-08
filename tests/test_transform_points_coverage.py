"""
Points outside the coverage of a transformation grid must not be returned unchanged
by `Transformer.transform_points()`, as if they had been transformed.

Uses the MLLW grid (nwldatum 4.7.0) from the vyperdatum grids (VYPER_GRIDS).
"""
import numpy as np
import pytest
import vyperdatum.transformer as vtf
from vyperdatum.transformer import Transformer


# NAD83(2011) 3D -> NAD83(2011) + MLLW at Norfolk, VA (in the MLLW grid), Kodiak, AK
# (a nodata cell in the MLLW grid) and central Kansas (no MLLW coverage).
COVERAGE_LON = np.array([-76.197, -152.40, -98.0])
COVERAGE_LAT = np.array([37.13, 57.79, 38.5])


def _ellipsoid_to_mllw_transformer():
    steps = [{"crs_from": "EPSG:6319", "crs_to": "EPSG:6318+NOAA:98", "v_shift": True}]
    return Transformer(crs_from="EPSG:6319", crs_to="EPSG:6318+NOAA:98", steps=steps)


def test_transform_points_outside_grid_coverage_returns_inf(caplog):
    """
    Points outside the coverage of the transformation grid must not be returned
    unchanged, as if they had been transformed. They come back as inf, and a
    warning gives their count. Points inside the coverage are unaffected.
    """
    success, xt, yt, zt = _ellipsoid_to_mllw_transformer().transform_points(
        COVERAGE_LON, COVERAGE_LAT, np.full(3, 5.0), always_xy=True)
    assert success is True
    assert pytest.approx(zt[0], abs=.01) == 42.23, "incorrect z inside the grid coverage."
    assert np.isinf(zt[1:]).all(), f"points outside the grid coverage were not flagged: {zt}"
    assert "2 of 3 point(s) could not be transformed" in caplog.text


def test_transform_points_allow_ballpark_passes_through():
    """
    With `allow_ballpark=True`, PROJ may fall back to a no-op ballpark operation,
    which returns points outside the grid coverage unchanged. This is why it is
    no longer the default.
    """
    success, _, _, zt = _ellipsoid_to_mllw_transformer().transform_points(
        COVERAGE_LON, COVERAGE_LAT, np.full(3, 5.0), always_xy=True, allow_ballpark=True)
    assert success is True
    assert pytest.approx(zt[0], abs=.01) == 42.23
    assert list(zt[1:]) == [5.0, 5.0]


def test_transform_points_inside_grid_coverage_logs_no_warning(caplog):
    success, _, _, zt = _ellipsoid_to_mllw_transformer().transform_points(
        COVERAGE_LON[:1], COVERAGE_LAT[:1], np.array([5.0]), always_xy=True)
    assert success is True
    assert np.isfinite(zt).all()
    assert "could not be transformed" not in caplog.text


def test_log_untransformed_points_ignores_non_finite_input():
    """Points that were already non-finite in the input are not counted as failures."""
    x, y = np.array([1.0, 2.0, 3.0]), np.array([1.0, 2.0, 3.0])
    z = np.array([0.0, np.nan, 0.0])
    zt = np.array([0.5, np.nan, np.inf])
    assert vtf._log_untransformed_points(x, y, z, x, y, zt) == 1
    assert vtf._log_untransformed_points(x, y, z, x, y, np.array([0.5, np.nan, 0.5])) == 0


@pytest.mark.parametrize("shape", [(1, 3), (3, 1), ()], ids=["1x3", "3x1", "scalar"])
def test_transform_points_outside_coverage_any_input_shape(shape, caplog):
    """
    The out-of-coverage check must work for any input shape (2-D arrays, numpy
    scalars) and must never turn a successful transformation into a failure.
    """
    if shape == ():
        lon, lat, h = np.float64(COVERAGE_LON[2]), np.float64(COVERAGE_LAT[2]), np.float64(5.0)
        expected_failed = 1
    else:
        lon, lat = COVERAGE_LON.reshape(shape), COVERAGE_LAT.reshape(shape)
        h = np.full(shape, 5.0)
        expected_failed = 2
    success, _, _, zt = _ellipsoid_to_mllw_transformer().transform_points(
        lon, lat, h, always_xy=True)
    assert success is True
    assert np.shape(zt) == shape
    assert np.isinf(zt).sum() == expected_failed
    assert f"{expected_failed} of " in caplog.text


def test_log_untransformed_points_never_raises():
    """Inputs the check can't handle are skipped rather than failing the transformation."""
    # x and y have shapes that can't be combined.
    x, y = [1.0, 2.0], [1.0, 2.0, 3.0]
    assert vtf._log_untransformed_points(x, y, [0.0], [1.0], [1.0], [1.0]) == 0
    # Sizes that broadcast but differ: the failed index is past the end of x.
    assert vtf._log_untransformed_points([1.0], [1.0], [0.0, 0.0, 0.0],
                                         [1.0], [1.0], [1.0, np.inf, np.inf]) == 0
