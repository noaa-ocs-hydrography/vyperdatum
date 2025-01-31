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
    parent_dir = r"C:\Users\mohammad.ashkezari\Documents\projects\vyperdatum\untrack\data\raster\HRD\Original"
    files = get_tiff_files(parent_dir, extention=".tif")

    for i, input_file in enumerate(files[:]):
        print(f"{i+1}/{len(files)}: {input_file}")
        output_file = input_file.replace("Original", "Manual")

        # to ITRF2020
        output_ITRF = output_file + "_ITRF.tif"
        tf = Transformer(crs_from="EPSG:32618",
                         crs_to="EPSG:9990",
                         steps=["EPSG:32618", "EPSG:9755", "EPSG:6318", "EPSG:9000", "EPSG:9990"]
                         )
        tf.transform_raster(input_file=input_file,
                            output_file=output_ITRF,
                            overview=False,
                            pre_post_checks=False,
                            vdatum_check=False
                            )

        # to NAVD88
        output_ITRF_NAVD88 = output_ITRF + "_NAVD88.tif"
        tf = Transformer(crs_from="EPSG:9990+NOAA:91",
                         crs_to="EPSG:9990+EPSG:5703",
                         steps=["EPSG:9990+NOAA:91", "EPSG:9990+EPSG:5703"]
                         )
        tf.transform_raster(input_file=output_ITRF,
                            output_file=output_ITRF_NAVD88,
                            overview=False,
                            vdatum_check=False
                            )

        # back to WGS84
        tf = Transformer(crs_from="EPSG:9990",
                         crs_to="EPSG:32618",
                         steps=["EPSG:9990", "EPSG:9990", "EPSG:6318", "EPSG:9755", "EPSG:32618"]
                         )
        tf.transform_raster(input_file=output_ITRF_NAVD88,
                            output_file=output_file,
                            overview=False,
                            vdatum_check=False
                            )

        update_raster_wkt(output_file, pp.CRS("EPSG:32618+EPSG:5703").to_wkt())
        os.remove(output_ITRF)
        os.remove(output_ITRF_NAVD88)

        print(f'\n{"*"*50} {i+1}/{len(files)} Completed {"*"*50}\n')
