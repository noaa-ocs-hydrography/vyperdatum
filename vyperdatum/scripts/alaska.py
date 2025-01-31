import os
import pyproj as pp
from vyperdatum.transformer import Transformer
from vyperdatum.utils.raster_utils import raster_metadata, update_raster_wkt
from vyperdatum.utils.vdatum_rest_utils import vdatum_cross_validate


def get_tiff_files(parent_dir: str, extention: str) -> list:
    tiff_files = []
    for (dirpath, dirnames, filenames) in os.walk(parent_dir):
        for filename in filenames:
            if filename.endswith(extention):
                tiff_files.append(os.sep.join([dirpath, filename]))
    return tiff_files

if __name__ == "__main__":
    parent_dir = r"C:\Users\mohammad.ashkezari\Documents\projects\vyperdatum\untrack\data\raster\RSD\Alaska\Original"
    files = get_tiff_files(parent_dir, extention=".tif")
    crs_from = "EPSG:6338+NOAA:5537"
    crs_to = "EPSG:6338+NOAA:98"

    for i, input_file in enumerate(files[:2]):
        print(f"{i+1}/{len(files)}: {input_file}")
        tf = Transformer(crs_from=crs_from,
                         crs_to=crs_to,
                         )
        output_file = input_file.replace("Original", "Manual")
        tf.transform_raster(input_file=input_file,
                            output_file=output_file,
                            overview=False,
                            pre_post_checks=False,
                            vdatum_check=False
                            )

        # vdatum_cross_validate(s_wkt=pp.CRS(crs_from).to_wkt(),
        #                       t_wkt=pp.CRS(crs_to).to_wkt(),
        #                       n_sample=20,
        #                       s_raster_metadata=raster_metadata(input_file),
        #                       t_raster_metadata=raster_metadata(output_file),
        #                       s_point_samples=None,
        #                       t_point_samples=None,
        #                       tolerance=0.3,
        #                       raster_sampling_band=1,
        #                       region="ak",
        #                       pivot_h_crs="EPSG:6318",
        #                       s_h_frame=None,
        #                       s_v_frame=None,
        #                       s_h_zone=None,
        #                       t_h_frame=None,
        #                       t_v_frame=None,
        #                       t_h_zone=None
        #                       )
        print(f'\n{"*"*50} {i+1}/{len(files)} Completed {"*"*50}\n')
