import glob
from vyperdatum.transformer import Transformer
from vyperdatum.utils.raster_utils import raster_metadata, update_raster_wkt
from vyperdatum.utils.vdatum_rest_utils import vdatum_cross_validate
import pyproj as pp




if __name__ == "__main__":

    parent_dir = r"C:\Users\mohammad.ashkezari\Documents\projects\vyperdatum\untrack\data\raster\PBC\Original\ME2201_block04*\*.tif"
    files = glob.glob(parent_dir, recursive=True)[:]
    crs_from = "EPSG:6348"
    crs_to = "EPSG:6348+NOAA:101"
    for i, input_file in enumerate(files):
        print(f"{i+1}/{len(files)}: {input_file}")
        tf = Transformer(crs_from=crs_from,
                         crs_to=crs_to
                         )
        output_file = input_file.replace("Original", "Manual")
        tf.transform_raster(input_file=input_file,
                            output_file=output_file,
                            overview=False,
                            pre_post_checks=True,
                            vdatum_check=False
                            )
        print(f'\n{"*"*50} {i+1}/{len(files)} Completed {"*"*50}\n')
