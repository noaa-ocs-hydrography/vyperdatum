import os
import glob
import pathlib
from vyperdatum.transformer import Transformer
from vyperdatum.utils.raster_utils import raster_metadata, raster_compress
from osgeo import gdal
import pyproj as pp


def transform(input_file, home_dir):
    options = {"options": ["s_coord_epoch=2010.0", "t_coord_epoch=2010.0"]}
    warp_kwargs_vertical = {
                            "outputType": gdal.gdalconst.GDT_Float32,
                            "srcBands": [1],
                            "dstBands": [1],
                            "warpOptions": ["APPLY_VERTICAL_SHIFT=YES", "SAMPLE_GRID=YES", "SAMPLE_STEPS=ALL"],
                            "errorThreshold": 0,
                            }

    t1 = Transformer(crs_from="EPSG:32619+EPSG:5866",
                     crs_to="EPSG:9755+EPSG:5866",
                     allow_ballpark=False
                     )
    out_file1 = pathlib.Path(input_file).with_stem("_01_" + pathlib.Path(input_file).stem)
    t1.transform_raster(input_file=input_file,
                        output_file=out_file1,
                        apply_vertical=False,
                        warp_kwargs=options
                        )

    t2 = Transformer(crs_from="EPSG:9755",   # must have been EPSG:9755+EPSG:5866, but bug in db/register
                     crs_to="EPSG:6318",     # must have been EPSG:6318+EPSG:5866, but bug in db/register
                     allow_ballpark=False
                     )
    out_file2 = pathlib.Path(input_file).with_stem("_02_" + pathlib.Path(input_file).stem)
    t2.transform_raster(input_file=out_file1,
                        output_file=out_file2,
                        apply_vertical=False,
                        warp_kwargs=options
                        )

    t3 = Transformer(crs_from="EPSG:6318+EPSG:5866",
                     crs_to="EPSG:26919+EPSG:5866",
                     allow_ballpark=False
                     )
    # out_file3 = pathlib.Path(input_file).with_stem("_03_" + pathlib.Path(input_file).stem)
    p = pathlib.Path(input_file)
    xform_dir = os.path.join(home_dir + r"\Manual", p.parent.name)
    os.makedirs(xform_dir, exist_ok=True)
    out_file3 = os.path.join(xform_dir, p.name)
    t3.transform_raster(input_file=out_file2,
                        output_file=out_file3,
                        apply_vertical=False,
                        )

    os.remove(out_file1)
    os.remove(out_file2)
    return out_file3


if __name__ == "__main__":
    # home_dir: path to the dir where the "Original" and "Manual" are stored
    home_dir = r"C:\Users\mohammad.ashkezari\Documents\projects\vyperdatum\untrack\data\raster\PBC\BAG"
    files = glob.glob(home_dir + r"\Original\**\*.bag", recursive=True)
    for i, input_file in enumerate(files):
        print(f"{i+1}/{len(files)}: {input_file}")
        raster_metadata(input_file, verbose=True)
        transformed_file = transform(input_file, home_dir)
