import os
import pathlib
import logging
import json
import tempfile
from osgeo import gdal
import numpy as np
from typing import Union, Optional
import pyproj as pp
from vyperdatum.utils.spatial_utils import overlapping_regions, overlapping_extents
from vyperdatum.utils.crs_utils import commandline, pipeline_string, crs_components
from vyperdatum.enums import VDATUM
from vyperdatum.utils import crs_utils

logger = logging.getLogger("root_logger")
gdal.UseExceptions()


def band_stats(band_array: np.ndarray) -> list:
    """
    Return a list containing the min, max, mean, and std of the band array.

    Parameters
    ----------
    band_array: numpy.ndarray
        raster band array

    Returns:
    --------
    list:
        min, max, mean, and std of the band array.
    """
    return [np.nanmin(band_array), np.nanmax(band_array),
            np.nanmean(band_array), np.nanstd(band_array)]


def raster_metadata(raster_file: str, verbose: bool = False) -> dict:
    try:
        metadata = {}
        ds = gdal.Open(raster_file, gdal.GA_ReadOnly)
        srs = ds.GetSpatialRef()
        gdal_metadata = ds.GetMetadata()
        metadata |= {"path": raster_file}
        metadata |= {"description": ds.GetDescription()}
        metadata |= {"driver": ds.GetDriver().ShortName}
        metadata |= {"bands": ds.RasterCount}
        metadata |= {"dimensions": f"{ds.RasterXSize} x {ds.RasterYSize}"}
        metadata |= {"band_no_data": [ds.GetRasterBand(i+1).GetNoDataValue()
                                      for i in range(ds.RasterCount)]}
        metadata |= {"block_size": [ds.GetRasterBand(i+1).GetBlockSize()
                                      for i in range(ds.RasterCount)]}
        metadata |= {"band_descriptions": [ds.GetRasterBand(i+1).GetDescription()
                                           for i in range(ds.RasterCount)]}
        # metadata |= {"band_stats": [band_stats(ds.GetRasterBand(i+1).ReadAsArray())
        #                             for i in range(ds.RasterCount)]}
        metadata |= {"compression": ds.GetMetadata("IMAGE_STRUCTURE").get("COMPRESSION", None)}
        metadata |= {"Vyperdatum_Metadata": json.loads(gdal_metadata.get("Vyperdatum_Metadata", "{}"))}
        metadata |= {"coordinate_epoch": srs.GetCoordinateEpoch()}
        geot = ds.GetGeoTransform()
        res_x, res_y = geot[1], geot[5]
        x_min, y_max = geot[0], geot[3]
        x_max = x_min + res_x * ds.RasterXSize
        y_min = y_max + res_y * ds.RasterYSize
        metadata |= {"geo_transform": geot}
        metadata |= {"extent": [x_min, y_min, x_max, y_max]}
        metadata |= {"resolution": [res_x, res_y]}
        metadata |= {"wkt": srs.ExportToWkt()}
        input_crs = pp.CRS(metadata["wkt"])
        h_ac, v_ac = crs_components(crs=input_crs, raise_no_auth=False)
        metadata |= {"h_authcode": h_ac}
        metadata |= {"v_authcode": v_ac}
        ds = None

        if input_crs.is_compound:
            input_horizontal_crs = pp.CRS(input_crs.sub_crs_list[0])
            input_vertical_crs = pp.CRS(input_crs.sub_crs_list[1])
        else:
            input_horizontal_crs = input_crs
            input_vertical_crs = None

        transformer = pp.Transformer.from_crs(input_horizontal_crs,
                                              "EPSG:6318",
                                              always_xy=True
                                              )
        [[lon_min, lon_max], [lat_min, lat_max]] = transformer.transform([x_min, x_max],
                                                                         [y_min, y_max])
        metadata |= {"geo_extent": [lon_min, lat_min, lon_max, lat_max]}
        metadata |= {"overlapping_regions": overlapping_regions(VDATUM.DIR.value, *metadata["geo_extent"])}
        metadata |= {"overlapping_extents": overlapping_extents(*metadata["geo_extent"])}
        metadata |= {"info": gdal.Info(raster_file, format="json")}

    except Exception as e:
        logger.exception(f"Unable to get raster metadata: {e}")

    if verbose:
        print(f"{'-'*80}\nFile: {pathlib.Path(raster_file).name}"
              f"\n\tInput CRS: {input_crs.name}"
              f"\n\tInput Horizontal Authority: {input_horizontal_crs.to_authority()}"
              f"\n\tInput Vertical Authority: {input_vertical_crs.to_authority() if input_crs.is_compound else None}"
              f"\n\tInput Vertical CRS: {input_vertical_crs if input_crs.is_compound else None}"
              f"\n\tInput Vertical CRS WKT: {input_vertical_crs.to_wkt() if input_crs.is_compound else None}"
              f"\n{'-'*80}\n"
              )
    return metadata


def add_overview(raster_file: str, compression: str = "", embedded: bool = True) -> None:
    """
    Add overview bands to a raster file with no existing overviews.

    parameters
    ----------
    raster_file: str
        Absolute full path to the raster file.
    compression: str
        The name of compression algorithm.
    embedded: bool, default=True
        If True, the overviews will be embedded in the file, otherwise stored externally.
    """
    try:
        ds = gdal.Open(raster_file, gdal.GA_Update if embedded else gdal.GA_ReadOnly)
        if compression:
            gdal.SetConfigOption("COMPRESS_OVERVIEW", compression)
    finally:
        ds.BuildOverviews("NEAREST", [2, 4, 16], gdal.TermProgress_nocb)
        ds = None
    return


def add_rat(raster: str) -> None:
    """
    Add Raster Attribute Table (RAT) to all bands of a raster file.

    parameters
    ----------
    raster_file: str
        Absolute full path to the raster file.
    """
    ds = gdal.Open(raster)
    for i in range(ds.RasterCount):
        rat = gdal.RasterAttributeTable()
        rat.CreateColumn("VALUE", gdal.GFT_Real, gdal.GFU_Generic)
        rat.CreateColumn("COUNT", gdal.GFT_Integer, gdal.GFU_Generic)
        band = ds.GetRasterBand(i+1)
        unique, counts = np.unique(band.ReadAsArray(), return_counts=True)
        for i in range(len(unique)):
            rat.SetValueAsDouble(i, 0, float(unique[i]))
            rat.SetValueAsInt(i, 1, int(counts[i]))
        band.SetDefaultRAT(rat)
    ds = None
    return


def set_nodatavalue(raster_file: str,
                    band_nodatavalue: Union[list[tuple[int, float]], float],
                    ) -> None:
    """
    Change the NoDataValue of the raster file bands.

    parameters
    ----------
    raster_file: str
        Absolute full path to the raster file.
    band_nodatavalue: Union[list[tuple[int, float]], float]
        A list of tuples: (band_index, NoDataValue).
        If a single float is passed, all bands will be affected.
    """
    if isinstance(band_nodatavalue, float):
        ds = gdal.Open(raster_file)
        band_nodatavalue = [(b, band_nodatavalue) for b in range(1, ds.RasterCount+1)]
        ds = None
    ds = gdal.Open(raster_file, gdal.GA_Update)
    for b, nodv in band_nodatavalue:
        band = ds.GetRasterBand(b)
        bar = band.ReadAsArray()
        bar[np.where(bar == band.GetNoDataValue())] = nodv
        band.WriteArray(bar)
        ds.GetRasterBand(b).SetNoDataValue(nodv)
        band = None
    ds = None
    return


def unchanged_to_nodata(src_raster_file: str,
                        xform_raster_file: str,
                        xform_band: int,
                        ) -> None:
    """
    Compare the `xform_band` values of the `src_raster_file` and `xform_raster_file`.
    Change the values to NoDataValue if the transformed value is the same as the
    original value (indicating that the transformation has failed).
    Currentl, PROJ keep the source raster unchanged when fails to apply the transformation.
    The transformation fails when the source data is outside any of the underlying
    transformation grids. This function is meant to replace the failed transformation
    points with NoDataValue.  

    parameters
    ----------
    src_raster_file: str
        Absolute full path to the source raster file.
    xform_raster_file: str
        Absolute full path to the transformed raster file.
    xform_band: int
        The reference band index that is used for comparison between the source and transformed file.
    """
    src_ds = gdal.Open(src_raster_file)
    xform_ds = gdal.Open(xform_raster_file, gdal.GA_Update)
    src_band = src_ds.GetRasterBand(xform_band)
    xform_band = xform_ds.GetRasterBand(xform_band)
    ndv = src_band.GetNoDataValue()
    sar, xar = src_band.ReadAsArray(), xform_band.ReadAsArray()
    unchanged_mask = np.where(np.abs(sar - xar) < 0.01)
    src_band, xform_band = None, None
    for b in range(1, xform_ds.RasterCount+1):
        band = xform_ds.GetRasterBand(b)
        bar = band.ReadAsArray()
        bar[unchanged_mask] = ndv
        band.WriteArray(bar)
        xform_ds.GetRasterBand(b).SetNoDataValue(ndv)
        band = None
    src_ds, xform_ds = None, None
    return


def raster_compress(raster_file_path: str,
                    output_file_path: str,
                    format: str,
                    compression: str
                    ):
    """
    Compress raster file.

    Parameters
    ----------
    raster_file_path: str
        absolute path to the input raster file.
    output_file_path: str
        absolute path to the compressed output raster file.
    format: str
        raster file format.
    compression: str
        compression algorithm.
    """
    translate_kwargs = {"format": format,
                        "creationOptions": [f"COMPRESS={compression}"]
                        }
    gtiff_co = [f"BIGTIFF={'YES' if os.path.getsize(raster_file_path) > 3e9 else 'IF_NEEDED'}",
                "TILED=YES"]

    if format.lower() == "gtiff":
        translate_kwargs["creationOptions"].extend(gtiff_co)
    gdal.Translate(output_file_path, raster_file_path, **translate_kwargs)
    return


def preserve_raster_size(input_file: str,
                         output_file: str
                         ):
    """
    Resize the `output_file` raster dimensions to those of the input `input_file`.

    Parameters
    ----------
    input_file: str
        absolute path to the input raster file.
    output_file: str
        absolute path to the compressed output raster file.
    """
    ds_in = gdal.Open(input_file)
    ds_out = gdal.Open(output_file)
    w_in, h_in = ds_in.RasterXSize, ds_in.RasterYSize
    w_out, h_out = ds_out.RasterXSize, ds_out.RasterYSize
    ds_in, ds_out = None, None
    if w_in != w_out or h_in != h_out:
        output_file_copy = str(output_file)+".tmp"
        os.rename(output_file, output_file_copy)
        gdal.Translate(output_file, output_file_copy, width=w_in, height=h_in)
        os.remove(output_file_copy)
    return


def crs_to_code_auth(crs: pp.CRS) -> Optional[str]:
    """
    Return CRS string representation in form of code:authority

    Raises
    -------
    ValueError:
        If either code or authority of the crs (or its sub_crs) can not be determined.

    Returns
    --------
    str:
        crs string in form of code:authority
    """
    def get_code_auth(_crs: pp.CRS):
        if _crs.to_authority(min_confidence=100):
            return ":".join(_crs.to_authority(min_confidence=100))
        raise ValueError(f"Unable to produce authority name and code for this crs:\n{_crs}")

    if crs.is_compound:
        hcrs = pp.CRS(crs.sub_crs_list[0])
        vcrs = pp.CRS(crs.sub_crs_list[1])
        code_auth = f"{get_code_auth(hcrs)}+{get_code_auth(vcrs)}"
    else:
        code_auth = get_code_auth(crs)
    return code_auth


def push_pop_at_vshift(pipe: str) -> str:
    """
    Sandwich the vgrid_shift operation with push/pop of the horizontal CRS components.

    Parameters
    ----------
    pipe: proj pipeline string.
    """
    horz_push = " +step +proj=push +v_1 +v_2 "
    horz_pop = " +step +proj=pop +v_1 +v_2 "

    vgird_delim = "+step +inv +proj=vgridshift"
    vgrid_splits = pipe.split(vgird_delim)
    if len(vgrid_splits) != 2:
        raise ValueError(f"Pipeline split by '{vgird_delim}' must result in "
                         f"exactly 2 parts but got {len(vgrid_splits)} parts:\n {vgrid_splits}")
    hydroid_delim = ".tif"
    hydroid_splits = vgrid_splits[-1].split(hydroid_delim)

    sand_pipe = vgrid_splits[0] + horz_push + vgird_delim + " " + (hydroid_delim + " ").join(hydroid_splits[:-1]) + hydroid_delim + " "

    step_delim = "+step"
    step_splits = hydroid_splits[-1].split(step_delim)

    sand_pipe += step_splits[0] + horz_pop + step_delim + step_delim.join(step_splits[1:])
    return sand_pipe


def raster_pre_transformation_checks(source_meta: dict, source_crs: Union[pp.CRS, str]):
    """
    Run a number of sanity checks on the source raster file, before transformation.
    Warns if a check fails.

    Parameters
    ----------
    source_meta: dict
        Source raster metadata generated by `raster_metadata` function.

    Returns
    ----------
    bool
        Returns True if all checks pass, otherwise False.
    """
    passed = True
    if ~isinstance(source_crs, pp.CRS):
        source_crs = pp.CRS(source_crs)
    source_auth = source_crs.to_authority()
    raster_auth = pp.CRS(source_meta["wkt"]).to_authority()
    if source_auth != raster_auth:
        passed = False
        logger.warning("The expected authority code/name of the "
                       f"input raster file is {raster_auth}, but received {source_auth}"
                       )
    if source_meta["bands"] != 3:
        passed = False
        logger.warning("Number of bands in the raster file: "
                       f"{source_meta['bands']}. NBS rasters typically contain 3 bands")
    if len(source_meta["overlapping_regions"]) != 1:
        passed = False
        logger.warning("The raster is not overlapping with a single region. "
                       f"The overlapping regions: ({source_meta['overlapping_regions']}).")
    return passed


def raster_post_transformation_checks(source_meta: dict,
                                      target_meta: dict,
                                      target_crs: Union[pp.CRS, str],
                                      vertical_transform: bool
                                      ):
    """
    Run a number of sanity checks on the transformed raster file.
    Warns if a check fails.

    Parameters
    ----------
    source_meta: dict
        Source raster metadata generated by `raster_metadata` function.
    target_meta: dict
        Target raster metadata generated by `raster_metadata` function.
    target_crs: pyproj.crs.CRS or input used to create one
        The expected CRS object for the target raster file.
    vertical_transform: bool
        True if it's a vertical transformation, otherwise False.

    Returns
    ----------
    bool
        Returns True if all checks pass, otherwise False.
    """
    if ~isinstance(target_crs, pp.CRS):
        target_crs = pp.CRS(target_crs)
    passed = True
    target_auth = target_crs.to_authority()
    transformed_auth = pp.CRS(target_meta["wkt"]).to_authority()
    if target_auth != transformed_auth:
        passed = False
        logger.warning("The expected authority code/name of the "
                       f"transformed raster is {target_auth}, but received {transformed_auth}"
                       )
    if source_meta["bands"] != target_meta["bands"]:
        passed = False
        logger.warning("Number of bands in the source file "
                       f"({source_meta['bands']}) doesn't match target ({target_meta['bands']}).")

    if source_meta["driver"] != target_meta["driver"]:
        passed = False
        logger.warning("The driver of the source file "
                       f"({source_meta['driver']}) doesn't match target ({target_meta['driver']}).")

    if vertical_transform:
        if source_meta["dimensions"] != target_meta["dimensions"]:
            passed = False
            logger.warning("The source file band dimensions "
                           f" ({source_meta['dimensions']}) don't match those of the "
                           f"transformed file ({target_meta['dimensions']}).")
        if source_meta["resolution"][0] != target_meta["resolution"][0] or source_meta["resolution"][1] != target_meta["resolution"][1]:
            passed = False
            logger.warning("The source file pixel size "
                           f" ({source_meta['resolution']}) don't match those of the "
                           f"transformed file ({target_meta['resolution']}).")
    return passed


def update_raster_wkt(input_file: str, wkt: str) -> None:
    """
    Assign a new WKT to a GeoTIFF in-place, or to a BAG by recreating the file.
    WARNING: This only *assigns* the SRS. If you're actually changing CRS
    (e.g., degrees->meters), you must reproject with gdal.Warp instead.

    Parameters
    -----------
    input_file: str
        Absolute path to the input raster file.
    wkt: str
        New WKT to update the raster file.    
    """
    if not os.path.exists(input_file):
        err_msg = f"Trying to update WKT, but the input raster file {input_file} does not exist."
        logger.error(err_msg)
        raise FileNotFoundError(err_msg)

    ds = gdal.Open(input_file, gdal.GA_ReadOnly)
    if ds is None:
        raise RuntimeError(f"GDAL cannot open: {input_file}")

    drv = ds.GetDriver().ShortName.upper()

    # GeoTIFF: update in place
    if drv == "GTIFF":
        ds = None
        upd = gdal.Open(input_file, gdal.GA_Update)
        if upd is None:
            raise RuntimeError("Failed to reopen GeoTIFF in update mode.")
        upd.SetProjection(wkt)
        upd.FlushCache()
        upd = None
        return

    # BAG: recreate with -a_srs
    if drv == "BAG":
        tmp_out = input_file + ".tmp.bag"

        ds_bs = gdal.Open(input_file)
        bs = min(ds_bs.GetRasterBand(1).GetBlockSize())
        ds_bs = None

        # Build gdal.Translate options equivalent to: -of BAG -a_srs "<wkt>"
        topts = gdal.TranslateOptions(
            options=["-of", "BAG", "-a_srs", wkt, "-co", f"BLOCK_SIZE={bs}"]
        )
        out = gdal.Translate(tmp_out, ds, options=topts)
        if out is None:
            raise RuntimeError("gdal.Translate failed when recreating BAG.")
        out = None
        ds = None

        os.replace(tmp_out, input_file)
        return

    # Other drivers: try in-place, else fall back to copy-on-write via Translate
    ds = None
    upd = gdal.Open(input_file, gdal.GA_Update)
    if upd:
        upd.SetProjection(wkt)
        upd.FlushCache()
        upd = None
    else:
        tmp_out = input_file + ".tmp"
        topts = gdal.TranslateOptions(options=["-a_srs", wkt])
        out = gdal.Translate(tmp_out, input_file, options=topts)
        if out is None:
            raise RuntimeError(f"Driver {drv} does not support updating SRS.")
        out = None
        os.replace(tmp_out, input_file)
    return


def overwrite_with_original(input_file: str,
                            output_file: str,
                            elevation_band: int = None
                            ) -> None:
    """
    Overwrite the non-elevation bands in the output file with
    the original input file band arrays. Currently, we assume that the elevation
    band is the first band in the input file. The other bands are assumed to be
    the same as the input file.

    Parameters
    ----------
    input_file: str
        Absolute path to the input raster file.
    output_file: str
        Absolute path to the output raster file.
    elevation_band: int, optional
        The index of the elevation band in the input file. If not provided,
        the the index of a band named 'elevation' or 'dem' will be used. Raise exception,
        If no such band name is found.

    Raises
    ----------
    ValueError:
        If the elevation band is not found.

    """
    ds_in = gdal.Open(input_file, gdal.GA_ReadOnly)
    if ds_in.RasterCount < 2:
        return
    if elevation_band is None:
        band_count = ds_in.RasterCount
        for i in range(1, band_count + 1):
            band = ds_in.GetRasterBand(i)
            if band.GetDescription().lower() in ["elevation", "dem"]:
                elevation_band = i
                break
    if elevation_band is None:
        raise ValueError("No elevation band found in the input raster file. "
                         "Please provide the index of the elevation band.")
    ds_out = gdal.Open(output_file, gdal.GA_ReadOnly)
    input_metadata = raster_metadata(input_file)
    # combine the vertically transformed bands and
    # the non-transformed ones into a new raster
    driver = gdal.GetDriverByName(input_metadata["driver"])
    mem_path = f"/vsimem/{os.path.splitext(os.path.basename(output_file))[0]}.tiff"
    ds_temp = driver.Create(mem_path,
                            ds_in.RasterXSize,
                            ds_in.RasterYSize,
                            ds_in.RasterCount,
                            gdal.GDT_Float32
                            )
    ds_temp.SetGeoTransform(ds_out.GetGeoTransform())
    ds_temp.SetProjection(ds_out.GetProjection())
    for b in range(1, ds_in.RasterCount+1):
        if b == elevation_band:
            out_shape = ds_out.GetRasterBand(b).ReadAsArray().shape
            in_shape = ds_in.GetRasterBand(b).ReadAsArray().shape
            if out_shape != in_shape:
                logger.error(f"Band {b} dimensions has changed from"
                             f"{in_shape} to {out_shape}")
            ds_temp.GetRasterBand(b).SetDescription(ds_out.GetRasterBand(b).GetDescription())
            ds_temp.GetRasterBand(b).SetNoDataValue(ds_out.GetRasterBand(b).GetNoDataValue())
            ds_temp.GetRasterBand(b).WriteArray(ds_out.GetRasterBand(b).ReadAsArray())
        else:
            ds_temp.GetRasterBand(b).SetDescription(ds_in.GetRasterBand(b).GetDescription())
            # ds_temp.GetRasterBand(b).SetNoDataValue(ds_in.GetRasterBand(b).GetNoDataValue())
            ds_temp.GetRasterBand(b).WriteArray(ds_in.GetRasterBand(b).ReadAsArray())
    ds_in, ds_out = None, None
    ds_temp.FlushCache()
    driver.CreateCopy(output_file, ds_temp)

    cop = ["COMPRESS=DEFLATE"]
    if input_metadata["driver"].lower() == "gtiff":
        cop.extend(["TILED=YES"])

    gdal.Translate(output_file, ds_temp, format=input_metadata["driver"],
                   outputType=gdal.GDT_Float32,
                   creationOptions=cop)     

    ds_temp = None
    gdal.Unlink(mem_path)
    return


def update_stats(input_file):
    """
    Update statistics for the raster file.

    Parameters:
        input_file (str): Path to the raster file.
    """
    ds = gdal.Open(input_file, gdal.GA_Update)
    for i in range(1, ds.RasterCount + 1):
        ds.GetRasterBand(i).ComputeStatistics(False)
    ds = None
    return


def apply_nbs_bandnames(input_file):
    """
    Apply NBS band names to the raster file.
    Sets the first band description to 'elevation' and the second band
    description to 'uncertainty' if the raster has more than one band.

    Parameters:
        input_file (str): Path to the raster file.
    """
    ds = gdal.Open(input_file, gdal.GA_Update)
    if ds is None:
        err_msg = f"Could not open file: {input_file}"
        logger.error(err_msg)
        raise RuntimeError(err_msg)

    band = ds.GetRasterBand(1)
    band.SetDescription("elevation")

    if ds.RasterCount > 1:
        band = ds.GetRasterBand(2)
        band.SetDescription("uncertainty")

    band.FlushCache()
    ds = None
    return


def add_uncertainty_band(input_file: str) -> None:
    src_ds = gdal.Open(input_file)
    if src_ds is None:
        raise RuntimeError(f"Could not open {input_file}")

    # assumes uncertainty band already exists
    if src_ds.RasterCount > 1:
        return

    input_metadata = raster_metadata(input_file)
    elev_band = src_ds.GetRasterBand(1)
    nodata_val = elev_band.GetNoDataValue()
    elevation = elev_band.ReadAsArray().astype(np.float32)

    if nodata_val is not None:
        mask = (elevation == nodata_val)
    else:
        mask = np.zeros_like(elevation, dtype=bool)

    uncertainty = 1 + 0.02 * elevation
    uncertainty[mask] = nodata_val if nodata_val is not None else 0

    cols = src_ds.RasterXSize
    rows = src_ds.RasterYSize
    count = src_ds.RasterCount
    geotransform = src_ds.GetGeoTransform()
    projection = src_ds.GetProjection()
    dtype = gdal.GDT_Float32

    # Temp uncompressed file with extra band
    tmp_uncompressed = tempfile.NamedTemporaryFile(suffix=".tif", delete=False)
    tmp_uncompressed_path = tmp_uncompressed.name
    tmp_uncompressed.close()

    driver = gdal.GetDriverByName("GTiff")
    raw_ds = driver.Create(tmp_uncompressed_path, cols, rows, count + 1, dtype)
    raw_ds.SetGeoTransform(geotransform)
    raw_ds.SetProjection(projection)

    for i in range(count):
        band = src_ds.GetRasterBand(i + 1)
        data = band.ReadAsArray()
        out_band = raw_ds.GetRasterBand(i + 1)
        out_band.WriteArray(data)
        out_band.SetDescription(band.GetDescription())
        nd = band.GetNoDataValue()
        if nd is not None:
            out_band.SetNoDataValue(nd)

    # Add uncertainty band
    unc_band = raw_ds.GetRasterBand(count + 1)
    unc_band.WriteArray(uncertainty)
    unc_band.SetDescription("uncertainty")
    if nodata_val is not None:
        unc_band.SetNoDataValue(nodata_val)
    unc_band.FlushCache()

    raw_ds = None
    src_ds = None

    cop = ["COMPRESS=DEFLATE"]
    if input_metadata["driver"].lower() == "gtiff":
        cop.extend(["TILED=YES", "BIGTIFF=IF_SAFER"])
    gdal.Translate(
        destName=input_file,
        srcDS=tmp_uncompressed_path,
        creationOptions=cop,
        format=input_metadata["driver"]
    )

    os.remove(tmp_uncompressed_path)
    return


def apply_nbs_band_standards(input_file: str) -> None:
    """
    Apply NBS band standards to the raster file.
    Sets the first band description to 'elevation' and the second band
    description to 'uncertainty' if the raster has more than one band.
    Adds uncertainty band if it does not exist, and updates statistics.

    Parameters:
        input_file (str): Path to the raster file.
    """
    if not os.path.exists(input_file):
        err_msg = f"Raster file {input_file} does not exist."
        logger.error(err_msg)
        raise FileNotFoundError(err_msg)
    ds = gdal.Open(input_file)
    if ds.GetDriver().ShortName.lower() != "gtiff":
        return
    
    apply_nbs_bandnames(input_file)
    add_uncertainty_band(input_file)
    update_stats(input_file)
    return
