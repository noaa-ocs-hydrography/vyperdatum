import os
import glob
from vyperdatum.transformer import Transformer
from vyperdatum.pipeline import Pipeline
from vyperdatum.utils.raster_utils import raster_metadata, update_raster_wkt
from vyperdatum.utils.vdatum_rest_utils import vdatum_cross_validate
import pyproj as pp


if __name__ == "__main__":
    files = glob.glob(r"C:\Users\mohammad.ashkezari\Documents\projects\vyperdatum\untrack\data\raster\PBC\V\Original\**\*.tif", recursive=True)
    for i, input_file in enumerate(files):
        print(f"{i+1}/{len(files)}: {input_file}")
        if os.path.basename(input_file).startswith("MA"):
            crs_from = "EPSG:6348"
            crs_to = "EPSG:6348+NOAA:5320"
            tf = Transformer(crs_from=crs_from,
                             crs_to=crs_to,
                             steps=["EPSG:6348", "EPSG:6319", "EPSG:6318+NOAA:5320", "EPSG:6348+NOAA:5320"]
                            #  steps=Pipeline(crs_from=crs_from, crs_to=crs_to).linear_steps()
                            #  steps=Pipeline(crs_from=crs_from, crs_to=crs_to).graph_steps()
                             )
            tf.transform_raster(input_file=input_file,
                                output_file=input_file.replace("Original", "Manual"),
                                overview=False,
                                )
        elif os.path.basename(input_file).startswith("ma"):
            crs_from1 = "EPSG:26919"
            crs_to1 = "EPSG:9990+NOAA:98"
            crs_from2 = "EPSG:9990"
            crs_to2 = "EPSG:26919"
            crs_to3 = "EPSG:26919+NOAA:98"

            tf = Transformer(crs_from=crs_from1,
                             crs_to=crs_to1,
                             steps=[crs_from1, "EPSG:6319", "EPSG:7912", "EPSG:9989", crs_to1]
                             )
            output_file = input_file.replace("Original", "Manual")
            output_ITRF = output_file + "_ITRF.tif"
            tf.transform_raster(input_file=input_file,
                                output_file=output_ITRF,
                                overview=False,
                                pre_post_checks=False,
                                vdatum_check=False
                                )

            tf = Transformer(crs_from=crs_from2,
                             crs_to=crs_to2,
                             steps=["EPSG:9990", "EPSG:9000", crs_to2]
                             )
            tf.transform_raster(input_file=output_ITRF,
                                output_file=output_file,
                                overview=False,
                                vdatum_check=False
                                )
            update_raster_wkt(output_file, pp.CRS(crs_to3).to_wkt())
            os.remove(output_ITRF)
            vdatum_cross_validate(s_wkt=pp.CRS(crs_from1).to_wkt(),
                                  t_wkt=pp.CRS(crs_to3).to_wkt(),
                                  n_sample=20,
                                  s_raster_metadata=raster_metadata(input_file),
                                  t_raster_metadata=raster_metadata(output_file),
                                  s_point_samples=None,
                                  t_point_samples=None,
                                  tolerance=0.3,
                                  raster_sampling_band=1,
                                  region="contiguous",
                                  pivot_h_crs="EPSG:6318",
                                  s_h_frame=None,
                                  s_v_frame=None,
                                  s_h_zone=None,
                                  t_h_frame=None,
                                  t_v_frame=None,
                                  t_h_zone=None
                                  )
        elif os.path.basename(input_file).startswith("ct") or os.path.basename(input_file).startswith("rh"):
            crs_from1 = "EPSG:26919"
            crs_to1 = "EPSG:9990+NOAA:98"
            crs_from2 = "EPSG:9990"
            crs_to2 = "EPSG:26919"
            crs_to3 = "EPSG:26919+NOAA:98"

            tf = Transformer(crs_from=crs_from1,
                             crs_to=crs_to1,
                             steps=[crs_from1, "EPSG:6319", "EPSG:7912", "EPSG:9989", crs_to1]
                             )
            output_file = input_file.replace("Original", "Manual")
            output_ITRF = output_file + "_ITRF.tif"
            tf.transform_raster(input_file=input_file,
                                output_file=output_ITRF,
                                overview=False,
                                pre_post_checks=False,
                                vdatum_check=False
                                )

            tf = Transformer(crs_from=crs_from2,
                             crs_to=crs_to2,
                             steps=["EPSG:9990", "EPSG:9000", crs_to2]
                             )
            tf.transform_raster(input_file=output_ITRF,
                                output_file=output_file,
                                overview=False,
                                vdatum_check=False
                                )
            update_raster_wkt(output_file, pp.CRS(crs_to3).to_wkt())
            os.remove(output_ITRF)
            vdatum_cross_validate(s_wkt=pp.CRS(crs_from1).to_wkt(),
                                  t_wkt=pp.CRS(crs_to3).to_wkt(),
                                  n_sample=20,
                                  s_raster_metadata=raster_metadata(input_file),
                                  t_raster_metadata=raster_metadata(output_file),
                                  s_point_samples=None,
                                  t_point_samples=None,
                                  tolerance=0.3,
                                  raster_sampling_band=1,
                                  region="contiguous",
                                  pivot_h_crs="EPSG:6318",
                                  s_h_frame=None,
                                  s_v_frame=None,
                                  s_h_zone=None,
                                  t_h_frame=None,
                                  t_v_frame=None,
                                  t_h_zone=None
                                  )
        print(f'\n{"*"*50} {i+1}/{len(files)} Completed {"*"*50}\n')
