import os
import pathlib
from osgeo import gdal, osr
import numpy as np
import pyproj as pp
import pytest
import vyperdatum.transformer as vtf
from vyperdatum.transformer import Transformer
from vyperdatum.drivers.npz import NPZ


def raster_wkt(raster_file: str):
    wkt = None
    if pathlib.Path(raster_file).suffix.lower() == ".npz":
        wkt = NPZ(raster_file).wkt()
    else:
        ds = gdal.Open(raster_file)
        srs = osr.SpatialReference(wkt=ds.GetProjection())
        wkt = srs.ExportToWkt()
        ds = None
    return wkt


@pytest.mark.parametrize("input_file, bench_file, func", [
    (r"C:\Users\mohammad.ashkezari\Documents\projects\vyperdatum\untrack\data\raster\Modeling_BC25L26L_20230919.tiff",
     r"C:\Users\mohammad.ashkezari\Documents\projects\vyperdatum\untrack\data\raster\BlueTopo_BC25L26L_20230919.tiff",
     "bluetopo")
    ])
def test_transform_bluetopo(input_file: str, bench_file: str, func: str):
    xform_file = globals()[func](input_file)
    gen_ds = gdal.Open(xform_file)
    target_ds = gdal.Open(bench_file)
    gen_band = np.nan_to_num(gen_ds.GetRasterBand(1).ReadAsArray())
    target_band = np.nan_to_num(target_ds.GetRasterBand(1).ReadAsArray())
    assert gen_ds.RasterCount == target_ds.RasterCount, "unexpected band counts"
    assert pytest.approx(gen_band.min(), 0.001) == target_band.min(), f"inconsistent min band value (gen_min: {gen_band.min()} vs target_min: {target_band.min()})"
    assert pytest.approx(gen_band.max(), 0.001) == target_band.max(), f"inconsistent max band value (gen_max: {gen_band.max()} vs target_max: {target_band.max()})"
    gen_band.flags.writeable = False
    target_band.flags.writeable = False
    # assert hash(gen_band) == hash(target_band), f"hash check failed ({hash(gen_band)} vs {hash(target_band)})"
    # assert gen_ds.GetRasterBand(1).Checksum() == target_ds.GetRasterBand(1).Checksum(), f"checksum failed ({gen_ds.GetRasterBand(1).Checksum()} vs {target_ds.GetRasterBand(1).Checksum()})"
    # assert pp.CRS(raster_wkt(bench_file)).equals(pp.CRS(raster_wkt(xform_file))), "inconsistent crs."
    gen_ds, target_ds = None, None
    gen_band, target_band = None, None



@pytest.mark.parametrize("input_file, output_file, crs_from, crs_to", [
    (r"C:\Users\mohammad.ashkezari\Documents\projects\vyperdatum\untrack\data\raster\00_test\Original\FL1701-TB-C_BLK-E-F_US4FL1ET_ellipsoidal_dem_b1.tif",
     r"C:\Users\mohammad.ashkezari\Documents\projects\vyperdatum\untrack\data\raster\00_test\Manual\FL1701-TB-C_BLK-E-F_US4FL1ET_ellipsoidal_dem_b1.tif",
     "EPSG:6346",
     "EPSG:6346+NOAA:98",
     ),
    (r"C:\Users\mohammad.ashkezari\Documents\projects\vyperdatum\untrack\data\raster\00_test\Original\ct1401_mllw_dem_1m.tif",
     r"C:\Users\mohammad.ashkezari\Documents\projects\vyperdatum\untrack\data\raster\00_test\Manual\ct1401_mllw_dem_1m.tif",
     "EPSG:26919",
     "EPSG:26919+NOAA:98",
     ),
    (r"C:\Users\mohammad.ashkezari\Documents\projects\vyperdatum\untrack\data\raster\00_test\Original\Modeling_BC25L26L_20230919.tiff",
     r"C:\Users\mohammad.ashkezari\Documents\projects\vyperdatum\untrack\data\raster\00_test\Manual\Modeling_BC25L26L_20230919.tiff",
     "EPSG:26914+NOAA:98",
     "EPSG:26914+EPSG:5703",
     ),
    (r"C:\Users\mohammad.ashkezari\Documents\projects\vyperdatum\untrack\data\raster\00_test\Original\MD1903-TB-C_US4MD1DD_ellipsoidal_dem.tif",
     r"C:\Users\mohammad.ashkezari\Documents\projects\vyperdatum\untrack\data\raster\00_test\Manual\MD1903-TB-C_US4MD1DD_ellipsoidal_dem.tif",
     "EPSG:6347",
     "EPSG:6347+NOAA:98",
     )    
    ])
def test_transform_raster(input_file: str, output_file: str, crs_from: str, crs_to: str):
    tf = Transformer(crs_from=crs_from,
                     crs_to=crs_to
                     )
    success = tf.transform_raster(input_file=input_file,
                                  output_file=output_file,
                                  overview=False,
                                  )
    assert success, "Raster transformation unsuccessful."


NAVD88_TO_MLLW = [{"crs_from": "EPSG:6318+EPSG:5703", "crs_to": "EPSG:6318+NOAA:98",
                   "v_shift": True}]


def _navd88_to_mllw_transformer():
    return Transformer(crs_from="EPSG:6318+EPSG:5703", crs_to="EPSG:6318+NOAA:98",
                       steps=NAVD88_TO_MLLW)


def _write_navd88_raster(fname: str):
    """Write a small constant-value NAD83(2011) + NAVD88 GeoTIFF near Norfolk, VA."""
    ds = gdal.GetDriverByName("GTiff").Create(fname, 20, 20, 1, gdal.GDT_Float32)
    ds.SetGeoTransform((-76.25, 0.005, 0, 37.20, 0, -0.005))
    srs = osr.SpatialReference()
    srs.SetFromUserInput("EPSG:6318+EPSG:5703")
    ds.SetProjection(srs.ExportToWkt())
    band = ds.GetRasterBand(1)
    band.WriteArray(np.full((20, 20), 5.0, dtype=np.float32))
    band.SetNoDataValue(-9999)
    ds = None


def test_transform_raster_unreadable_input_returns_false(tmp_path, caplog):
    """
    A failure before the temporary-file paths are assigned must return False and
    log the original error, rather than raising UnboundLocalError from the cleanup.
    """
    input_file = tmp_path / "not_a_raster.tif"
    input_file.write_text("not a raster")
    success = _navd88_to_mllw_transformer().transform_raster(str(input_file),
                                                             str(tmp_path / "out.tif"),
                                                             pre_post_checks=False,
                                                             vdatum_check=False)
    assert success is False
    assert "Exception in `transform_raster()`" in caplog.text


def test_transform_raster_success(tmp_path):
    input_file, output_file = str(tmp_path / "navd88.tif"), str(tmp_path / "mllw.tif")
    _write_navd88_raster(input_file)
    success = _navd88_to_mllw_transformer().transform_raster(input_file, output_file,
                                                             overview=False,
                                                             vdatum_check=False)
    assert success is True
    assert os.path.isfile(output_file)


def test_transform_raster_late_exception_returns_false(tmp_path, monkeypatch, caplog):
    """
    An exception raised after `success` was set to True (here, in the VDatum
    cross-validation) must make transform_raster return False.
    """
    def failing_vdatum_check(**kwargs):
        raise RuntimeError("simulated VDatum failure")

    monkeypatch.setattr(vtf, "vdatum_cross_validate", failing_vdatum_check)
    input_file, output_file = str(tmp_path / "navd88.tif"), str(tmp_path / "mllw.tif")
    _write_navd88_raster(input_file)
    success = _navd88_to_mllw_transformer().transform_raster(input_file, output_file,
                                                             overview=False,
                                                             vdatum_check=True)
    assert success is False
    assert "simulated VDatum failure" in caplog.text
