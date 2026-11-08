"""
Callers of `Transformer.transform_points()` must check its `success` flag.

On failure `transform_points()` returns `(False, None, None, None)`. These tests force
that failure and check that each caller stops with a clear error instead of writing
the `None` arrays (or partially transformed data) to its output.
"""
from types import SimpleNamespace

import h5py
import laspy
import numpy as np
import pyproj as pp
import pytest
import geopandas as gpd
from osgeo import gdal, osr
from shapely.geometry import Point

from vyperdatum.transformer import Transformer
from vyperdatum.drivers import vrbag
from vyperdatum.drivers.npz import NPZ
from vyperdatum.scripts.raster_arrays import RasterArrays

gdal.UseExceptions()

CRS_FROM = "EPSG:6318+EPSG:5703"
CRS_TO = "EPSG:6319"
STEPS = [{"crs_from": CRS_FROM, "crs_to": CRS_TO, "v_shift": True}]
FAILED = (False, None, None, None)


@pytest.fixture
def tf():
    return Transformer(crs_from=CRS_FROM, crs_to=CRS_TO, steps=STEPS)


@pytest.fixture
def failing_tf(tf, monkeypatch):
    """A transformer whose `transform_points()` always fails."""
    monkeypatch.setattr(Transformer, "transform_points", lambda self, *args, **kwargs: FAILED)
    return tf


def _points(n=5):
    x = np.linspace(39.0, 39.1, n)
    y = np.linspace(-76.5, -76.4, n)
    z = np.linspace(-5.0, -1.0, n)
    return x, y, z


# ----------------------------------------------------------------------------- npz
def _write_npz(path):
    x, y, z = _points()
    data = np.column_stack([x, y, z, np.full_like(x, 0.5)])
    minmax = np.array([np.min(data, 0), np.max(data, 0)])
    np.savez(path, wkt=np.array(pp.CRS(CRS_FROM).to_wkt()), data=data, minmax=minmax)
    return data


def test_npz_transform_raises_on_failure(failing_tf, tmp_path):
    """`NPZ.transform()` raises and leaves the file untouched."""
    fname = tmp_path / "in.npz"
    data = _write_npz(fname)
    nz = NPZ(input_file=str(fname))
    content = nz.content
    with pytest.raises(ValueError, match="NPZ transformation failed"):
        nz.transform(transformer_instance=failing_tf, vdatum_check=False)
    # The file must be closed, or Windows can't remove it (transform_npz() does on failure).
    assert content.fid is None, "NPZ.transform() left the npz file open"
    with np.load(fname) as saved:
        np.testing.assert_array_equal(saved["data"], data)


def test_transform_npz_removes_output_on_failure(failing_tf, tmp_path, caplog):
    """`transform_npz()` returns False and removes the output, like the other transform_*()."""
    input_file, output_file = tmp_path / "in.npz", tmp_path / "out" / "out.npz"
    _write_npz(input_file)
    success = failing_tf.transform_npz(input_file=str(input_file),
                                       output_file=str(output_file),
                                       pre_post_checks=False,
                                       vdatum_check=False)
    assert success is False
    assert not output_file.exists()
    assert "NPZ transformation failed" in caplog.text


# ----------------------------------------------------------------------------- laz
def test_transform_laz_removes_output_on_failure(failing_tf, tmp_path, caplog):
    input_file, output_file = tmp_path / "in.laz", tmp_path / "out.laz"
    x, y, z = _points()
    las = laspy.LasData(laspy.LasHeader(point_format=3, version="1.2"))
    las.header.scales = np.array([1e-7, 1e-7, 1e-3])
    las.x, las.y, las.z = x, y, z
    las.write(str(input_file))
    success = failing_tf.transform_laz(input_file=str(input_file),
                                       output_file=str(output_file),
                                       pre_post_checks=False,
                                       vdatum_check=False)
    assert success is False
    assert not output_file.exists()
    assert "LAZ transformation failed" in caplog.text


# ----------------------------------------------------------------------- geoparquet
def test_transform_geoparquet_fails_cleanly(failing_tf, tmp_path, caplog):
    input_file, output_file = tmp_path / "in.parquet", tmp_path / "out.parquet"
    x, y, z = _points()
    gdf = gpd.GeoDataFrame({"uncertainty": np.full_like(z, 0.5),
                            "classification": np.ones(len(z), dtype=np.int32)},
                           geometry=[Point(*p) for p in zip(y, x, z)],
                           crs=pp.CRS(CRS_FROM))
    gdf.to_parquet(input_file)
    success = failing_tf.transform_geoparquet(input_file=str(input_file),
                                              output_file=str(output_file),
                                              pre_post_checks=False,
                                              vdatum_check=False)
    assert success is False
    assert not output_file.exists()
    assert "GeoParquet transformation failed" in caplog.text


# --------------------------------------------------------------------------- vrbag
def _write_fake_vrbag(path, elevation):
    """
    Minimal HDF5 layout that `is_vr()`, `base_grid_point_transform()` and
    `subgrid_point_transform()` read. GDAL can't open it; tests stub `gdal.Open`
    and `get_subgrid_points()` where needed.
    """
    meta_dtype = np.dtype([("index", "<u4"), ("dimensions_x", "<u4"), ("dimensions_y", "<u4"),
                           ("resolution_x", "<f4"), ("resolution_y", "<f4"),
                           ("sw_corner_x", "<f4"), ("sw_corner_y", "<f4")])
    ref_dtype = np.dtype([("depth", "<f4"), ("depth_uncrt", "<f4")])
    with h5py.File(path, "w") as bag:
        root = bag.create_group("BAG_root")
        root.create_dataset("elevation", data=elevation)
        meta = np.zeros((1, 1), dtype=meta_dtype)
        meta[0, 0]["index"] = 0
        root.create_dataset("varres_metadata", data=meta)
        refs = np.zeros((1, 4), dtype=ref_dtype)
        refs["depth"] = [-1.0, -2.0, -3.0, -4.0]
        root.create_dataset("varres_refinements", data=refs)


def test_vrbag_base_grid_raises_on_failure(failing_tf, tmp_path, monkeypatch):
    fname = tmp_path / "fake_vr.bag"
    _write_fake_vrbag(fname, elevation=np.array([[-1.0, vrbag.vrb_enum.NDV_REF.value],
                                                 [-3.0, -4.0]], dtype=np.float32))
    fake_ds = SimpleNamespace(GetGeoTransform=lambda: (-76.5, 0.01, 0, 39.1, 0, -0.01))
    monkeypatch.setattr(vrbag, "gdal", SimpleNamespace(Open=lambda fname: fake_ds))
    with pytest.raises(ValueError, match="VR BAG base grid failed"):
        vrbag.base_grid_point_transform(fname=str(fname), tf=failing_tf,
                                        nodata_value=vrbag.vrb_enum.NDV_REF.value)


def test_vrbag_subgrid_raises_on_failure(failing_tf, monkeypatch):
    monkeypatch.setattr(vrbag, "get_subgrid_points", lambda fname, i, j: (0, *_points()))
    with pytest.raises(ValueError, match="VR BAG subgrid 1, 2 failed"):
        vrbag.single_subgrid_point_transform("unused.bag", 1, 2, failing_tf,
                                             vrbag.vrb_enum.NDV_REF.value)


def test_vrbag_subgrid_still_skips_unreadable_subgrid(failing_tf, monkeypatch):
    """A subgrid `get_subgrid_points()` couldn't read is still skipped, as before."""
    monkeypatch.setattr(vrbag, "get_subgrid_points", lambda fname, i, j: (None,) * 4)
    assert vrbag.single_subgrid_point_transform("unused.bag", 1, 2, failing_tf,
                                                vrbag.vrb_enum.NDV_REF.value) == (None, None)


def test_vrbag_transform_fails_on_subgrid_failure(failing_tf, tmp_path, monkeypatch, caplog):
    """A failed subgrid fails the whole VR BAG transform before anything is written."""
    fname = tmp_path / "fake_vr.bag"
    _write_fake_vrbag(fname, elevation=np.full((2, 2), -1.0, dtype=np.float32))
    monkeypatch.setattr(vrbag, "get_subgrid_points", lambda fname, i, j: (0, *_points(4)))
    assert vrbag.transform(fname=str(fname), tf=failing_tf) is False
    assert "VR BAG subgrid 0, 0 failed" in caplog.text
    with h5py.File(fname) as bag:
        depths = bag["BAG_root"]["varres_refinements"][0]["depth"]
    np.testing.assert_array_equal(depths, [-1.0, -2.0, -3.0, -4.0])


# ------------------------------------------------------------------- raster_arrays
def _write_tif(path, nx=4, ny=4):
    ds = gdal.GetDriverByName("GTiff").Create(str(path), nx, ny, 1, gdal.GDT_Float32)
    ds.SetGeoTransform((-76.5, 0.001, 0, 39.1, 0, -0.001))
    srs = osr.SpatialReference()
    srs.ImportFromEPSG(6318)
    ds.SetProjection(srs.ExportToWkt())
    band = ds.GetRasterBand(1)
    band.SetNoDataValue(-9999)
    band.WriteArray(np.linspace(-5, -1, nx * ny, dtype=np.float32).reshape(ny, nx))
    ds = None


@pytest.fixture
def raster(tmp_path):
    fname = tmp_path / "in.tif"
    _write_tif(fname)
    ra = RasterArrays(str(fname), backend="memory")
    yield ra
    ra.close()


def test_raster_arrays_bbox_raises_on_failure(failing_tf, raster, tmp_path):
    output_file = tmp_path / "out.parquet"
    with pytest.raises(ValueError, match="while computing the output extent"):
        raster.transform(failing_tf, output_file=str(output_file), chunk_size=4)
    assert not output_file.exists()


def test_raster_arrays_transform_raises_and_removes_partial_output(tf, raster, tmp_path,
                                                                   monkeypatch):
    """The second chunk fails after the first was written: no partial file is left behind."""
    calls = []

    def first_chunk_only(self, x, y, z, **kwargs):
        calls.append(len(x))
        return (True, x, y, z) if len(calls) == 1 else FAILED

    monkeypatch.setattr(Transformer, "transform_points", first_chunk_only)
    output_file = tmp_path / "out.parquet"
    with pytest.raises(ValueError, match=r"Point transformation failed for points 4:8"):
        raster.transform(tf, output_file=str(output_file), chunk_size=4,
                         set_extent_metadata=False)
    assert len(calls) == 2
    assert not output_file.exists()


def test_raster_arrays_transform_success(tf, raster, tmp_path, monkeypatch):
    """Sanity check of the same setup when every chunk succeeds."""
    monkeypatch.setattr(Transformer, "transform_points",
                        lambda self, x, y, z, **kwargs: (True, x, y, z))
    output_file = tmp_path / "out.parquet"
    assert raster.transform(tf, output_file=str(output_file), chunk_size=4) is True
    assert len(gpd.read_parquet(output_file)) == 16
