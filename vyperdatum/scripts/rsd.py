import os
import glob
from pathlib import Path
from vyperdatum.transformer import Transformer
from vyperdatum.utils.raster_utils import raster_metadata, update_raster_wkt
from vyperdatum.utils.vdatum_rest_utils import vdatum_cross_validate
from vyperdatum.utils.crs_utils import pipeline_string
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


def transform_with_vyperdatum(input_file, crs_from, crs_to):
    # steps = [
    #             {"crs_from": "EPSG:6347", "crs_to": "EPSG:6318", "v_shift": False},
    #             {"crs_from": "EPSG:6319", "crs_to": "EPSG:6318+NOAA:98", "v_shift": True},
    #             {"crs_from": "EPSG:6318+NOAA:98", "crs_to": "EPSG:6347+NOAA:98", "v_shift": False}
    #         ]

    tf = Transformer(crs_from=crs_from,
                     crs_to=crs_to,
                    #  steps=steps
                     )
    output_file = input_file.replace("Original", "Manual")
    tf.transform_raster(input_file=input_file,
                        output_file=output_file,
                        overview=False,
                        pre_post_checks=True,
                        vdatum_check=True
                        )
    return


def steps_to_concat_pipe(steps):
    concat_pipe = "+proj=pipeline "
    for step in steps:
        pipe = pipeline_string(step["crs_from"], step["crs_to"])
        concat_pipe = f"{concat_pipe} {pipe.split('+proj=pipeline')[1]}"
    return concat_pipe


def transform_with_concat_steps(input_file, output_file):
    steps = [
                {"crs_from": "EPSG:6347", "crs_to": "EPSG:6318", "v_shift": False},
                {"crs_from": "EPSG:6319", "crs_to": "EPSG:6318+NOAA:98", "v_shift": True},
                {"crs_from": "EPSG:6318", "crs_to": "EPSG:6347", "v_shift": False}
            ]


    gdal_warp_concatenated_transform = steps_to_concat_pipe(steps)
    output_vrt = output_file.replace(".tif", ".vrt")
    # output pixel resolution = input pixel resolution
    with gdal.Open(input_file, gdal.GA_ReadOnly) as input_ds:
        geotransform = input_ds.GetGeoTransform()
        xres, yres = geotransform[1], geotransform[5]

    # create vrt transformation template dataset
    ds = gdal.Warp(output_vrt, input_file, format="vrt", outputType=gdal.gdalconst.GDT_Float32,warpOptions = ["APPLY_VERTICAL_SHIFT=YES", "SAMPLE_GRID=YES", "SAMPLE_STEPS=ALL"], errorThreshold = 0, xRes=xres, yRes=yres, targetAlignedPixels=True, coordinateOperation=gdal_warp_concatenated_transform)
    # remove whitespace formatting used in proj pipeline string and put it in GeoTIFF metadata
    gdal_warp_concatenated_transform = re.sub(r'\s{2,}', ' ', gdal_warp_concatenated_transform).strip()
    ds.SetMetadataItem('TIFFTAG_IMAGEDESCRIPTION', gdal_warp_concatenated_transform)

    # execute the transformation from the vrt dataset to output compressed tif
    output_ds = gdal.Translate(output_file, ds, format="GTiff", outputType=gdal.GDT_Float32, creationOptions=["COMPRESS=DEFLATE", "TILED=YES"])
    output_ds = None    
    return

def transform_with_concat_pipe(input_file, output_file):    
    output_vrt = output_file.replace(".tif", ".vrt")

    #projinfo -s EPSG:6347 -t EPSG:9989 --spatial-test intersects --hide-ballpark -o PROJ
    NAD83_2011_UTM18N_to_ITRF2020 = """
    +step +inv +proj=utm +zone=18 +ellps=GRS80
    +step +proj=cart +ellps=GRS80
    +step +inv +proj=helmert
        +x=1.0039 +y=-1.90961 +z=-0.54117 +rx=0.02678138 +ry=-0.00042027 +rz=0.01093206 +s=-5.109e-05
        +dx=0.00079 +dy=-0.0007 +dz=-0.00124 +drx=6.667e-05 +dry=-0.00075744 +drz=-5.133e-05 +ds=-7.201e-05
        +t_epoch=2010 +convention=coordinate_frame
    +step +inv +proj=cart +ellps=GRS80"""

    #projinfo -s EPSG:9990 -t EPSG:6347 --spatial-test intersects --hide-ballpark -o PROJ
    ITRF2020_2010_to_NAD83_2011_18N = """
    +step +proj=cart +ellps=GRS80
    +step +proj=helmert +x=1.0039 +y=-1.90961 +z=-0.54117 +rx=0.02678138
            +ry=-0.00042027 +rz=0.01093206 +s=-5.109e-05 +dx=0.00079 +dy=-0.0007
            +dz=-0.00124 +drx=6.667e-05 +dry=-0.00075744 +drz=-5.133e-05 +ds=-7.201e-05
            +t_epoch=2010 +convention=coordinate_frame
    +step +inv +proj=cart +ellps=GRS80
    +step +proj=utm +zone=18 +ellps=GRS80"""

    MLLW_ITRF2020_2020 = "us_noaa_nos_MLLW-ITRF2020_2020.0_(nwldatum_4.7.0_20240621).tif"

    gdal_warp_concatenated_transform = f"""\
    +proj=pipeline
    {NAD83_2011_UTM18N_to_ITRF2020}
    +step +inv +proj=vgridshift +grids={MLLW_ITRF2020_2020} +multiplier=1
    +step +proj=push +v_3
    {ITRF2020_2010_to_NAD83_2011_18N}
    +step +proj=pop +v_3"""

    # output pixel resolution = input pixel resolution
    with gdal.Open(input_file, gdal.GA_ReadOnly) as input_ds:
        geotransform = input_ds.GetGeoTransform()
        xres, yres = geotransform[1], geotransform[5]

    # create vrt transformation template dataset
    ds = gdal.Warp(output_vrt, input_file, format="vrt", outputType=gdal.gdalconst.GDT_Float32,warpOptions = ["APPLY_VERTICAL_SHIFT=YES", "SAMPLE_GRID=YES", "SAMPLE_STEPS=ALL"], errorThreshold = 0, xRes=xres, yRes=yres, targetAlignedPixels=True, coordinateOperation=gdal_warp_concatenated_transform)
    # remove whitespace formatting used in proj pipeline string and put it in GeoTIFF metadata
    gdal_warp_concatenated_transform = re.sub(r'\s{2,}', ' ', gdal_warp_concatenated_transform).strip()
    ds.SetMetadataItem('TIFFTAG_IMAGEDESCRIPTION', gdal_warp_concatenated_transform)

    # execute the transformation from the vrt dataset to output compressed tif
    output_ds = gdal.Translate(output_file, ds, format="GTiff", outputType=gdal.GDT_Float32, creationOptions=["COMPRESS=DEFLATE", "TILED=YES"])
    output_ds = None    
    return

def nad83_transform_with_concat_pipe(input_file, output_file):    
    output_vrt = output_file.replace(".tif", ".vrt")

    #projinfo -s EPSG:6347 -t EPSG:6319 --spatial-test intersects --hide-ballpark -o PROJ
    NAD83_2011_UTM18N_to_GEOGRAPHIC = "+step +inv +proj=utm +zone=18 +ellps=GRS80"
    GEOGRAPHIC_to_NAD83_2011_UTM18N = "+step +proj=utm +zone=18 +ellps=GRS80"
    # NAD83_2011_UTM18N_to_GEOGRAPHIC = """
    # +step +inv +proj=utm +zone=18 +ellps=GRS80
    # +step +proj=unitconvert +xy_in=rad +z_in=m +xy_out=deg +z_out=m
    # +step +proj=axisswap +order=2,1
    # """
    # GEOGRAPHIC_to_NAD83_2011_UTM18N = """
    # +step +proj=axisswap +order=2,1
    # +step +proj=unitconvert +xy_in=deg +xy_out=rad
    # +step +proj=utm +zone=18 +ellps=GRS80
    # """

    horz_push = "+step +proj=push +v_1 +v_2"
    horz_pop = "+step +proj=pop +v_1 +v_2"

    #projinfo -s EPSG:6319 -t EPSG:6318+NOAA:98 --spatial-test intersects --hide-ballpark -o PROJ
    NAD83_2011_to_NWLD = "+step +inv +proj=vgridshift +grids=us_noaa_nos_MLLW-NAD83(2011)_2010.0_(nwldatum_4.7.0_20240621).tif +multiplier=1"
    # NAD83_2011_to_NWLD = """
    # +step +proj=axisswap +order=2,1
    # +step +proj=unitconvert +xy_in=deg +xy_out=rad
    # +step +inv +proj=vgridshift
    #         +grids=us_noaa_nos_MLLW-NAD83(2011)_2010.0_(nwldatum_4.7.0_20240621).tif
    #         +multiplier=1
    # +step +proj=unitconvert +xy_in=rad +xy_out=deg
    # +step +proj=axisswap +order=2,1
    # """
    
    gdal_warp_concatenated_transform = f"""\
    +proj=pipeline
    {NAD83_2011_UTM18N_to_GEOGRAPHIC}

    {NAD83_2011_to_NWLD}

    {GEOGRAPHIC_to_NAD83_2011_UTM18N}
    """

    # output pixel resolution = input pixel resolution
    with gdal.Open(input_file, gdal.GA_ReadOnly) as input_ds:
        geotransform = input_ds.GetGeoTransform()
        xres, yres = geotransform[1], geotransform[5]

    # create vrt transformation template dataset
    ds = gdal.Warp(output_vrt, input_file, format="vrt", outputType=gdal.gdalconst.GDT_Float32,warpOptions = ["APPLY_VERTICAL_SHIFT=YES", "SAMPLE_GRID=YES", "SAMPLE_STEPS=ALL"], errorThreshold = 0, xRes=xres, yRes=yres, targetAlignedPixels=True, coordinateOperation=gdal_warp_concatenated_transform)
    # remove whitespace formatting used in proj pipeline string and put it in GeoTIFF metadata
    gdal_warp_concatenated_transform = re.sub(r'\s{2,}', ' ', gdal_warp_concatenated_transform).strip()
    ds.SetMetadataItem('TIFFTAG_IMAGEDESCRIPTION', gdal_warp_concatenated_transform)

    # execute the transformation from the vrt dataset to output compressed tif
    output_ds = gdal.Translate(output_file, ds, format="GTiff", outputType=gdal.GDT_Float32, creationOptions=["COMPRESS=DEFLATE", "TILED=YES"])
    output_ds = None    
    return




if __name__ == "__main__":
    files = glob.glob(r"C:\Users\mohammad.ashkezari\Documents\projects\vyperdatum\untrack\data\raster\NC\Original\**\*.tif", recursive=True)
    files = glob.glob(r"C:\Users\mohammad.ashkezari\Documents\projects\vyperdatum\untrack\data\raster\RSD\MD\Original\**\*.tif", recursive=True)
    files = [r"C:\Users\mohammad.ashkezari\Desktop\test\Original\clip_NC.tif"]



    crs_from = "EPSG:6347"
    crs_to = "EPSG:6347+NOAA:98"

    files = [r"C:\Users\mohammad.ashkezari\Documents\projects\vyperdatum\untrack\data\raster\NC\Original\VA1803-TB-C_BLK-01\VA1803-TB-C_BLK-01_US4VA1FD_ellipsoidal_dem_b1.tif"]

    for i, input_file in enumerate(files[:]):
        print(f"{i+1}/{len(files)}: {input_file}")
        transform_with_vyperdatum(input_file, crs_from, crs_to)

        ###########################
        # try:
        #     output_file = input_file.replace("Original", "Manual")
        #     Path(os.path.split(output_file)[0]).mkdir(parents=True, exist_ok=True)
        #     # transform_with_concat_pipe(input_file, output_file)
        #     # nad83_transform_with_concat_pipe(input_file, output_file)
        #     transform_with_concat_steps(input_file, output_file)

        #     update_raster_wkt(output_file, pp.CRS(crs_to).to_wkt())
        #     input_metadata, output_metadata = raster_metadata(input_file), raster_metadata(output_file)
        #     passed, cross_df = vdatum_cross_validate(s_wkt=input_metadata["wkt"],
        #                                              t_wkt=output_metadata["wkt"],
        #                                              n_sample=20,
        #                                              s_raster_metadata=input_metadata,
        #                                              t_raster_metadata=output_metadata,
        #                                              s_point_samples=None,
        #                                              t_point_samples=None,
        #                                              tolerance=0.3,
        #                                              raster_sampling_band=1,
        #                                              region=None,
        #                                              pivot_h_crs="EPSG:6318",
        #                                              s_h_frame=None,
        #                                              s_v_frame=None,
        #                                              s_h_zone=None,
        #                                              t_h_frame=None,
        #                                              t_v_frame=None,
        #                                              t_h_zone=None
        #                                              )

        #     # if not passed:
        #     cross_df.to_csv(Path(output_file).parent.absolute()/Path(f"{os.path.split(input_file)[1]}_vdatum_check.csv"), index=False)
        # except Exception as e:
        #         efile = open(Path(output_file).parent.absolute()/Path(f"{os.path.split(input_file)[1]}_error.txt"), "w")
        #         efile.write(str(e))
        #         efile.close()

        ###########################

        print(f'\n{"*"*50} {i+1}/{len(files)} Completed {"*"*50}\n')
