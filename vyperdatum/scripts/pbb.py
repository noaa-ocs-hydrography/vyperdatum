import os
from vyperdatum.transformer import Transformer
from vyperdatum.utils.raster_utils import raster_metadata, update_raster_wkt
from vyperdatum.utils.vdatum_rest_utils import vdatum_cross_validate
import pyproj as pp


def get_tiff_files(parent_dir: str, extention: str) -> list:
    tiff_files = []
    for (dirpath, dirnames, filenames) in os.walk(parent_dir):
        for filename in filenames:
            if filename.endswith(extention):
                tiff_files.append(os.sep.join([dirpath, filename]))
    return tiff_files


if __name__ == "__main__":
    parent_dir = r"C:\Users\mohammad.ashkezari\Documents\projects\vyperdatum\untrack\data\raster\PBB\Original\FL2205-TB-C"
    files = get_tiff_files(parent_dir, extention=".tif")
    
    # files = [r"C:\Users\mohammad.ashkezari\Documents\projects\vyperdatum\untrack\data\raster\PBB\Original\FL1813-TB-N\FL1813-TB-N_US4FL2DJ_ellipsoidal_dem.tif"]
    crs_from = "EPSG:6346"
    crs_to = "EPSG:6346+NOAA:98"
    for i, input_file in enumerate(files[:]):
        print(f"{i+1}/{len(files)}: {input_file}")
        tf = Transformer(crs_from=crs_from,
                         crs_to=crs_to
                         )
        output_file = input_file.replace("Original", "Manual")
        tf.transform_raster(input_file=input_file,
                            output_file=output_file,
                            overview=False,
                            pre_post_checks=True,
                            vdatum_check=True
                            )                    
        print(f'\n{"*"*50} {i+1}/{len(files)} Completed {"*"*50}\n')

