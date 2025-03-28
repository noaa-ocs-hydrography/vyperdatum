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


# if __name__ == "__main__":
#     parent_dir = r"C:\Users\mohammad.ashkezari\Documents\projects\vyperdatum\untrack\data\raster\PBB\Original"
#     files = get_tiff_files(parent_dir, extention=".tif")
#     crs_from1 = "EPSG:6346"
#     crs_to1 = "EPSG:9990+NOAA:98"
#     crs_from2 = "EPSG:9990"
#     crs_to2 = "EPSG:6346"
#     crs_to3 = "EPSG:6346+NOAA:98"
#     for i, input_file in enumerate(files[:1]):
#         print(f"{i+1}/{len(files)}: {input_file}")
#         tf = Transformer(crs_from=crs_from1,
#                          crs_to=crs_to1,
#                          steps=[crs_from1, "EPSG:6319", "EPSG:7912", "EPSG:9989", crs_to1]
#                          )
#         output_file = input_file.replace("Original", "Manual")
#         output_ITRF = output_file + "_ITRF.tif"
#         tf.transform_raster(input_file=input_file,
#                             output_file=output_ITRF,
#                             overview=False,
#                             pre_post_checks=False,
#                             vdatum_check=False
#                             )

#         tf = Transformer(crs_from=crs_from2,
#                          crs_to=crs_to2,
#                          steps=["EPSG:9990", "EPSG:9000", crs_to2]
#                          )
#         tf.transform_raster(input_file=output_ITRF,
#                             output_file=output_file,
#                             overview=False,
#                             vdatum_check=False
#                             )
#         update_raster_wkt(output_file, pp.CRS(crs_to3).to_wkt())
#         os.remove(output_ITRF)
#         vdatum_cross_validate(s_wkt=pp.CRS(crs_from1).to_wkt(),
#                               t_wkt=pp.CRS(crs_to3).to_wkt(),
#                               n_sample=20,
#                               s_raster_metadata=raster_metadata(input_file),
#                               t_raster_metadata=raster_metadata(output_file),
#                               s_point_samples=None,
#                               t_point_samples=None,
#                               tolerance=0.3,
#                               raster_sampling_band=1,
#                               region="contiguous",
#                               pivot_h_crs="EPSG:6318",
#                               s_h_frame=None,
#                               s_v_frame=None,
#                               s_h_zone=None,
#                               t_h_frame=None,
#                               t_v_frame=None,
#                               t_h_zone=None
#                               )
#         print(f'\n{"*"*50} {i+1}/{len(files)} Completed {"*"*50}\n')



if __name__ == "__main__":
    parent_dir = r"C:\Users\mohammad.ashkezari\Documents\projects\vyperdatum\untrack\data\raster\PBB\Original"
    files = get_tiff_files(parent_dir, extention=".tif")
    
    files = [r"C:\Users\mohammad.ashkezari\Documents\projects\vyperdatum\untrack\data\raster\PBB\Original\FL1813-TB-N\FL1813-TB-N_US4FL2DJ_ellipsoidal_dem.tif"]
    crs_from = "EPSG:6346"
    crs_to = "EPSG:6346+NOAA:98"
    for i, input_file in enumerate(files[:1]):
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
