import os
import glob
import pathlib
from vyperdatum.transformer import Transformer
from vyperdatum.pipeline import Pipeline
from vyperdatum.utils.raster_utils import raster_metadata
from vyperdatum.utils.vdatum_rest_utils import vdatum_cross_validate_raster
from osgeo import gdal


def transform_NC(input_file):
    """
    3-Step transformation:
    EPSG:6347 >>> EPSG:6319
    EPSG:6319 >>> EPSG:6318+NOAA:5374
    EPSG:6318+NOAA:5374 >>> EPSG:6347+NOAA:5374
    """
    warp_kwargs_vertical = {
                            "outputType": gdal.gdalconst.GDT_Float32,
                            "srcBands": [1],
                            "dstBands": [1],
                            "warpOptions": ["APPLY_VERTICAL_SHIFT=YES"],
                            "errorThreshold": 0,
                            }

    t1 = Transformer(crs_from="EPSG:6347",
                     crs_to="EPSG:6319",
                     allow_ballpark=False
                     )
    out_file1 = pathlib.Path(input_file).with_stem("_01_" + pathlib.Path(input_file).stem)
    t1.transform_raster(input_file=input_file,
                        output_file=out_file1,
                        apply_vertical=False,
                        )

    t2 = Transformer(crs_from="EPSG:6319",
                     crs_to="EPSG:6318+NOAA:5374",
                     allow_ballpark=False
                     )
    out_file2 = pathlib.Path(input_file).with_stem("_02_" + pathlib.Path(input_file).stem)
    t2.transform_raster(input_file=out_file1,
                        output_file=out_file2,
                        apply_vertical=True,
                        warp_kwargs=warp_kwargs_vertical
                        )

    t3 = Transformer(crs_from="EPSG:6318+NOAA:5374",
                     crs_to="EPSG:6347+NOAA:5374",
                     allow_ballpark=False
                     )
    # out_file3 = pathlib.Path(input_file).with_stem("_03_" + pathlib.Path(input_file).stem)
    p = pathlib.Path(input_file)
    xform_dir = os.path.join(r"C:\Users\mohammad.ashkezari\Documents\projects\vyperdatum\untrack\data\raster\NC\Manual", p.parent.name)
    os.makedirs(xform_dir, exist_ok=True)
    out_file3 = os.path.join(xform_dir, p.name)
    t3.transform_raster(input_file=out_file2,
                        output_file=out_file3,
                        apply_vertical=False,
                        )

    os.remove(out_file1)
    os.remove(out_file2)
    return out_file3


def transform_VA_MD(input_file):
    """
    7-Step transformation:
    EPSG:6347 >>> EPSG:6319                           [NAD83(2011) (geographic 3D)]
    EPSG:6319 >>> EPSG:7912                           [ITRF2014 (geographic 3D)]
    EPSG:7912 >>> EPSG:9000+NOAA:5543                 [ITRF2014 + MSL (XGEOID20B_CONUSPAC) height]
    EPSG:9000+NOAA:5543 >>> EPSG:9000+NOAA:5197       [ITRF2014 + LMSL height]
    EPSG:9000+NOAA:5197 >>> EPSG:9000+NOAA:5200       [ITRF2014 + MLLW height]
    EPSG:9000+NOAA:5200 >>> EPSG:6318+NOAA:5200       [NAD83(2011) + MLLW height]
    EPSG:6318+NOAA:5200 >>> EPSG:6347+NOAA:5200       [NAD83(2011) / UTM 18N + MLLW height]
    """
    options = {"options": ["s_coord_epoch=2010.0", "t_coord_epoch=2010.0"]}
    warp_kwargs_vertical = {
                            "outputType": gdal.gdalconst.GDT_Float32,
                            "srcBands": [1],
                            "dstBands": [1],
                            "warpOptions": ["APPLY_VERTICAL_SHIFT=YES", "SAMPLE_GRID=YES", "SAMPLE_STEPS=ALL"],
                            "errorThreshold": 0,
                            }

    t1 = Transformer(crs_from="EPSG:6347",
                     crs_to="EPSG:6319",
                     allow_ballpark=False
                     )
    out_file1 = pathlib.Path(input_file).with_stem("_01_" + pathlib.Path(input_file).stem)
    t1.transform_raster(input_file=input_file,
                        output_file=out_file1,
                        apply_vertical=False,
                        )

    t2 = Transformer(crs_from="EPSG:6319",
                     crs_to="EPSG:7912",
                     allow_ballpark=False
                     )
    out_file2 = pathlib.Path(input_file).with_stem("_02_" + pathlib.Path(input_file).stem)
    t2.transform_raster(input_file=out_file1,
                        output_file=out_file2,
                        apply_vertical=True,
                        warp_kwargs=warp_kwargs_vertical | options
                        )

    t3 = Transformer(crs_from="EPSG:7912",
                     crs_to="EPSG:9000+NOAA:5543",
                     allow_ballpark=False
                     )
    out_file3 = pathlib.Path(input_file).with_stem("_03_" + pathlib.Path(input_file).stem)
    t3.transform_raster(input_file=out_file2,
                        output_file=out_file3,
                        apply_vertical=True,
                        warp_kwargs=warp_kwargs_vertical
                        )

    t4 = Transformer(crs_from="EPSG:9000+NOAA:5543",
                     crs_to="EPSG:9000+NOAA:5197",
                     allow_ballpark=False
                     )
    out_file4 = pathlib.Path(input_file).with_stem("_04_" + pathlib.Path(input_file).stem)
    t4.transform_raster(input_file=out_file3,
                        output_file=out_file4,
                        apply_vertical=True,
                        warp_kwargs=warp_kwargs_vertical
                        )

    t5 = Transformer(crs_from="EPSG:9000+NOAA:5197",
                     crs_to="EPSG:9000+NOAA:5200",
                     allow_ballpark=False
                     )
    out_file5 = pathlib.Path(input_file).with_stem("_05_" + pathlib.Path(input_file).stem)
    t5.transform_raster(input_file=out_file4,
                        output_file=out_file5,
                        apply_vertical=True,
                        warp_kwargs=warp_kwargs_vertical
                        )

    t6 = Transformer(crs_from="EPSG:9000",     # had to be "EPSG:9000+NOAA:5200", but there it's buggy and PROJ doesn't allow it
                     crs_to="EPSG:6318",       # had to be "EPSG:6318+NOAA:5200", but there it's buggy and PROJ doesn't allow it
                     allow_ballpark=False
                     )
    out_file6 = pathlib.Path(input_file).with_stem("_06_" + pathlib.Path(input_file).stem)
    t6.transform_raster(input_file=out_file5,
                        output_file=out_file6,
                        apply_vertical=False,
                        )

    t7 = Transformer(crs_from="EPSG:6318+NOAA:5200",
                     crs_to="EPSG:6347+NOAA:5200",
                     allow_ballpark=False
                     )
    p = pathlib.Path(input_file)
    xform_dir = os.path.join(r"C:\Users\mohammad.ashkezari\Documents\projects\vyperdatum\untrack\data\raster\NC\Manual", p.parent.name)
    os.makedirs(xform_dir, exist_ok=True)
    out_file7 = os.path.join(xform_dir, p.name)
    t7.transform_raster(input_file=out_file6,
                        output_file=out_file7,
                        apply_vertical=False,
                        )

    os.remove(out_file1)
    os.remove(out_file2)
    os.remove(out_file3)
    os.remove(out_file4)
    os.remove(out_file5)
    os.remove(out_file6)
    return out_file7


def transform_VA_MD_short(input_file):
    """
    4-Step transformation:
    EPSG:6347 >>> EPSG:7912                           [ITRF2014 (geographic 3D)]                       
    EPSG:7912 >>> EPSG:9000+NOAA:5200                 [ITRF2014 + MLLW height]
    EPSG:9000+NOAA:5200 >>> EPSG:6318+NOAA:5200       [NAD83(2011) + MLLW height]
    EPSG:6318+NOAA:5200 >>> EPSG:6347+NOAA:5200       [NAD83(2011) / UTM 18N + MLLW height]
    """
    options = {"options": ["s_coord_epoch=2010.0", "t_coord_epoch=2010.0"]}
    warp_kwargs_vertical = {
                            "outputType": gdal.gdalconst.GDT_Float32,
                            "srcBands": [1],
                            "dstBands": [1],
                            "warpOptions": ["APPLY_VERTICAL_SHIFT=YES", "SAMPLE_GRID=YES", "SAMPLE_STEPS=ALL"],
                            "errorThreshold": 0,
                            }

    t1 = Transformer(crs_from="EPSG:6347",
                     crs_to="EPSG:7912",
                     allow_ballpark=False
                     )
    out_file1 = pathlib.Path(input_file).with_stem("_01_" + pathlib.Path(input_file).stem)
    t1.transform_raster(input_file=input_file,
                        output_file=out_file1,
                        apply_vertical=False,
                        warp_kwargs=options
                        )

    t2 = Transformer(crs_from="EPSG:7912",
                     crs_to="EPSG:9000+NOAA:5200",
                     allow_ballpark=False
                     )
    out_file2 = pathlib.Path(input_file).with_stem("_02_" + pathlib.Path(input_file).stem)
    t2.transform_raster(input_file=out_file1,
                        output_file=out_file2,
                        apply_vertical=True,
                        warp_kwargs=warp_kwargs_vertical | options
                        )

    t3 = Transformer(crs_from="EPSG:9000",     # had to be "EPSG:9000+NOAA:5200", but there it's buggy and PROJ doesn't allow it
                     crs_to="EPSG:6318",       # had to be "EPSG:6318+NOAA:5200", but there it's buggy and PROJ doesn't allow it
                     allow_ballpark=False
                     )
    out_file3 = pathlib.Path(input_file).with_stem("_03_" + pathlib.Path(input_file).stem)
    t3.transform_raster(input_file=out_file2,
                        output_file=out_file3,
                        apply_vertical=False,
                        warp_kwargs=options
                        )

    t4 = Transformer(crs_from="EPSG:6318+NOAA:5200",
                     crs_to="EPSG:6347+NOAA:5200",
                     allow_ballpark=False
                     )
    p = pathlib.Path(input_file)
    xform_dir = os.path.join(r"C:\Users\mohammad.ashkezari\Documents\projects\vyperdatum\untrack\data\raster\NC\Manual", p.parent.name)
    os.makedirs(xform_dir, exist_ok=True)
    out_file4 = os.path.join(xform_dir, p.name)
    t4.transform_raster(input_file=out_file3,
                        output_file=out_file4,
                        apply_vertical=False
                        )

    os.remove(out_file1)
    os.remove(out_file2)
    os.remove(out_file3)
    return out_file4


if __name__ == "__main__":
    files = glob.glob(r"C:\Users\mohammad.ashkezari\Documents\projects\vyperdatum\untrack\data\raster\NC\Original\**\MD*.tif", recursive=True)
    for i, input_file in enumerate(files):
        print(f"{i+1}/{len(files)}: {input_file}")
        transformed_file = None
        if os.path.basename(input_file).startswith("NC"):
            crs_from = "EPSG:6347"
            crs_to = "EPSG:6347+NOAA:5374"
            tf = Transformer(crs_from=crs_from,
                             crs_to=crs_to,
                             steps=["EPSG:6347", "EPSG:6319", "EPSG:6318+NOAA:5374", "EPSG:6347+NOAA:5374"]
                            #  steps=Pipeline(crs_from=crs_from, crs_to=crs_to).linear_steps()
                            #  steps=Pipeline(crs_from=crs_from, crs_to=crs_to).graph_steps()
                             )
            tf.transform_raster(input_file=input_file,
                                output_file=input_file.replace("Original", "Manual"),
                                overview=False,
                                )
        elif os.path.basename(input_file).startswith("VA") or os.path.basename(input_file).startswith("MD"):
            crs_from = "EPSG:6347"
            crs_to = "EPSG:6347+NOAA:5200"
            tf = Transformer(crs_from=crs_from,
                             crs_to=crs_to,
                             steps=["EPSG:6347", "EPSG:6319", "EPSG:7912", "EPSG:9000+NOAA:5543", "EPSG:9000+NOAA:5197", "EPSG:9000+NOAA:5200", "EPSG:6318+NOAA:5200", "EPSG:6347+NOAA:5200"]
                            #  steps=Pipeline(crs_from=crs_from, crs_to=crs_to).linear_steps()
                            #  steps=Pipeline(crs_from=crs_from, crs_to=crs_to).graph_steps()
                             )
            tf.transform_raster(input_file=input_file,
                                output_file=input_file.replace("Original", "Manual"),
                                overview=False,
                                )
        print(f'\n{"*"*50} {i+1}/{len(files)} Completed {"*"*50}\n')
