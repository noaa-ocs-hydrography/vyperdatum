import pytest
import os
import numpy as np
import pandas as pd
import pyproj as pp
import vyperdatum.transformer as vtf
from vyperdatum.transformer import Transformer
from vyperdatum.drivers.npz import NPZ
from vyperdatum.drivers.laz import LAZ
from vyperdatum.drivers.gparq import GeoParquet



def test_6349_to_6319():
    """
    Verify the a point on NAD83_2011_NAVD88 (EPSG:6349) is transformed
    correctly to NAD83_2011_3D (EPSG:6319).

    If network is off then a noop is used for the transform and NAVD88 to
    NAD83_2011_3D returns 0.0 leading to the test failure.
    """

    coords_lat_lon = (39, -76.5, 0)
    x, y, z = Transformer(crs_from=6349, crs_to=6319).transform_points(*coords_lat_lon)
    assert pytest.approx(x, abs=.01) == coords_lat_lon[0], "x coordinate should remain unchanged."
    assert pytest.approx(y, abs=.01) == coords_lat_lon[1], "y coordinate should remain unchanged."
    assert pytest.approx(z, abs=.01) == -33.29, "incorrect z coordinate transformation."


NAVD88_TO_NAD83_3D = [{"crs_from": "EPSG:6318+EPSG:5703", "crs_to": "EPSG:6319", "v_shift": True}]


def _navd88_transformer(steps=NAVD88_TO_NAD83_3D):
    return Transformer(crs_from="EPSG:6318+EPSG:5703", crs_to="EPSG:6319", steps=steps)


def test_transform_points_success():
    """A valid point transformation returns success and the transformed coordinates."""
    success, xt, yt, zt = _navd88_transformer().transform_points(np.array([39.0]),
                                                                 np.array([-76.5]),
                                                                 np.array([0.0]))
    assert success is True
    assert pytest.approx(xt[0], abs=.01) == 39
    assert pytest.approx(yt[0], abs=.01) == -76.5
    assert pytest.approx(zt[0], abs=.01) == -33.29


def test_transform_points_invalid_input_returns_none(caplog):
    """
    Input that fails before the outputs are assigned (scalars have no `.copy()`)
    must return (False, None, None, None) and log the original error, rather than
    raising UnboundLocalError.
    """
    result = _navd88_transformer().transform_points(39, -76.5, 0)
    assert result == (False, None, None, None)
    assert "Error while running the point transformation." in caplog.text
    assert "AttributeError" in caplog.text


def test_transform_points_failed_step_returns_none():
    """
    A failure in a later step must not leak the partially transformed
    arrays from the earlier steps.
    """
    tf = _navd88_transformer()
    # bypass the constructor's step validation to inject a failing second step
    tf.steps = NAVD88_TO_NAD83_3D + [{"crs_from": "EPSG:6319", "crs_to": "NOT:A_CRS",
                                      "v_shift": False}]
    result = tf.transform_points(np.array([39.0]), np.array([-76.5]), np.array([0.0]))
    assert result == (False, None, None, None)


def test_transform_points_failed_vdatum_check_returns_none(monkeypatch, tmp_path):
    """A failed VDatum cross-validation must return (False, None, None, None)."""
    monkeypatch.setattr(vtf, "vdatum_cross_validate", lambda **kwargs: (False, pd.DataFrame()))
    monkeypatch.chdir(tmp_path)
    result = _navd88_transformer().transform_points(np.array([39.0]),
                                                    np.array([-76.5]),
                                                    np.array([0.0]),
                                                    vdatum_check=True)
    assert result == (False, None, None, None)


def test_transform_missing_file_returns_false(caplog, tmp_path):
    """`transform()` logs the error and returns False for a missing input file."""
    success = _navd88_transformer().transform(input_file=str(tmp_path / "missing.tif"),
                                              output_file=str(tmp_path / "out.tif"))
    assert success is False
    assert "FileNotFoundError" in caplog.text


def test_transform_npz_cleanup_failure_returns_false(caplog, tmp_path, monkeypatch):
    """
    If the output of a failed transformation can't be removed (on Windows, while
    the file is still open), the method still returns False, logs the original
    error, and only warns about the leftover file instead of raising.
    """
    input_file = tmp_path / "not_an_npz.npz"
    input_file.write_bytes(b"not an npz file")

    def locked_remove(path):
        raise PermissionError(13, "The process cannot access the file", str(path))

    monkeypatch.setattr(vtf.os, "remove", locked_remove)
    success = _navd88_transformer().transform_npz(input_file=str(input_file),
                                                  output_file=str(tmp_path / "out.npz"),
                                                  pre_post_checks=False,
                                                  vdatum_check=False)
    assert success is False
    assert "Exception in `transform_npz()`" in caplog.text
    assert "Could not remove the output of the failed transformation" in caplog.text


@pytest.mark.parametrize("fname", [
    r"C:\Users\mohammad.ashkezari\Documents\projects\vyperdatum\untrack\data\point\npz\2018_NCMP_MA_19TCF2495_BareEarth_1mGrid_transformed.bruty.bruty.npz",
    r"C:\Users\mohammad.ashkezari\Documents\projects\vyperdatum\untrack\data\point\npz\W00405_MB_1m_MLLW_1of4_transformed.bruty.npz"
])
def test_npz(fname):
    npz = NPZ(fname)
    x, y, z, u = npz.xyzu()
    wkt = npz.wkt()
    mmx, mmy, mmz, mmu = npz.minmax()
    assert x.shape == y.shape == z.shape == u.shape, f"inconsistent data array dimensions in npz file: {fname}"  # noqa: E501
    assert mmx.shape == mmy.shape == mmz.shape == mmu.shape, f"inconsistent minmax array dimensions in npz file: {fname}"  # noqa: E501
    assert isinstance(wkt, str), f"unexpected wkt type in npz file: {fname}"


def test_transform_gparq():
    fname = r"C:\Users\mohammad.ashkezari\Documents\projects\vyperdatum\untrack\data\point\geoparquet\South_Locust_Point_&_Masonville_&_Ferry_Bar_&_Fairfield_2023_Elevation_MLLW_3ftx3ft.parquet"
    d, f = os.path.split(fname)
    output_file = os.path.join(d, f"transformed_{f}")
    crs_from = "EPSG:6347+NOAA:98"
    crs_to = "EPSG:6347+EPSG:5703"
    tf = Transformer(crs_from=crs_from, crs_to=crs_to)
    tf.transform(input_file=fname, output_file=output_file)
    gp = GeoParquet(output_file)
    auth_code = "+".join([":".join(pp.CRS(s).to_authority()) for s in pp.CRS(gp.wkt()).sub_crs_list])
    assert auth_code == crs_to, f"Incorrect WKT in the transformed geoparquet file: {output_file}"


def test_transform_npz():
    fname = r"C:\Users\mohammad.ashkezari\Documents\projects\vyperdatum\untrack\data\point\npz\W00405_MB_1m_MLLW_1of4_transformed.bruty.npz"
    d, f = os.path.split(fname)
    output_file = os.path.join(d, f"transformed_{f}")
    crs_from = "EPSG:26919"
    crs_to = "EPSG:26919+NOAA:5434"
    steps = ["EPSG:26919", "EPSG:6319", "EPSG:6318+NOAA:5434", "EPSG:26919+NOAA:5434"]
    tf = Transformer(crs_from=crs_from, crs_to=crs_to, steps=steps)
    tf.transform(input_file=fname, output_file=output_file)
    npz = NPZ(output_file)
    auth_code = "+".join([":".join(pp.CRS(s).to_authority()) for s in pp.CRS(npz.wkt()).sub_crs_list])
    assert auth_code == crs_to, f"Incorrect WKT in the transformed npz file: {output_file}"


def test_transform_laz():
    fname = r"C:\Users\mohammad.ashkezari\Documents\projects\vyperdatum\untrack\data\point\laz\ma2021_cent_east_Job1082403.laz"
    d, f = os.path.split(fname)
    output_file = os.path.join(d, f"transformed_{f}")
    crs_from = "EPSG:6348+EPSG:5703"
    crs_to = "EPSG:6348+NOAA:5320"
    steps = ["EPSG:6348+EPSG:5703", "EPSG:6318+EPSG:5703", "EPSG:6318+NOAA:5320", "EPSG:6348+NOAA:5320"]
    tf = Transformer(crs_from=crs_from, crs_to=crs_to, steps=steps)
    tf.transform(input_file=fname, output_file=output_file)
    lz = LAZ(output_file)
    auth_code = "+".join([":".join(pp.CRS(s).to_authority()) for s in pp.CRS(lz.wkt()).sub_crs_list])
    assert auth_code == crs_to, f"Incorrect WKT in the transformed laz file: {output_file}"


def test_transform_vrbag():
    fname = r"C:\Users\mohammad.ashkezari\Documents\projects\vyperdatum\untrack\data\point\vrbag\W00656_MB_VR_MLLW_5of5.bag"
    d, f = os.path.split(fname)
    output_file = os.path.join(d, f"transformed_{f}")
    crs_from = "EPSG:32617+EPSG:5866"
    crs_to = "EPSG:26917+EPSG:5866"
    steps = ["EPSG:32617+EPSG:5866", "EPSG:9755", "EPSG:6318", "EPSG:26917+EPSG:5866"]
    tf = Transformer(crs_from=crs_from, crs_to=crs_to, steps=steps)
    tf.transform(input_file=fname, output_file=output_file)

    auth_code = "+".join([":".join(pp.CRS(s).to_authority()) for s in pp.CRS(wkt).sub_crs_list])
    assert auth_code == crs_to, f"Incorrect WKT in the transformed vrbag file: {output_file}"