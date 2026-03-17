import glob
from vyperdatum.transformer import Transformer
from vyperdatum.utils.raster_utils import raster_metadata, update_raster_wkt
from vyperdatum.utils.vdatum_rest_utils import vdatum_cross_validate
import pyproj as pp




if __name__ == "__main__":

    parent_dir = r"C:\Users\mohammad.ashkezari\Documents\projects\vyperdatum\untrack\data\raster\PBA\PBA_WestCoast_UTM10N_NCD\Original\or2014_usace_ncmp_or_dem_J1328127\*.tif"
    
    or2014_usace_ncmp_or_dem_J1328127tR00_C01.tif
    
    files = glob.glob(parent_dir, recursive=True)[:1]
    crs_from = "EPSG:26910+EPSG:5703"
    crs_to = "EPSG:26910+NOAA:101"



    for i, input_file in enumerate(files):
        print(f"{i+1}/{len(files)}: {input_file}")
        tf = Transformer(crs_from=crs_from,
                         crs_to=crs_to
                         )
        output_file = input_file.replace("Original", "Manual")
        tf.transform(input_file=input_file,
                     output_file=output_file,
                     pre_post_checks=True,
                     vdatum_check=False
                     )
        print(f'\n{"*"*50} {i+1}/{len(files)} Completed {"*"*50}\n')
