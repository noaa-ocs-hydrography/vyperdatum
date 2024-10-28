import os
import pathlib
from osgeo import gdal, osr
import numpy as np
import pyproj as pp
import pytest
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



def bluetopo(input_file):
    """
    Transform from NAD83 / UTM zone 14N + MLLW to NAD83(2011) / UTM zone 19N + NAVD88
    """

    warp_kwargs_vertical = {
                            "outputType": gdal.gdalconst.GDT_Float32,
                            "srcBands": [1],
                            "dstBands": [1],
                            "warpOptions": ["APPLY_VERTICAL_SHIFT=YES"],
                            "errorThreshold": 0,
                            }

    # Horizontal: NAD83 / UTM zone 14N + MLLW  height >>>>  NAD83(NSRS2007) + MLLW height
    t1 = Transformer(crs_from="EPSG:26914+NOAA:5498",
                     crs_to="EPSG:4759+NOAA:5498",
                     allow_ballpark=False
                     )
    print(f"t1: {t1.transformer.to_proj4()}\n{'-'*40}")
    out_file1 = pathlib.Path(input_file).with_stem("_01_4759_5498_" + pathlib.Path(input_file).stem)
    t1.transform_raster(input_file=input_file,
                        output_file=out_file1,
                        apply_vertical=False,
                        )

    # Vertical: NAD83(NSRS2007) + MLLW height >>>>  NAD83(NSRS2007) + NAVD88
    t2 = Transformer(crs_from="EPSG:4759+NOAA:5498",
                     crs_to="EPSG:4759+EPSG:5703",
                     allow_ballpark=False
                     )
    print(f"t2: {t2.transformer.to_proj4()}\n{'-'*40}")
    out_file2 = pathlib.Path(input_file).with_stem("_02_4759_5703_" + pathlib.Path(input_file).stem)
    t2.transform_raster(input_file=out_file1,
                        output_file=out_file2,
                        apply_vertical=True,
                        warp_kwargs=warp_kwargs_vertical
                        )

    # Project: NAD83(NSRS2007) + NAVD88  >>>>  NAD83 / UTM 14N + NAVD88
    t3 = Transformer(crs_from="EPSG:4759+EPSG:5703",
                     crs_to="EPSG:26914+EPSG:5703",
                     allow_ballpark=False
                     )
    print(f"t3: {t3.transformer.to_proj4()}\n{'-'*40}")
    out_file3 = pathlib.Path(input_file).with_stem("_03_6318_5703_" + pathlib.Path(input_file).stem)
    t3.transform_raster(input_file=out_file2,
                        output_file=out_file3,
                        apply_vertical=False
                        )
    return out_file3



def pbc_ma(input_file):
    warp_kwargs_vertical = {
                            "outputType": gdal.gdalconst.GDT_Float32,
                            "srcBands": [1],
                            "dstBands": [1],
                            "warpOptions": ["APPLY_VERTICAL_SHIFT=YES"],
                            "errorThreshold": 0,
                            }

    t1 = Transformer(crs_from="EPSG:6348",
                     crs_to="EPSG:6319",
                     allow_ballpark=False
                     )
    out_file1 = pathlib.Path(input_file).with_stem("_01_" + pathlib.Path(input_file).stem)
    t1.transform_raster(input_file=input_file,
                        output_file=out_file1,
                        apply_vertical=False,
                        )

    t2 = Transformer(crs_from="EPSG:6319",
                     crs_to="EPSG:6318+NOAA:5320",
                     allow_ballpark=False
                     )
    out_file2 = pathlib.Path(input_file).with_stem("_02_" + pathlib.Path(input_file).stem)
    t2.transform_raster(input_file=out_file1,
                        output_file=out_file2,
                        apply_vertical=True,
                        warp_kwargs=warp_kwargs_vertical
                        )

    t3 = Transformer(crs_from="EPSG:6318+NOAA:5320",
                     crs_to="EPSG:6348+NOAA:5320",
                     allow_ballpark=False
                     )
    out_file3 = pathlib.Path(input_file).with_stem("_03_" + pathlib.Path(input_file).stem)
    t3.transform_raster(input_file=out_file2,
                        output_file=out_file3,
                        apply_vertical=False,
                        )
    return out_file3


@pytest.mark.parametrize("input_file, bench_file, func", [
    (r"C:\Users\mohammad.ashkezari\Documents\projects\vyperdatum\untrack\data\raster\Modeling_BC25L26L_20230919.tiff",
     r"C:\Users\mohammad.ashkezari\Documents\projects\vyperdatum\untrack\data\raster\BlueTopo_BC25L26L_20230919.tiff",
     "bluetopo"),
    (r"C:\Users\mohammad.ashkezari\Documents\projects\vyperdatum\untrack\data\raster\PBC\clipped_MA2204-TB-N_TPU_3band_mosaic_tpu.tif",
     r"C:\Users\mohammad.ashkezari\Documents\projects\vyperdatum\untrack\data\raster\PBC\modeling\Modeling_Merged.tif",
     "pbc_ma"),
    ])
def test_transform_raster(input_file: str, bench_file: str, func: str):
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
