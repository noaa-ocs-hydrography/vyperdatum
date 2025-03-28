import os
import glob
from pathlib import Path
from vyperdatum.transformer import Transformer
from vyperdatum.utils.raster_utils import raster_metadata, update_raster_wkt
from vyperdatum.utils.vdatum_rest_utils import vdatum_cross_validate
import pyproj as pp
from osgeo import gdal
import re


def get_tiff_files(parent_dir: str, extention: str) -> list:
    tiff_files = []
    for (dirpath, dirnames, filenames) in os.walk(parent_dir):
        for filename in filenames:
            if filename.endswith(extention):
                tiff_files.append(os.sep.join([dirpath, filename]))
    return tiff_files


def transform_with_vyperdatum_navd88(input_file, zone):
    if zone == "16N":
        crs_from = "EPSG:26916+NOAA:89"
        crs_to = "EPSG:26916+EPSG:5703"
    elif zone == "15N":
        crs_from = "EPSG:26915+NOAA:89"
        crs_to = "EPSG:26915+EPSG:5703"
    else:
        raise ValueError(f"Invalid zone: {zone}")

    tf = Transformer(crs_from=crs_from,
                     crs_to=crs_to,
                    #  steps=steps
                     )
    output_file = input_file.replace("Original", "Manual")
    tf.transform_raster(input_file=input_file,
                        output_file=output_file,
                        overview=False,
                        pre_post_checks=True,
                        vdatum_check=False
                        )

    # passed, cross_df = vdatum_cross_validate(s_wkt=pp.CRS(crs_from).to_wkt(),
    #                                          t_wkt=pp.CRS(crs_to).to_wkt(),
    #                                          n_sample=20,
    #                                          s_raster_metadata=raster_metadata(input_file),
    #                                          t_raster_metadata=raster_metadata(output_file),
    #                                          s_point_samples=None,
    #                                          t_point_samples=None,
    #                                          tolerance=0.3,
    #                                          raster_sampling_band=1,
    #                                          region="contiguous",
    #                                          pivot_h_crs="EPSG:6318",
    #                                          s_h_frame="NAD83_2011",
    #                                          s_v_frame="NAVD88",
    #                                          s_h_zone=None,
    #                                          t_h_frame="NAD83_2011",
    #                                          t_v_frame="LWD_IGLD85",
    #                                          t_h_zone=None
    #                                          )
    # cross_df.to_csv(Path(output_file).parent.absolute()/Path(f"{os.path.split(input_file)[1]}_vdatum_check.csv"), index=False)    
    return


if __name__ == "__main__":
    files = glob.glob(r"C:\Users\mohammad.ashkezari\Documents\projects\vyperdatum\untrack\data\raster\MSP\Original\**\*.tif", recursive=True)

    for i, input_file in enumerate(files[1:2]):
        try:
            print(f"{i+1}/{len(files)}: {input_file}")
            zone = None
            if input_file.find(r"\16N") != -1:
                zone = "16N"
            elif input_file.find(r"\15N") != -1:
                zone = "15N"
            # meta = raster_metadata(input_file)
            # print(f"raster horizontal CRS: {meta['h_authcode']}\nraster vertical CRS: {meta['v_authcode']}")
            transform_with_vyperdatum_navd88(input_file, zone)

            print(f'\n{"*"*50} {i+1}/{len(files)} Completed {"*"*50}\n')
        except Exception as e:
            print(f"Error transforming {input_file}:\n{e}")


