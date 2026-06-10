import requests
import logging
import time
import random
import numpy as np
import pandas as pd
from colorama import Fore, Style
from osgeo import gdal
from typing import Optional, Union
import pyproj as pp
from tqdm import tqdm
import difflib
from vyperdatum.enums import VDATUM


logger = logging.getLogger("root_logger")
gdal.UseExceptions()


def vdatum_transform_point(s_x, s_y, s_z, region,
                           s_h_frame, s_v_frame, s_h_zone,
                           t_h_frame, t_v_frame, t_h_zone,
                           s_v_goid="geoid18",
                           t_v_goid="geoid18",
                           ):
    """
    Call point transformation GET endpoint (/convert) of the Vdatum REST API.
    API docs: https://vdatum.noaa.gov/docs/services.html

    Parameters
    ----------
    s_x: float
        Source point longitude
    s_y: float
        Source point latitude
    s_z: float
        Source point height
    region: str
        Vdatum region name (e.g. ak, as, contiguous, gcnmi, prvi)
        https://vdatum.noaa.gov/docs/services.html#step140
    s_h_frame: str
        Source horizontal reference frame (e.g. NAD83_2011)
        https://vdatum.noaa.gov/docs/services.html#step150
    s_v_frame: str
        source vertical reference frame (e.g. NAVD88, PRVD02, MLLW)
        https://vdatum.noaa.gov/docs/services.html#step160
    t_h_frame: str
        Target horizontal reference frame (e.g. NAD83_2011)
        https://vdatum.noaa.gov/docs/services.html#step150
    t_v_frame: str
        Target vertical reference frame (e.g. NAVD88, PRVD02, MLLW)
        https://vdatum.noaa.gov/docs/services.html#step160
    s_v_goid: str
        Source vertical GEOID model (e.g. geoid18 (default), geoid12b,
        geoid12a, geoid09, geoid06, geoid03, geoid99, geoid96, egm2008,
        egm1996, egm1984, xgeoid16b, xgeoid17b, xgeoid18b, xgeoid19b,
        xgeoid20b)
    t_v_goid: str
        Target vertical GEOID model (e.g. geoid18 (default), geoid12b,
        geoid12a, geoid09, geoid06, geoid03, geoid99, geoid96, egm2008,
        egm1996, egm1984, xgeoid16b, xgeoid17b, xgeoid18b, xgeoid19b,
        xgeoid20b)

    Returns
    -------
    Optional[tuple]
        The transformed coordinates (lon, lat, height)
    Optional[dict]
        The complete vdatum response object
    """
    url = "https://vdatum.noaa.gov/vdatumweb/api/convert"
    params = dict(s_x=s_x, s_y=s_y, s_z=s_z, region=region,
                  s_h_frame=s_h_frame, s_v_frame=s_v_frame,
                  s_h_zone=s_h_zone if s_h_zone else "",
                  t_h_frame=t_h_frame, t_v_frame=t_v_frame,
                  t_h_zone=t_h_zone if t_h_zone else "",
                  s_v_goid=s_v_goid, t_v_goid=t_v_goid)
    # logger.debug(f"Parameter used to call Vdatum API:\n{params}\n")
    try:
        resp = requests.get(url, params=params, timeout=200).json()
        time.sleep(0.5)
    except Exception as e:
        logger.exception(f"VDatum API exception:\n{e}")
        return None, None
    return (float(resp.get("t_x", np.nan)),
            float(resp.get("t_y", np.nan)),
            float(resp.get("t_z", np.nan))), resp


def api_region_alias(vdatum_regions: list[str]):
    """
    Vdatum REST api uses different region names compared to those
    listed in the vdatum grids directory. This function expects to
    receive region name according to the vdatum grids directory and
    returns region name consistent with the vdatum REST api. Default
    output is `contiguous`.

    Parameters
    ------------
    region: list[str]
         Region name according to the vdatum grids directory.

    Returns
    ------------
    str
    """
    if not vdatum_regions:
        return "contiguous"
    api_region = set()
    for region in vdatum_regions:
        if region.startswith("AK"):
            api_region.add("ak")
        elif region.startswith("MD"):
            api_region.add("chesapeak_delaware")
        elif region.startswith("TX"):
            api_region.add("wgom")
        elif region.startswith("WA") or region.startswith("OR") or region.startswith("WC"):
            api_region.add("westcoast")
        elif region.startswith("PRVI"):
            api_region.add("prvi")

    if len(api_region) != 1:
        api_region = "contiguous"
    else:    
        api_region = api_region.pop()
    # Note: not all regions are covered here. For example, I do'nt know what is the Hawaii
    # region name is in vdatum grid directory (or as, sgi, spi, sli, gcnmi, wgom, ...).
    # looks like `westcoast` and `chesapeak_delaware` are not considered as part of `contiguous`?.
    # https://vdatum.noaa.gov/docs/services.html#step140
    return api_region


def wkt_to_utm(wkt: str) -> Optional[str]:
    """
    Receives WKT and returns the UTM zone, if applicable.

    Parameters
    ------------
    wkt: str
         WKT string

    Returns
    ------------
    Optional[str]
         UTM zone
    """
    zone = None
    input_crs = pp.CRS(wkt)
    if not input_crs.is_projected:
        return zone
    input_crs = input_crs.name.split("+")[0].strip()
    if len(input_crs.split("/ UTM zone ")) == 2:
        zone = input_crs.split("/ UTM zone ")[1].strip()
    return zone


def wkt_to_crs(wkt: str) -> tuple[Optional[str], Optional[str]]:
    """
    Receives WKT and returns the horizontal/vertical CRS names.

    Parameters
    ------------
    wkt: str
         WKT string

    Returns
    ------------
    tuple[Optional[str], Optional[str]]
         Horizontal and vertical CRS names, if identified.
    """
    input_crs = pp.CRS(wkt)
    if input_crs.is_compound:
        horizontal_crs = pp.CRS(input_crs.sub_crs_list[0])
        vertical_crs = pp.CRS(input_crs.sub_crs_list[1])
    else:
        horizontal_crs = input_crs
        vertical_crs = None
    return horizontal_crs.name, vertical_crs.name if vertical_crs else None


def api_crs_aliases(wkt: str) -> tuple[str, str]:
    """
    Vdatum REST api uses different CRS names compared to those
    of the PROJ/pyproj. This function expects to receive a CRS WKT
    and returns horizontal and vertical CRS names that are consumable
    by the vdatum REST api.


    Parameters
    ------------
    wkt: str
         WKT string.

    Returns
    ------------
    tuple[str, str]
        Horizontal and vertical CRS names that are consumable by the vdatum REST api.
    """
    h_crs, v_crs = wkt_to_crs(wkt)
    h_crs = h_crs.split("/")[0].strip()
    h_matches = difflib.get_close_matches(h_crs, VDATUM.H_FRAMES.value)
    if len(h_matches) == 0:
        logger.error(f"No Vdatum horizontal CRS name matched with '{h_crs}'")
    h_crs = h_matches[0]

    v_crs_black = ["HRD"]
    if v_crs and v_crs.split()[0].upper().strip() in v_crs_black:
        logger.error(f"The raster's vertical CRS is '{v_crs}' which is not covered by Vdatum.")

    if not v_crs:
        v_crs = h_crs
    else:
        v_matches = difflib.get_close_matches(v_crs, VDATUM.V_FRAMES.value)
        if len(v_matches) == 0:
            v_matches = difflib.get_close_matches(v_crs.split()[0].strip(), VDATUM.V_FRAMES.value)
        if len(v_matches) == 0:
            v_matches = difflib.get_close_matches(v_crs.split()[0].strip(), VDATUM.V_FRAMES.value)
            logger.error(f"No Vdatum vertical CRS name matched with '{v_crs}'")
        v_crs = v_matches[0]
    return h_crs, v_crs


def index_to_xy(i: int, j: int, geot: tuple):
    """
    Take indices of a raster's band array and return x, y.

    Parameters
    ----------
    i: int
        Raster's band array first index.
    j: int
        Raster's band array second index.
    geot: tuple
        Gdal GeoTransform tuple object.

    Returns
    ----------
    float, float
        easting, northing
    """
    res_x, res_y = geot[1], geot[5]
    x_min, y_max = geot[0], geot[3]
    x = j * res_x + x_min + (res_x / 2.0)
    y = i * res_y + y_max + (res_y / 2.0)
    return x, y


def sample_raster(source_meta: dict,
                  target_meta: dict,
                  n_sample: int,
                  sampling_band: int,
                  pivot_h_crs: Optional[str]
                  ) -> tuple[list, list]:
    """
    Randomly draw `n_samples` points (not NoDataValue) from the `sampling_band`
    of the source and target rasters.

    Parameters
    ----------
    source_meta: dict
        Source raster metadata generated by `raster_metadata` function.
    target_meta: dict
        Target raster metadata generated by `raster_metadata` function.
    n_sample: int
        The number of sample points (coordinates).
    sampling_band: dict
        The index of the source band to be sampled (default 1).
    pivot_h_crs: Optional[str]
        When not None, both source and target samples are transformed
        into a common horizontal CRS, otherwise ignored (default None).
        Example: pivot_h_crs = 'EPSG:6318'

    Raises
    -------
    ValueError:
        If there are less not-null values than `n_sample` in the target raster band.

    Returns
    ----------
    tuple[list, list]
        Returns `n_samples` points from the rasters in form of two lists of [x, y, sampled_value].
    """
    ds_source = gdal.Open(source_meta["path"])
    ds_target = gdal.Open(target_meta["path"])
    bar_source = ds_source.GetRasterBand(sampling_band).ReadAsArray()
    bar_target = ds_target.GetRasterBand(sampling_band).ReadAsArray()
    nodata_value = ds_target.GetRasterBand(sampling_band).GetNoDataValue()
    if np.count_nonzero(np.where(bar_target != nodata_value)) < n_sample:
        raise ValueError(f"Cannot sample {n_sample} from the target raster. Too many NoDataValue.")
    source_samples, target_samples = [], []
    c = 0
    while len(target_samples) < n_sample:
        c += 1
        if c > 1e6:
            raise ValueError(f"Failed to find {n_sample} sample points from the target raster.")
        i, j = np.random.choice(bar_target.shape[0]), np.random.choice(bar_target.shape[1])
        if bar_target[i, j] == nodata_value:
            continue
        x, y = index_to_xy(i, j, ds_target.GetGeoTransform())
        target_samples.append([x, y, bar_target[i, j]])

        source_geot = ds_source.GetGeoTransform()
        source_i = int((y - source_geot[3]) / source_geot[5])
        source_j = int((x - source_geot[0]) / source_geot[1])

        source_x, source_y = index_to_xy(source_i, source_j, ds_source.GetGeoTransform())
        source_samples.append([source_x, source_y, bar_source[source_i, source_j]])
    ds_source, ds_target = None, None
    if pivot_h_crs:
        source_crs_h, _ = wkt_to_crs(source_meta["wkt"])
        target_crs_h, _ = wkt_to_crs(target_meta["wkt"])
        source_transformer = pp.Transformer.from_crs(pp.CRS(source_crs_h),
                                                     pp.CRS(pivot_h_crs),
                                                     always_xy=True
                                                     )
        target_transformer = pp.Transformer.from_crs(pp.CRS(target_crs_h),
                                                     pp.CRS(pivot_h_crs),
                                                     always_xy=True
                                                     )
        for i, p in enumerate(source_samples):
            lon, lat = source_transformer.transform(p[0], p[1])
            p[0], p[1] = lon, lat
            lon, lat = target_transformer.transform(target_samples[i][0], target_samples[i][1])
            target_samples[i][0], target_samples[i][1] = lon, lat
    return source_samples, target_samples


def vdatum_cross_validate(s_wkt: str,
                          t_wkt: str,
                          n_sample: int,
                          s_raster_metadata: Optional[dict],
                          t_raster_metadata: Optional[dict],
                          s_point_samples: Optional[Union[list, np.ndarray]],
                          t_point_samples: Optional[Union[list, np.ndarray]],
                          tolerance: float = 0.3,
                          raster_sampling_band: int = 1,
                          region: Optional[str] = None,
                          pivot_h_crs: Optional[str] = None,
                          s_h_frame: Optional[str] = None,
                          s_v_frame: Optional[str] = None,
                          s_h_zone: Optional[str] = None,
                          t_h_frame: Optional[str] = None,
                          t_v_frame: Optional[str] = None,
                          t_h_zone: Optional[str] = None
                          ):
    """
    Randomly sample the source raster points and transform them to the
    target CRS using the vdatum API. Verify if the transformed values are
    consistent with the target raster values.

    Parameters
    ----------
    s_wkt: str
        WKT associated with the source data CRS.
    t_wkt: str
        WKT associated with the target data CRS.
    n_sample: int
        The number of sample points (coordinates).
    s_raster_metadata: Optional[dict]
        Source file metadata. This only applies to raster files; otherwise, None.
    t_raster_metadata: Optional[dict]
        Target file metadata. This only applies to raster files; otherwise, None.
    s_point_samples: Optional[Union[list, numpy.ndarray]]
        Lists of source sample points in form of [x, y, sampled_value].
        This parameter only applies to point transformations(not raster); otherwise, None.
    t_point_samples: Optional[Union[list, numpy.ndarray]]
        Lists of source sample points in form of [x, y, sampled_value].
        This parameter only applies to point transformations(not raster); otherwise, None.
    tolerance: float
        Maximum elevation deviation [m] between transformations conducted by Vyperdatum
        compared with Vdatum.
    raster_sampling_band: dict
        The index of the source raster file band to be sampled (default 1). Only applies to
        raster file inputs.
    region: Optional[str]
        Vdatum region name (e.g. ak, as, contiguous, gcnmi, prvi)
        https://vdatum.noaa.gov/docs/services.html#step140
    pivot_h_crs: Optional[str]
        When not None, both source and target samples are transformed
        into a common horizontal CRS, otherwise ignored (default None).
        Example: pivot_h_crs = 'EPSG:6318'
    s_h_frame: Optional[str]
        Source horizontal reference frame (e.g. NAD83_2011)
        https://vdatum.noaa.gov/docs/services.html#step150
    s_v_frame: Optional[str]
        source vertical reference frame (e.g. NAVD88, PRVD02, MLLW)
        https://vdatum.noaa.gov/docs/services.html#step160
    s_h_zone: Optional[str]
        source CRS zone, if projected.
        The details of this parameter is not documented in vdatum services page.
    t_h_frame: Optional[str]
        Target horizontal reference frame (e.g. NAD83_2011)
        https://vdatum.noaa.gov/docs/services.html#step150
    t_v_frame: Optional[str]
        Target vertical reference frame (e.g. NAVD88, PRVD02, MLLW)
        https://vdatum.noaa.gov/docs/services.html#step160
    t_h_zone: Optional[str]
        Target CRS zone, if projected.
        The details of this parameter is not documented in vdatum services page.

    Returns
    ----------
    bool
        True if all checks pass, otherwise False.
    pandas.DataFrame
        Dataframe containing the sampled input, transferred, and vdatum points.
    """
    # source_meta = raster_metadata(s_file)
    # target_meta = raster_metadata(t_file)
    # s_wkt = source_meta["wkt"]
    # t_wkt = target_meta["wkt"]

    passed = True
    if not region:
        overlapping_regions = t_raster_metadata.get("overlapping_regions") if s_raster_metadata else None
        region = api_region_alias(overlapping_regions)
        # if len(s_raster_metadata["overlapping_regions"]) != 1:
        #     logger.warning("The input is not overlapping with a single region."
        #                    f" The overlapping regions: ({s_raster_metadata['overlapping_regions']})."
        #                    " The Vdatum API region will be set to 'contiguous'.")
            

    source_crs_h, source_crs_v = wkt_to_crs(s_wkt)
    source_zone_h = wkt_to_utm(s_wkt)
    target_crs_h, target_crs_v = wkt_to_crs(t_wkt)
    target_zone_h = wkt_to_utm(t_wkt)
    s_h_zone = s_h_zone if s_h_zone else source_zone_h
    t_h_zone = t_h_zone if t_h_zone else target_zone_h
    if pivot_h_crs:
        s_h_zone, t_h_zone = None, None

    api_src_crs_h, api_src_crs_v = api_crs_aliases(s_wkt)
    source_crs_h = s_h_frame if s_h_frame else api_src_crs_h
    source_crs_v = s_v_frame if s_v_frame else api_src_crs_v
    api_tgt_crs_h, api_tgt_crs_v = api_crs_aliases(t_wkt)
    target_crs_h = t_h_frame if t_h_frame else api_tgt_crs_h
    target_crs_v = t_v_frame if t_v_frame else api_tgt_crs_v

    if s_raster_metadata and t_raster_metadata:  # in the case of raster file inputs
        logger.info(f"Taking {n_sample} random sample{'s' if n_sample > 1 else ''} "
                    "from the source and transformed rasters ...")
        source_samples, target_samples = sample_raster(s_raster_metadata,
                                                       t_raster_metadata,
                                                       n_sample,
                                                       raster_sampling_band,
                                                       pivot_h_crs=pivot_h_crs
                                                       )
    else:
        random_idx = random.sample(range(len(s_point_samples)), n_sample)
        source_samples = [list(s_point_samples[i]) for i in random_idx]
        target_samples = [list(t_point_samples[i]) for i in random_idx]

    vdatum_points, vdatum_resp = [], []
    cross_df = pd.DataFrame({})
    logger.info("Calling Vdatum API ...")
    for p in tqdm(source_samples):
        points, resp = vdatum_transform_point(s_x=p[0], s_y=p[1], s_z=p[2],
                                              region=region,
                                              s_h_frame=s_h_frame or source_crs_h,
                                              s_v_frame=s_v_frame or source_crs_v,
                                              s_h_zone=s_h_zone,
                                              t_h_frame=t_h_frame or target_crs_h,
                                              t_v_frame=t_v_frame or target_crs_v,
                                              t_h_zone=t_h_zone)
        if points:
            vdatum_points.append(points)
            vdatum_resp.append(resp)
        else:
            vdatum_points.append((None, None, None))
            vdatum_resp.append({})
    cross_df = pd.DataFrame({"src_x": [p[0] for p in source_samples],
                             "src_y": [p[1] for p in source_samples],
                             "src_val": [p[2] for p in source_samples],
                             "tgt_x": [p[0] for p in target_samples],
                             "tgt_y": [p[1] for p in target_samples],
                             "tgt_val": [p[2] for p in target_samples],
                             "vdatum_x": [p[0] for p in vdatum_points],
                             "vdatum_y": [p[1] for p in vdatum_points],
                             "vdatum_val": [p[2] for p in vdatum_points],
                             "vdatum_resp": [str(r) for r in vdatum_resp],
                             })
    try:
        # remove vdatum outlier/erroneous responses
        cross_df = cross_df.query("abs(vdatum_val)<10000")
        if len(cross_df) == 0:
            passed = False
        cross_df = cross_df.assign(deviation=cross_df["tgt_val"] - cross_df["vdatum_val"])
        deviation = cross_df["deviation"].abs().mean()
        std = cross_df["deviation"].abs().std()
        if deviation > tolerance:
            logger.warning(f"{Fore.RED}The deviation between the transferred values produced by "
                           f"Vyperdatum and Vdatum is {deviation:.2f} {chr(0x00b1)} {std:.2f} [m]"
                           f" exceeding the threshold {tolerance} [m].")
            passed = False
        elif deviation != deviation:
            logger.warning(f"{Fore.RED}The deviation between the transferred values produced by "
                           f"Vyperdatum and Vdatum is ambiguous (nan).")
            passed = False
        else:
            logger.warning(f"{Fore.GREEN}The deviation between the transferred values produced by "
                           f"Vyperdatum and Vdatum is {deviation:.2f} {chr(0x00b1)} {std:.2f} [m],"
                           f" below the threshold {tolerance} [m].")
        print(Style.RESET_ALL)
    except Exception as e:
        logger.exception(f"Exception in Vdatum deviation calculation:\n{e}")
        passed, cross_df = False, pd.DataFrame({})
    return passed, cross_df
