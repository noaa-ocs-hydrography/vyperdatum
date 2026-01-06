import glob
from vyperdatum.transformer import Transformer
from vyperdatum.utils.raster_utils import raster_metadata, update_raster_wkt
from vyperdatum.utils.vdatum_rest_utils import vdatum_cross_validate
import pyproj as pp




if __name__ == "__main__":

    parent_dir = r"C:\Users\mohammad.ashkezari\Documents\projects\vyperdatum\untrack\data\raster\PBC_mixed\Original\**\*.tiff"
    parent_dir = r"C:\Users\mohammad.ashkezari\Documents\projects\vyperdatum\untrack\data\raster\PBC_mixed\Original\**\*.bag"
    # parent_dir = r"C:\Users\mohammad.ashkezari\Desktop\bag\Original\*.bag"
    files = glob.glob(parent_dir, recursive=True)[:]
    files = [r"C:\Users\mohammad.ashkezari\Documents\projects\vyperdatum\untrack\data\raster\PBC_mixed\Original\E01096\E01096_MB_4m_MLLW_7of7_clipped.bag"]
    files = [r"C:\Users\mohammad.ashkezari\Documents\projects\vyperdatum\untrack\data\raster\PBC_mixed\Original\E01096\clipped.bag"]
    files = [r"C:\Users\mohammad.ashkezari\Documents\projects\vyperdatum\untrack\data\raster\PBC_mixed\Original\E01096\E01096_MB_4m_MLLW_7of7.bag"]
    crs_from = "EPSG:32619+NOAA:101"
    crs_to = "EPSG:6348+NOAA:101"
    # steps = [{'crs_from': 'EPSG:32619', 'crs_to': 'EPSG:9755', 'v_shift': False},
    #          {'crs_from': 'EPSG:9755', 'crs_to': 'EPSG:6318', 'v_shift': False},
    #          {'crs_from': 'EPSG:6318', 'crs_to': 'EPSG:6348', 'v_shift': False},
    #          ]
    for i, input_file in enumerate(files):
        print(f"{i+1}/{len(files)}: {input_file}")
        tf = Transformer(crs_from=crs_from,
                         crs_to=crs_to,
                        #  steps=steps
                         )
        output_file = input_file.replace("Original", "Manual")
        tf.transform(input_file=input_file,
                     output_file=output_file,
                     pre_post_checks=True,
                     vdatum_check=False
                     )
        print(f'\n{"*"*50} {i+1}/{len(files)} Completed {"*"*50}\n')
