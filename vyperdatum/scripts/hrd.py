import os
import json
from vyperdatum.transformer import Transformer
from vyperdatum.utils.raster_utils import raster_metadata, update_raster_wkt
from vyperdatum.utils.vdatum_rest_utils import vdatum_cross_validate
import pyproj as pp
from pathlib import Path


def get_tiff_files(parent_dir: str, extention: str) -> list:
    tiff_files = []
    for (dirpath, dirnames, filenames) in os.walk(parent_dir):
        for filename in filenames:
            if filename.endswith(extention):
                tiff_files.append(os.sep.join([dirpath, filename]))
    return tiff_files



def transform_with_vyperdatum(input_file, output_file, crs_from, crs_to):
    steps = [
                {"crs_from": "EPSG:6347", "crs_to": "EPSG:6318", "v_shift": False},
                {"crs_from": "EPSG:6319", "crs_to": "EPSG:6318+NOAA:98", "v_shift": True},
                {"crs_from": "EPSG:6318+NOAA:98", "crs_to": "EPSG:6347+NOAA:98", "v_shift": False}
            ]

    tf = Transformer(crs_from=crs_from,
                     crs_to=crs_to,
                    #  steps=steps
                     )
    
    tf.transform_raster(input_file=input_file,
                        output_file=output_file,
                        overview=False,
                        pre_post_checks=True,
                        vdatum_check=False
                        )
    return


if __name__ == "__main__":
    parent_dir = r"C:\Users\mohammad.ashkezari\Documents\projects\vyperdatum\untrack\data\raster\HRD\Original"
    files = get_tiff_files(parent_dir, extention=".tif")


    crs_from = "EPSG:32618+NOAA:86"
    crs_to = "EPSG:32618+EPSG:5703"

    # files = [r"C:\Users\mohammad.ashkezari\Documents\projects\vyperdatum\untrack\data\raster\NC\Original\NC1903-TB-C_BLK-07\NC1903-TB-C_BLK-07_US4NC1FG_ellipsoidal_dem.tif"]

    for i, input_file in enumerate(files[:1]):
        try:
            print(f"{i+1}/{len(files)}: {input_file}")
            output_file = input_file.replace("Original", "Manual")
            transform_with_vyperdatum(input_file, output_file, crs_from, crs_to)
            print(f'\n{"*"*50} {i+1}/{len(files)} Completed {"*"*50}\n')

            meta = raster_metadata(output_file)
            print(json.dumps(meta["Vyperdatum_Metadata"], sort_keys=True, indent=4))
        except Exception as e:
                efile = open(Path(output_file).parent.absolute()/Path(f"{os.path.split(input_file)[1]}_error.txt"), "w")
                efile.write(str(e))
                efile.close()
