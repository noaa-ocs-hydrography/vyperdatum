import os
import glob
import logging
from typing import Optional, Union
import pandas as pd
from osgeo import gdal, ogr
from vyperdatum.db import DB


logger = logging.getLogger("root_logger")
gdal.UseExceptions()


def get_grid_list(vdatum_directory: str):
    """
    Return all gtx files in the vdatum directory.

    Parameters
    ----------
    vdatum_directory
        absolute folder path to the vdatum directory

    Returns
    -------
    dict
        dictionary of {grid name: grid path, ...}
    list
        list of vdatum regions
    """
    grid_formats = [".tif", ".tiff", ".gtx"]
    grid_list = []
    for gfmt in grid_formats:
        search_path = os.path.join(vdatum_directory, "*/*{}".format(gfmt))
        grid_list += glob.glob(search_path)
    if len(grid_list) == 0:
        logger.error(f"No grid files found in the provided VDatum directory: {vdatum_directory}")
    grids = {}
    regions = []
    for grd in grid_list:
        grd_path, grd_file = os.path.split(grd)
        grd_path, grd_folder = os.path.split(grd_path)
        gtx_name = "/".join([grd_folder, grd_file])
        gtx_subpath = os.path.join(grd_folder, grd_file)
        grids[gtx_name] = gtx_subpath
        regions.append(grd_folder)
    regions = list(set(regions))
    return grids, regions


def get_region_polygons(datums_directory: str, extension: str = "kml") -> dict:
    """"
    Search the datums directory to find all geometry files.
    All datums are assumed to reside in a subfolder.

    Parameters
    ----------
    datums_directory : str
        absolute folder path to the vdatum directory

    extension : str
        the geometry file extension to search for

    Returns
    -------
    dict
        dictionary of {kml name: kml path, ...}
    """

    search_path = os.path.join(datums_directory, f"*/*.{extension}")
    geom_list = glob.glob(search_path)
    if len(geom_list) == 0:
        logger.error(f"No {extension} files found in the provided directory: {datums_directory}")
    geom = {}
    for filename in geom_list:
        geom_path, _ = os.path.split(filename)
        _, geom_name = os.path.split(geom_path)
        geom[geom_name] = filename
    return geom


def overlapping_regions(datums_directory: str,
                        lon_min: float,
                        lat_min: float,
                        lon_max: float,
                        lat_max: float
                        ) -> list[str]:
    """
    Return the region names that intersect with the provided bound.
    The input coordinate reference system is expected to be
    NAD83(2011) geographic.

    Parameters
    ----------
    lon_min
        the minimum longitude of the area of interest
    lat_min
        the minimum latitude of the area of interest
    lon_max
        the maximum longitude of the area of interest
    lat_max
        the maximum latitude of the area of interest

    Returns
    ----------
    list[str]
    """
    assert lon_min < lon_max
    assert lat_min < lat_max

    # build corners from the provided bounds
    ul = (lon_min, lat_max)
    ur = (lon_max, lat_max)
    lr = (lon_max, lat_min)
    ll = (lon_min, lat_min)

    # build polygon from corners
    ring = ogr.Geometry(ogr.wkbLinearRing)
    ring.AddPoint(ul[0], ul[1])
    ring.AddPoint(ur[0], ur[1])
    ring.AddPoint(lr[0], lr[1])
    ring.AddPoint(ll[0], ll[1])
    ring.AddPoint(ul[0], ul[1])
    data_geometry = ogr.Geometry(ogr.wkbPolygon)
    data_geometry.AddGeometry(ring)

    # see if the regions intersect with the provided geometries
    intersecting_regions = []
    polygon_files = get_region_polygons(datums_directory)
    for region in polygon_files:
        vector = ogr.Open(polygon_files[region])
        layer_count = vector.GetLayerCount()
        # found = False
        for m in range(layer_count):
            layer = vector.GetLayerByIndex(m)
            feature_count = layer.GetFeatureCount()
            for n in range(feature_count):
                feature = layer.GetNextFeature()
                try:
                    feature_name = feature.GetField(0)
                except AttributeError:
                    logger.warning("WARNING: Unable to read feature name from feature"
                                   f"in layer in {polygon_files[region]}"
                                   )
                    continue
                if isinstance(feature_name, str):
                    if feature_name[:15] == "valid-transform":
                        valid_vdatum_poly = feature.GetGeometryRef()
                        if data_geometry.Intersect(valid_vdatum_poly):
                            intersecting_regions.append(region)
                            # found = True
                feature = None
            layer = None
        # if not found and region in self.datum_data.extended_region:
        #     feature = vector.GetLayerByIndex(0).GetFeature(0)
        #     if data_geometry.Intersect(feature.GetGeometryRef()):
        #         intersecting_regions.append(region)
        vector = None
    return intersecting_regions


def overlapping_extents(lon_min: float,
                        lat_min: float,
                        lon_max: float,
                        lat_max: float
                        ) -> Union[Optional[list], Optional[pd.DataFrame]]:
    """
    Return database predefined extents that intersect with an area of interest.
    The results are sorted by coverage ratios.

    Parameters
    ----------
    lon_min
        the minimum longitude of the area of interest
    lat_min
        the minimum latitude of the area of interest
    lon_max
        the maximum longitude of the area of interest
    lat_max
        the maximum latitude of the area of interest
    """

    sql = f"""
    with data_extent AS (
        SELECT {lon_min} as min_lon,
               {lon_max} as max_lon,
               {lat_min} as min_lat,
               {lat_max} as max_lat
        )
    select *,

    -- ratio of data covered by a database extent:
    -- intersecting area of data and database extent divided by data area
    (
    (
    (min(data_extent.max_lon, east_lon) - max(data_extent.min_lon, west_lon))
    *
    (min(data_extent.max_lat, north_lat) - max(data_extent.min_lat, south_lat))
    ) / ((data_extent.max_lon-data_extent.min_lon) * (data_extent.max_lat-data_extent.min_lat)) 
    )
    as data_coverage_ratio,


    -- ratio of a database extent covered by data:
    -- intersecting area of data and database extent divided by the database extent area
    (
    (
    (min(data_extent.max_lon, east_lon) - max(data_extent.min_lon, west_lon))
    *
    (min(data_extent.max_lat, north_lat) - max(data_extent.min_lat, south_lat))
    ) / ((east_lon-west_lon) * (north_lat-south_lat)) 
    )
    as extent_coverage_ratio

    from extent, data_extent
    where
    east_lon >= data_extent.min_lon
    and west_lon <= data_extent.max_lon
    and north_lat >= data_extent.min_lat
    and south_lat <= data_extent.max_lat
    and deprecated = 0
    order by data_coverage_ratio desc,
             extent_coverage_ratio desc,
             (abs(east_lon - west_lon) * abs(north_lat - south_lat))
    """

    return DB().query(sql, dataframe=True)
