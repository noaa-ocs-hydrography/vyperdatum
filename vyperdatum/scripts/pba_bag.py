import os
import glob
import pathlib
from vyperdatum.transformer import Transformer
from vyperdatum.utils.raster_utils import raster_metadata
from vyperdatum.pipeline import Pipeline


def transform(input_file, home_dir):
    options = {"options": ["s_coord_epoch=2010.0", "t_coord_epoch=2010.0"]}
    warp_kwargs_vertical = {
                            "outputType": gdal.gdalconst.GDT_Float32,
                            "srcBands": [1],
                            "dstBands": [1],
                            "warpOptions": ["APPLY_VERTICAL_SHIFT=YES", "SAMPLE_GRID=YES", "SAMPLE_STEPS=ALL"],
                            "errorThreshold": 0,
                            }
    
    t1 = Transformer(crs_from="EPSG:32609",
                     crs_to="EPSG:9755",
                     allow_ballpark=False
                     )
    out_file1 = pathlib.Path(input_file).with_stem("_01_" + pathlib.Path(input_file).stem)
    t1.transform_raster(input_file=input_file,
                        output_file=out_file1,
                        apply_vertical=False,
                        warp_kwargs=options
                        )

    t2 = Transformer(crs_from="EPSG:9755",
                     crs_to="EPSG:6318",
                     allow_ballpark=False
                     )
    out_file2 = pathlib.Path(input_file).with_stem("_02_" + pathlib.Path(input_file).stem)
    t2.transform_raster(input_file=out_file1,
                        output_file=out_file2,
                        apply_vertical=False,
                        warp_kwargs=options
                        )

    t3 = Transformer(crs_from="EPSG:6318",
                     crs_to="EPSG:26909",
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

def transform_MLLW(input_file, home_dir, in_wgs84_crs, out_nad83_crs):
    options = {"options": ["s_coord_epoch=2010.0", "t_coord_epoch=2010.0"]}
    warp_kwargs_vertical = {
                            "outputType": gdal.gdalconst.GDT_Float32,
                            "srcBands": [1],
                            "dstBands": [1],
                            "warpOptions": ["APPLY_VERTICAL_SHIFT=YES"],
                            "errorThreshold": 0,
                            }

    t1 = Transformer(crs_from=f"{in_wgs84_crs}+EPSG:5866",
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
                     crs_to=f"{out_nad83_crs}+EPSG:5866",
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
    home_dir = r"C:\Users\mohammad.ashkezari\Documents\projects\vyperdatum\untrack\data\raster\PBA"
    files = glob.glob(home_dir + r"\Original\**\W*.bag", recursive=True)
    for i, input_file in enumerate(files):
        print(f"{i+1}/{len(files)}: {input_file}")
        raster_metadata(input_file, verbose=True)
        if os.path.basename(input_file).startswith("H12137"):
            transformed_file = transform_MLLW(input_file, home_dir, "EPSG:32619", "EPSG:26919")
        elif os.path.basename(input_file).startswith("W00656") or os.path.basename(input_file).startswith("D00158"):
            # transformed_file = transform_MLLW(input_file, home_dir, "EPSG:32617", "EPSG:26917")
            crs_from = "EPSG:32617+EPSG:5866"
            crs_to = "EPSG:26917+EPSG:5866"
            print(Pipeline(crs_from=crs_from, crs_to=crs_to).linear_steps())
            # print(Pipeline(crs_from=crs_from, crs_to=crs_to).graph_steps())
            # tf = Transformer(crs_from=crs_from,
            #                  crs_to=crs_to,
            #                  steps=["EPSG:32617+EPSG:5866", "EPSG:9755+EPSG:5866", "EPSG:6318+EPSG:5866", "EPSG:26917+EPSG:5866"]
            #                 #  steps=Pipeline(crs_from=crs_from, crs_to=crs_to).linear_steps()
            #                 #  steps=Pipeline(crs_from=crs_from, crs_to=crs_to).graph_steps()
            #                  )
            # tf.transform_raster(input_file=input_file,
            #                     output_file=input_file.replace("Original", "Manual"),
            #                     overview=False,
            #                     )
        else:
            transformed_file = transform(input_file, home_dir)

        print(f'\n{"*"*50} {i+1}/{len(files)} Completed {"*"*50}\n')
