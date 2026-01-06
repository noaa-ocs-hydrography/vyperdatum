import os
import rasterio
from rasterio.transform import Affine
from rasterio.crs import CRS
import numpy as np
import glob
import pathlib
from osgeo import gdal

gdal.UseExceptions()

def create_geotiff_from_tif_tfw(tif_path, tfw_path, output_path, epsg_code, nodata):
    """
    Creates a georeferenced GeoTIFF from a TIFF and its world file (.tfw).

    Parameters:
        tif_path (str): Path to the .tif image file.
        tfw_path (str): Path to the .tfw world file.
        output_path (str): Path to write the output GeoTIFF.
        epsg_code (int): EPSG code representing the CRS.
        nodata (float or int): NoData value to set in the output file.

    Returns:
        output_path (str): Path to the generated GeoTIFF.
    """
    # Read the .tfw world file
    with open(tfw_path, 'r') as f:
        A = float(f.readline())
        D = float(f.readline())
        B = float(f.readline())
        E = float(f.readline())
        C = float(f.readline())
        F = float(f.readline())

    transform = Affine(A, B, C, D, E, F)
    crs = CRS.from_epsg(epsg_code)

    with rasterio.open(tif_path) as src:
        data = src.read()
        profile = src.profile.copy()
        profile.update({
            'transform': transform,
            'crs': crs,
        })

        # if nodata is not None:
        #     profile.update({'nodata': nodata})

        with rasterio.open(output_path, 'w', **profile) as dst:
            dst.write(data)

    update_stats(output_path)
    return output_path


def update_stats(input_file):
    """
    Update statistics for the raster file.

    Parameters:
        input_file (str): Path to the raster file.
    """
    ds = gdal.Open(input_file, gdal.GA_Update)
    for i in range(1, ds.RasterCount + 1):
        ds.GetRasterBand(i).ComputeStatistics(False)
    ds = None  # flush
    return

files = glob.glob(r"C:\Users\mohammad.ashkezari\Documents\projects\vyperdatum\untrack\data\raster\ALK\Original\**\*.tif", recursive=True)
files = glob.glob(r"C:\Users\mohammad.ashkezari\Documents\projects\vyperdatum\untrack\data\raster\ALK\Manual2\**\*.tif", recursive=True)

for i, input_file in enumerate(files[:]):
    print(f"{i+1}/{len(files)}: {input_file}")
    update_stats(input_file)
    # output_file = input_file.replace("Original", "Processed")
    # tfw_file = input_file.replace(".tif", ".tfw")
    # pathlib.Path(os.path.split(output_file)[0]).mkdir(parents=True, exist_ok=True)
    # create_geotiff_from_tif_tfw(input_file, tfw_file, output_file, 6337, -999999)