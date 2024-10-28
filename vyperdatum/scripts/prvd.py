import os
import pathlib
import glob
from osgeo import gdal
from vyperdatum.transformer import Transformer
from vyperdatum.utils.raster_utils import raster_metadata


def transform_19n(input_file):
    """
    Transform from NAD83(2011) / UTM zone 19N + MLLW to NAD83(2011) / UTM zone 19N + PRVD
    """
    # Currently for Puerto Rico there is no "NAD83(2011) + MLLW" CRS is defined in the database. 
    # The closest CRS I can find is "NAD83(2011) + MSL (GEOID12B_PRVI) height": NOAA:8283 = EPSG:6318+NOAA:5535


    warp_kwargs_vertical = {
                            "outputType": gdal.gdalconst.GDT_Float32,
                            "srcBands": [1],
                            "dstBands": [1],
                            "warpOptions": ["APPLY_VERTICAL_SHIFT=YES", "SAMPLE_GRID=YES", "SAMPLE_STEPS=ALL"],
                            "errorThreshold": 0,
                            }
    
    # Horizontal: NAD83(2011) / UTM zone 19N + MLLW  >>>>  NAD83(2011) + MLLW
    t1 = Transformer(crs_from="EPSG:26919+NOAA:5535",
                     crs_to="NOAA:8283", # NOAA:8283 = EPSG:6318+NOAA:5535
                     allow_ballpark=False
                     )
    out_file1 = pathlib.Path(input_file).with_stem("_01_" + pathlib.Path(input_file).stem)
    t1.transform_raster(input_file=input_file,
                        output_file=out_file1,
                        apply_vertical=False
                        )

    # Vertical: NAD83(2011) + MSL (GEOID12B_PRVI) height >>>>  NAD83(2011) + PRVD02
    t2 = Transformer(crs_from="NOAA:8283", # NOAA:8283 = EPSG:6318+NOAA:5535
                     crs_to="EPSG:9522", #"EPSG:9522 = EPSG:6318+EPSG:6641
                     allow_ballpark=False  # have to set it to True (results in noop). Setting crs_to=NOAA:8552 also results in noop
                     )
    out_file2 = pathlib.Path(input_file).with_stem("_02_" + pathlib.Path(input_file).stem)
    t2.transform_raster(input_file=out_file1,
                        output_file=out_file2,
                        apply_vertical=True,
                        warp_kwargs=warp_kwargs_vertical
                        )

    # Project: NAD83(2011)  >>>>  NAD83(2011) / UTM zone 19N
    t3 = Transformer(crs_from="EPSG:9522", #"EPSG:9522 = EPSG:6318+EPSG:6641
                     crs_to="EPSG:26919+EPSG:6641",
                     allow_ballpark=False
                     )
    # out_file3 = pathlib.Path(input_file).with_stem("_03_" + pathlib.Path(input_file).stem)
    p = pathlib.Path(input_file)
    xform_dir = os.path.join(r"C:\Users\mohammad.ashkezari\Documents\projects\vyperdatum\untrack\data\raster\PRVD\Manual", p.parent.parent.name, p.parent.name)
    os.makedirs(xform_dir, exist_ok=True)
    out_file3 = os.path.join(xform_dir, p.name)

    t3.transform_raster(input_file=out_file2,
                        output_file=out_file3,
                        apply_vertical=False
                        )

    os.remove(out_file1)
    os.remove(out_file2)
    return


if __name__ == "__main__":
    # files = get_tiff_files(r"W:\working_space\test_environments\sandbox\PBG19") + get_tiff_files(r"W:\working_space\test_environments\sandbox\PBG20")
    files = glob.glob(r"C:\Users\mohammad.ashkezari\Documents\projects\vyperdatum\untrack\data\raster\PRVD\Original\**\**\*.tiff", recursive=True)
    for i, input_file in enumerate(files):
        print(f"{i+1}/{len(files)}: {input_file}")
        transform_19n(input_file)
