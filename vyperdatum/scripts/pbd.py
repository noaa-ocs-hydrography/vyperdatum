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
        crs_from = "EPSG:6345+EPSG:5703"
        crs_to = "EPSG:6345+NOAA:93"
        # crs_from = "EPSG:2251+EPSG:5703"
        # crs_to = "EPSG:2251+NOAA:93"
    elif zone == "17N":
        crs_from = "EPSG:6346+EPSG:5703"
        crs_to = "EPSG:6346+NOAA:93"
    elif zone == "18N":
        crs_from = "EPSG:6347+EPSG:5703"
        crs_to = "EPSG:6347+NOAA:93"
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

    passed, cross_df = vdatum_cross_validate(s_wkt=pp.CRS(crs_from).to_wkt(),
                                             t_wkt=pp.CRS(crs_to).to_wkt(),
                                             n_sample=20,
                                             s_raster_metadata=raster_metadata(input_file),
                                             t_raster_metadata=raster_metadata(output_file),
                                             s_point_samples=None,
                                             t_point_samples=None,
                                             tolerance=0.3,
                                             raster_sampling_band=1,
                                             region="contiguous",
                                             pivot_h_crs="EPSG:6318",
                                             s_h_frame="NAD83_2011",
                                             s_v_frame="NAVD88",
                                             s_h_zone=None,
                                             t_h_frame="NAD83_2011",
                                             t_v_frame="LWD_IGLD85",
                                             t_h_zone=None
                                             )
    cross_df.to_csv(Path(output_file).parent.absolute()/Path(f"{os.path.split(input_file)[1]}_vdatum_check.csv"), index=False)    
    return


def transform_with_vyperdatum_igld85(input_file, zone):
    if zone == "16N":
        crs_from = "EPSG:6345+NOAA:92"
        crs_to = "EPSG:6345+NOAA:93"
        steps = [
                    {"crs_from": "EPSG:6345+NOAA:92", "crs_to": "EPSG:6318+NOAA:92", "v_shift": False},
                    {"crs_from": "EPSG:6318+NOAA:92", "crs_to": "EPSG:6318+NOAA:93", "v_shift": True},
                    {"crs_from": "EPSG:6318+NOAA:93", "crs_to": "EPSG:6345+NOAA:93", "v_shift": False}
                ]
    elif zone == "15N":
        crs_from = "EPSG:6344+NOAA:92"
        crs_to = "EPSG:6344+NOAA:93"
        steps = [
                    {"crs_from": "EPSG:6344+NOAA:92", "crs_to": "EPSG:6318+NOAA:92", "v_shift": False},
                    {"crs_from": "EPSG:6318+NOAA:92", "crs_to": "EPSG:6318+NOAA:93", "v_shift": True},
                    {"crs_from": "EPSG:6318+NOAA:93", "crs_to": "EPSG:6344+NOAA:93", "v_shift": False}
                ]
    elif zone == "17N":
        crs_from = "EPSG:6346+NOAA:92"
        crs_to = "EPSG:6346+NOAA:93"
        steps = [
                    {"crs_from": "EPSG:6346+NOAA:92", "crs_to": "EPSG:6318+NOAA:92", "v_shift": False},
                    {"crs_from": "EPSG:6318+NOAA:92", "crs_to": "EPSG:6318+NOAA:93", "v_shift": True},
                    {"crs_from": "EPSG:6318+NOAA:93", "crs_to": "EPSG:6346+NOAA:93", "v_shift": False}
                ]
    elif zone == "18N":
        crs_from = "EPSG:6347+NOAA:92"
        crs_to = "EPSG:6347+NOAA:93"
        steps = [
                    {"crs_from": "EPSG:6347+NOAA:92", "crs_to": "EPSG:6318+NOAA:92", "v_shift": False},
                    {"crs_from": "EPSG:6318+NOAA:92", "crs_to": "EPSG:6318+NOAA:93", "v_shift": True},
                    {"crs_from": "EPSG:6318+NOAA:93", "crs_to": "EPSG:6347+NOAA:93", "v_shift": False}
                ]

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

    passed, cross_df = vdatum_cross_validate(s_wkt=pp.CRS(crs_from).to_wkt(),
                                             t_wkt=pp.CRS(crs_to).to_wkt(),
                                             n_sample=20,
                                             s_raster_metadata=raster_metadata(input_file),
                                             t_raster_metadata=raster_metadata(output_file),
                                             s_point_samples=None,
                                             t_point_samples=None,
                                             tolerance=0.3,
                                             raster_sampling_band=1,
                                             region="contiguous",
                                             pivot_h_crs="EPSG:6318",
                                             s_h_frame="NAD83_2011",
                                             s_v_frame="IGLD85",
                                             s_h_zone=None,
                                             t_h_frame="NAD83_2011",
                                             t_v_frame="LWD_IGLD85",
                                             t_h_zone=None
                                             )
    cross_df.to_csv(Path(output_file).parent.absolute()/Path(f"{os.path.split(input_file)[1]}_vdatum_check.csv"), index=False)    
    return


def transform_with_concat_pipe(input_file, output_file,
                               nwld="nwldatum_4.7.0_20240621",
                               zone=16, vdatum="MLLW"):

    output_vrt = output_file.replace(".tif", ".vrt")

    SRC_HORZ_PUSH = "+step +proj=push +v_1 +v_2"
    SRC_HORZ_POP = "+step +proj=pop +v_1 +v_2"

    NAD83_UTM_to_Geographic = lambda zone: f"+step +inv +proj=utm +zone={zone} +ellps=GRS80"
    NAD83_Geographic_to_UTM = lambda zone: f"+step +proj=utm +zone={zone} +ellps=GRS80"

    # projinfo -s EPSG:6318+EPSG:5703 -t EPSG:6319 --spatial-test intersects --hide-ballpark -o PROJ
    # (CONUS is Operation 1, AK is Operation 2)
    # AK_NAVD88_GEOID12B_to_NAD83 = "+step +proj=vgridshift +grids=us_noaa_g2012ba0.tif +multiplier=1"
    CONUS_NAVD88_GEOID18_to_NAD83 = "+step +proj=vgridshift +grids=us_noaa_g2018u0.tif +multiplier=1"


    # Note: NWLD hydroids are <datum> - [NAD83(2011) 2010.0, ITRF2020 2020.0]; to subtract, we inverse vgridshift (+step +inv)
    NAD83_2011_to_NWLD = lambda vdatum, nwld: f"+step +inv +proj=vgridshift +grids=us_noaa_nos_{vdatum}-NAD83(2011)_2010.0_({nwld}).tif +multiplier=1"

    # zone: 9, etc.
    # nwld: "nwldatum_4.7.0_20240621" (AK_ERTDM_2023), "nwldatum_4.0.0_20190729" (VDatum 4.0 SE AK only), "nwldatum_3.7.0_20170907" (AK_ERTDM_2021)
    # vdatum: "underkeel_hydroid", "MLLW", etc.

    # AK_NAD83_UTM_NAVD88_height_to_NAD83_UTM_NWLD_height = lambda zone, nwld, vdatum: f"""
    #     +proj=pipeline
    #         {NAD83_UTM_to_Geographic(zone)}
    #         {SRC_HORZ_PUSH}
    #         {AK_NAVD88_GEOID12B_to_NAD83}
    #         {NAD83_2011_to_NWLD(vdatum, nwld)}
    #         {SRC_HORZ_POP}
    #         {NAD83_Geographic_to_UTM(zone)}
    # """
    # proj_pipeline_transform = AK_NAD83_UTM_NAVD88_height_to_NAD83_UTM_NWLD_height(zone, nwld, vdatum)


    CONUS_NAD83_UTM_NAVD88_height_to_NAD83_UTM_NWLD_height = lambda zone, nwld, vdatum: f"""
        +proj=pipeline
            {NAD83_UTM_to_Geographic(zone)}
            {SRC_HORZ_PUSH}
            {CONUS_NAVD88_GEOID18_to_NAD83}
            {NAD83_2011_to_NWLD(vdatum, nwld)}
            {SRC_HORZ_POP}
            {NAD83_Geographic_to_UTM(zone)}
    """
    proj_pipeline_transform = CONUS_NAD83_UTM_NAVD88_height_to_NAD83_UTM_NWLD_height(zone, nwld, vdatum)


    # output pixel resolution = input pixel resolution
    with gdal.Open(input_file, gdal.GA_ReadOnly) as input_ds:
        geotransform = input_ds.GetGeoTransform()
        xres, yres = geotransform[1], geotransform[5]

    # create vrt transformation template dataset
    ds = gdal.Warp(output_vrt, input_file, format="vrt",
                   outputType=gdal.gdalconst.GDT_Float32,
                   warpOptions=["APPLY_VERTICAL_SHIFT=YES", "SAMPLE_GRID=YES", "SAMPLE_STEPS=ALL"],
                   errorThreshold=0, xRes=xres, yRes=yres, targetAlignedPixels=True,
                   coordinateOperation=proj_pipeline_transform)

    # remove whitespace formatting used in proj pipeline string and put it in GeoTIFF metadata
    proj_pipeline_transform = re.sub(r'\s{2,}', ' ', proj_pipeline_transform).strip()
    ds.SetMetadataItem('TIFFTAG_IMAGEDESCRIPTION', proj_pipeline_transform)

    # execute the transformation from the vrt dataset to output compressed tif
    output_ds = gdal.Translate(output_file, ds, format="GTiff",
                               outputType=gdal.GDT_Float32,
                               creationOptions=["COMPRESS=DEFLATE", "TILED=YES"])
    output_ds = None
    os.remove(output_vrt)
    return




if __name__ == "__main__":
    # files = glob.glob(r"C:\Users\mohammad.ashkezari\Documents\projects\vyperdatum\untrack\data\raster\PBD\Original\NAVD88\16N\**\*.tif", recursive=True)
    files = glob.glob(r"C:\Users\mohammad.ashkezari\Documents\projects\vyperdatum\untrack\data\raster\PBD\Original\NAVD88\**\*.tif", recursive=True)
    # files = glob.glob(r"C:\Users\mohammad.ashkezari\Documents\projects\vyperdatum\untrack\data\raster\PBD\Original\IGLD85\**\*.tif", recursive=True)

    # files = [r"C:\Users\mohammad.ashkezari\Documents\projects\vyperdatum\untrack\data\raster\PBD\Original\NAVD88\17N\usace2018_niagara_dem_Job1145328\usace2018_niagara_dem_J1145328_000_001.tif"]

    for i, input_file in enumerate(files[:]):
        try:
            print(f"{i+1}/{len(files)}: {input_file}")
            if input_file.find(r"\16N") != -1:
                zone = "16N"
            elif input_file.find(r"\15N") != -1:
                zone = "15N"
            elif input_file.find(r"\17N") != -1:
                zone = "17N"
            elif input_file.find(r"\18N") != -1:
                zone = "18N"
            transform_with_vyperdatum_navd88(input_file, zone)
            # transform_with_vyperdatum_igld85(input_file, zone)

            print(f'\n{"*"*50} {i+1}/{len(files)} Completed {"*"*50}\n')
        except Exception as e:
            print(f"Error transforming {input_file}:\n{e}")