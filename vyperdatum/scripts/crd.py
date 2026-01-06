import os
import pathlib
from osgeo import gdal
import glob
from vyperdatum.transformer import Transformer
from vyperdatum.utils.raster_utils import raster_metadata, update_raster_wkt
from vyperdatum.utils.vdatum_rest_utils import vdatum_cross_validate
import pyproj as pp
from pyproj import CRS, database
import math


def get_corresponding_utm_epsg(state_plane_code: str) -> str:
    """
    Given a State Plane CRS in 'AUTH:CODE' format (e.g., 'EPSG:2286'),
    returns the best matching UTM EPSG code based on extent and datum.
    Includes logging and fallback to common matches like EPSG:26910.
    """
    crs = CRS.from_user_input(state_plane_code)

    # Determine central point
    area = crs.area_of_use
    lon_center = (area.west + area.east) / 2
    lat_center = (area.south + area.north) / 2

    utm_zone = math.floor((lon_center + 180) / 6) + 1
    hemisphere = 'north' if lat_center >= 0 else 'south'

    print(f"Input CRS: {state_plane_code}")
    print(f"Estimated UTM zone: {utm_zone}, hemisphere: {hemisphere}")
    print(f"Datum: {crs.datum.name}")

    sp_datum = crs.datum.name.lower()

    candidates = []

    for info in database.query_crs_info(auth_name="EPSG"):
        name_lc = info.name.lower()
        if "utm zone" in name_lc and f"zone {utm_zone}" in name_lc and hemisphere in name_lc:
            try:
                utm_crs = CRS.from_authority(info.auth_name, info.code)
                utm_datum = utm_crs.datum.name.lower()

                print(f"Checking: {info.auth_name}:{info.code} | {utm_crs.name} | Datum: {utm_crs.datum.name}")

                if sp_datum in utm_datum or utm_datum in sp_datum:
                    print(f"Match found: {info.auth_name}:{info.code}")
                    return f"{info.auth_name}:{info.code}"
                else:
                    candidates.append((info.auth_name, info.code, utm_crs.datum.name))
            except Exception as e:
                continue

    print("No perfect datum match found.")
    print("Closest candidates:")
    for auth, code, datum in candidates:
        print(f"  - {auth}:{code} (Datum: {datum})")

    # Manual fallback: NAD83 / UTM zone 10N
    if utm_zone == 10 and hemisphere == 'north':
        print("Falling back to EPSG:26910 (NAD83 / UTM zone 10N)")
        return "EPSG:26910"

    return f"No matching UTM CRS found for {state_plane_code} (zone {utm_zone}, {hemisphere})"




def to_utm10(target_crs: str, input_tif: str, output_tif: str) -> None:
    src_ds = gdal.Open(input_tif)
    if src_ds is None:
        raise RuntimeError(f"Failed to open input file: {input_tif}")
    gdal.Warp(
        destNameOrDestDS=output_tif,
        srcDSOrSrcDSTab=src_ds,
        dstSRS=target_crs,
        format='GTiff',
        resampleAlg='bilinear',  # or nearest/cubic
        creationOptions=['COMPRESS=DEFLATE', 'TILED=YES']
    )
    return


if __name__ == "__main__":
    parent_dir = r"C:\Users\mohammad.ashkezari\Documents\projects\vyperdatum\untrack\data\raster\CRD\Original\**\*.tif"
    files = glob.glob(parent_dir, recursive=True)[:]
    files = [r"C:\Users\mohammad.ashkezari\Documents\projects\vyperdatum\untrack\data\raster\CRD\Original\or2014_usace_ncmp_or_dem_J1233315\or2014_usace_ncmp_or_dem_J1233315tR0_C0.tif"]
    for i, input_file in enumerate(files):
        print(f"{i+1}/{len(files)}: {input_file}")
        meta = raster_metadata(input_file)
        crs_from = f"{meta['h_authcode']}+EPSG:5703"
        crs_from = f"EPSG:6339+EPSG:5703"
        crs_to = f"EPSG:6339+NOAA:101"
        tf = Transformer(crs_from=crs_from,
                         crs_to=crs_to
                         )
        output_file = input_file.replace("Original", "Manual")
        tf.transform_raster(input_file=input_file,
                            output_file=output_file,
                            overview=False,
                            pre_post_checks=True,
                            vdatum_check=False
                            )
        print(f'\n{"*"*50} {i+1}/{len(files)} Completed {"*"*50}\n')
