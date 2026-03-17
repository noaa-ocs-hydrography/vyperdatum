import os
import re
import sys
import io
import pathlib
import logging
import json
import math
import tempfile
from pathlib import Path
from importlib.metadata import version
from osgeo import gdal, osr, ogr
import numpy as np
import subprocess
from typing import Union, Optional, Tuple
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
    if gdal.VSIStatL(input_file) is None:
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

        gdal.Rename(tmp_out, input_file)
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


def overwrite_with_original(input_file: str, output_file: str) -> None:
    """
    Overwrite the non-elevation bands in the output file with the original input
    file band arrays. If an uncertainty band exists, it will be masked so that
    uncertainty is only present where elevation is valid (not NoData).
    """
    ds_in = gdal.Open(input_file, gdal.GA_ReadOnly)
    if ds_in is None:
        raise ValueError(f"Failed to open input_file: {input_file}")

    if ds_in.RasterCount < 2:
        ds_in = None
        return

    elevation_band, uncertainty_band = None, None
    for i in range(1, ds_in.RasterCount + 1):
        band = ds_in.GetRasterBand(i)
        desc = (band.GetDescription() or "").strip().lower()
        if desc in ["elevation", "dem"]:
            elevation_band = i
        if desc in ["uncertainty", "tvu"]:
            uncertainty_band = i

    if elevation_band is None:
        ds_in = None
        raise ValueError(
            "No elevation band found in the input raster file. "
            "Please provide the index of the elevation band."
        )

    ds_out = gdal.Open(output_file, gdal.GA_ReadOnly)
    if ds_out is None:
        ds_in = None
        raise ValueError(f"Failed to open output_file: {output_file}")

    input_metadata = raster_metadata(input_file)
    driver = gdal.GetDriverByName(input_metadata["driver"])

    mem_path = f"/vsimem/{os.path.splitext(os.path.basename(output_file))[0]}.tiff"
    ds_temp = driver.Create(
        mem_path,
        ds_in.RasterXSize,
        ds_in.RasterYSize,
        ds_in.RasterCount,
        gdal.GDT_Float32
    )
    ds_temp.SetGeoTransform(ds_out.GetGeoTransform())
    ds_temp.SetProjection(ds_out.GetProjection())

    # --- Read elevation (from ds_out) once and build a validity mask ---
    elev_out_band = ds_out.GetRasterBand(elevation_band)
    elev_arr = elev_out_band.ReadAsArray()
    elev_nodata = elev_out_band.GetNoDataValue()

    if elev_nodata is None:
        # Fall back: treat non-finite as invalid
        valid_elev = np.isfinite(elev_arr)
    else:
        if np.isnan(elev_nodata):
            valid_elev = ~np.isnan(elev_arr)
        else:
            valid_elev = (elev_arr != elev_nodata) & np.isfinite(elev_arr)

    # --- Write all bands; mask uncertainty where elevation is invalid ---
    for b in range(1, ds_in.RasterCount + 1):
        out_band = ds_temp.GetRasterBand(b)

        if b == elevation_band:
            # Write transformed elevation from ds_out
            out_band.SetDescription("Elevation")
            if elev_nodata is not None:
                out_band.SetNoDataValue(float(elev_nodata))
            out_band.WriteArray(elev_arr.astype(np.float32, copy=False))

        elif uncertainty_band is not None and b == uncertainty_band:
            in_unc_band = ds_in.GetRasterBand(b)
            unc_arr = in_unc_band.ReadAsArray().astype(np.float32, copy=False)

            # Choose an output NoData for uncertainty
            unc_nodata_in = in_unc_band.GetNoDataValue()
            if unc_nodata_in is not None:
                unc_nodata_out = float(unc_nodata_in)
            elif elev_nodata is not None and np.isfinite(elev_nodata):
                unc_nodata_out = float(elev_nodata)
            else:
                unc_nodata_out = input_metadata["band_no_data"][0]

            # Mask uncertainty wherever elevation is NoData
            unc_masked = np.array(unc_arr, copy=True)
            unc_masked[~valid_elev] = unc_nodata_out

            out_band.SetDescription("Uncertainty")
            out_band.SetNoDataValue(unc_nodata_out)
            out_band.WriteArray(unc_masked)

        else:
            # Copy any other non-elevation bands from the input (mask at no elevation points)
            in_band = ds_in.GetRasterBand(b)
            arr = in_band.ReadAsArray()
            if elev_nodata is not None and np.isfinite(elev_nodata):
                unc_nodata_out = float(elev_nodata)
            else:
                unc_nodata_out = input_metadata["band_no_data"][0]
            arr_masked = np.array(arr, copy=True)
            arr_masked[~valid_elev] = unc_nodata_out
            out_band.SetDescription(in_band.GetDescription())
            nd = in_band.GetNoDataValue()
            if nd is not None:
                out_band.SetNoDataValue(float(nd))
            out_band.WriteArray(arr_masked.astype(np.float32, copy=False))

    ds_in, ds_out = None, None
    ds_temp.FlushCache()

    cop = ["COMPRESS=DEFLATE"]
    if input_metadata["driver"].lower() == "gtiff":
        cop.extend(["TILED=YES"])

    gdal.Translate(
        output_file,
        ds_temp,
        format=input_metadata["driver"],
        outputType=gdal.GDT_Float32,
        creationOptions=cop
    )

    ds_temp = None
    gdal.Unlink(mem_path)


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
    if gdal.VSIStatL(input_file) is None:
        err_msg = f"Raster file {input_file} does not exist."
        logger.error(err_msg)
        raise FileNotFoundError(err_msg)
    ds = gdal.Open(input_file)
    if ds.GetDriver().ShortName.lower() != "gtiff":
        return
    
    # apply_nbs_bandnames(input_file)
    add_uncertainty_band(input_file)
    update_stats(input_file)
    return


def create_cutline_from_grid(grid_path: str,
                             output_cutline: str,
                             input_extent=None,
                             input_wkt: str = None):
    """
    Create a cutline polygon from a GTG grid's valid (non-nodata) area,
    restricted to the vicinity of `input_extent` (bbox) when provided.
    This version supports rasters that span multiple subgrids by unioning 
    all overlapping valid areas.
    """
    _logger = globals().get("logger", None)

    def _log(level: str, msg: str):
        if _logger is not None:
            getattr(_logger, level)(msg)
        else:
            print(f"{level.upper()}: {msg}")

    def _inv_geotransform(gt):
        inv = gdal.InvGeoTransform(gt)
        if isinstance(inv, tuple) and len(inv) == 2 and isinstance(inv[0], (bool, int)):
            ok, inv_gt = inv
            if not ok:
                raise RuntimeError("gdal.InvGeoTransform failed")
            return tuple(inv_gt)
        if isinstance(inv, (tuple, list)) and len(inv) == 6:
            return tuple(inv)
        raise RuntimeError(f"Unexpected gdal.InvGeoTransform return: {type(inv)} {inv}")

    def _ds_extent(ds):
        gt = ds.GetGeoTransform()
        x0, px_w, _, y0, _, px_h = gt
        w, h = ds.RasterXSize, ds.RasterYSize
        xmin = x0
        xmax = x0 + px_w * w
        ymax = y0
        ymin = y0 + px_h * h
        if xmin > xmax:
            xmin, xmax = xmax, xmin
        if ymin > ymax:
            ymin, ymax = ymax, ymin
        return (xmin, ymin, xmax, ymax)

    def _bbox_intersection(a, b):
        ax0, ay0, ax1, ay1 = a
        bx0, by0, bx1, by1 = b
        ix0 = max(ax0, bx0)
        iy0 = max(ay0, by0)
        ix1 = min(ax1, bx1)
        iy1 = min(ay1, by1)
        if ix0 >= ix1 or iy0 >= iy1:
            return None
        return (ix0, iy0, ix1, iy1)

    def _bbox_to_srcwin(ds, bbox, pad_pixels=3):
        ds_ext = _ds_extent(ds)
        bb = _bbox_intersection(bbox, ds_ext)
        if bb is None:
            return None
        xmin, ymin, xmax, ymax = bb

        inv_gt = _inv_geotransform(ds.GetGeoTransform())

        px0, py0 = gdal.ApplyGeoTransform(inv_gt, xmin, ymax)
        px1, py1 = gdal.ApplyGeoTransform(inv_gt, xmax, ymin)

        col0 = int(math.floor(min(px0, px1))) - pad_pixels
        col1 = int(math.ceil(max(px0, px1))) + pad_pixels
        row0 = int(math.floor(min(py0, py1))) - pad_pixels
        row1 = int(math.ceil(max(py0, py1))) + pad_pixels

        col0 = max(0, min(col0, ds.RasterXSize))
        col1 = max(0, min(col1, ds.RasterXSize))
        row0 = max(0, min(row0, ds.RasterYSize))
        row1 = max(0, min(row1, ds.RasterYSize))

        xsize = col1 - col0
        ysize = row1 - row0
        if xsize <= 0 or ysize <= 0:
            return None
        return (col0, row0, xsize, ysize)

    def _srs_from_wkt(wkt: str):
        srs = osr.SpatialReference()
        srs.ImportFromWkt(wkt)
        try:
            srs.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
        except Exception:
            pass
        return srs

    def _reproject_bbox(bbox, src_srs, dst_srs):
        xmin, ymin, xmax, ymax = bbox
        ct = osr.CoordinateTransformation(src_srs, dst_srs)
        pts = [
            ct.TransformPoint(xmin, ymin),
            ct.TransformPoint(xmin, ymax),
            ct.TransformPoint(xmax, ymin),
            ct.TransformPoint(xmax, ymax),
        ]
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        return (min(xs), min(ys), max(xs), max(ys))

    try:
        gdal.UseExceptions()
        ogr.UseExceptions()

        overlap_pct = None
        container = gdal.Open(grid_path)
        if container is None:
            _log("error", f"Could not open grid: {grid_path}")
            return None, None

        candidates = []
        subdatasets = container.GetSubDatasets() or []
        if subdatasets:
            _log("info", f"GTG file detected with {len(subdatasets)} subgrids")
            for idx, (name, desc) in enumerate(subdatasets):
                ds = gdal.Open(name)
                if ds is None:
                    continue
                ext = _ds_extent(ds)
                candidates.append((idx, name, desc, ds, ext))
        else:
            ds = container
            ext = _ds_extent(ds)
            candidates.append((0, grid_path, "", ds, ext))

        if not candidates:
            _log("error", "No readable subdatasets found in grid.")
            return None, None

        grid_wkt = candidates[0][3].GetProjection()
        grid_srs = _srs_from_wkt(grid_wkt) if grid_wkt else None

        bbox_grid = None
        if input_extent is not None:
            bbox_in = tuple(float(x) for x in input_extent)
            if input_wkt and grid_srs:
                in_srs = _srs_from_wkt(input_wkt)
                bbox_grid = _reproject_bbox(bbox_in, in_srs, grid_srs)
            else:
                bbox_grid = bbox_in

        # Identify all subgrids that overlap our raster bounding box
        overlapping_cands = []
        if bbox_grid is not None:
            for cand in candidates:
                idx, name, desc, ds, ext = cand
                inter = _bbox_intersection(bbox_grid, ext)
                if inter is not None:
                    overlapping_cands.append((cand, inter))
            if not overlapping_cands:
                _log("error", f"Input bbox does not overlap any subgrids. bbox={bbox_grid}")
                return None, None
        else:
            overlapping_cands = [(cand, cand[4]) for cand in candidates]

        _log("info", f"Found {len(overlapping_cands)} overlapping subgrid(s). Processing union...")

        union_geom = None
        total_valid = 0
        total_cells = 0

        # Iterate and union every valid overlapping geometry
        for cand, target_bbox in overlapping_cands:
            idx, name, desc, grid_ds, grid_ext = cand
            srcwin = _bbox_to_srcwin(grid_ds, target_bbox, pad_pixels=5)
            if srcwin is None:
                continue

            xoff, yoff, xsize, ysize = srcwin
            cropped = gdal.Translate("", grid_ds, format="MEM", srcWin=[xoff, yoff, xsize, ysize])
            if cropped is None:
                continue

            band = cropped.GetRasterBand(1)
            nodata = band.GetNoDataValue()
            arr = band.ReadAsArray()
            if arr is None:
                continue
            if nodata is None:
                nodata = -32768.0

            valid_mask = (~np.isnan(arr)) & (~np.isclose(arr.astype("float64"), float(nodata)))
            v_count = int(valid_mask.sum())
            t_count = int(valid_mask.size)
            total_valid += v_count
            total_cells += t_count

            if v_count == 0:
                continue

            mem = gdal.GetDriverByName("MEM")
            mask_ds = mem.Create("", xsize, ysize, 1, gdal.GDT_Byte)
            mask_ds.SetGeoTransform(cropped.GetGeoTransform())
            if grid_wkt:
                mask_ds.SetProjection(grid_wkt)
            mask_band = mask_ds.GetRasterBand(1)
            mask_band.WriteArray(valid_mask.astype("uint8"))
            mask_band.FlushCache()

            vmem_drv = ogr.GetDriverByName("MEM")
            vmem_ds = vmem_drv.CreateDataSource(f"mem_cutline_{idx}")
            srs = _srs_from_wkt(grid_wkt) if grid_wkt else None
            vmem_lyr = vmem_ds.CreateLayer("cutline", srs=srs, geom_type=ogr.wkbPolygon)
            vmem_lyr.CreateField(ogr.FieldDefn("DN", ogr.OFTInteger))

            gdal.Polygonize(mask_band, mask_band, vmem_lyr, 0, ["8CONNECTED=8"])
            vmem_lyr.SetAttributeFilter("DN = 1")

            # Merge the subgrid geometry into the master union
            for f in vmem_lyr:
                g = f.GetGeometryRef()
                if g is not None:
                    g2 = g.Clone()
                    union_geom = g2 if union_geom is None else union_geom.Union(g2)

        if union_geom is None:
            _log("error", "Failed to build union geometry from subgrids.")
            return None, None

        overlap_pct = (total_valid / total_cells * 100.0) if total_cells > 0 else 0.0
        _log("info", f"Valid cells (combined): {total_valid} / {total_cells} ({overlap_pct:.2f}%)")

        if srs and srs.IsGeographic():
            tol = 0.0005
        else:
            tol = 50.0
        try:
            union_geom = union_geom.Simplify(tol)
        except Exception:
            pass

        ext = os.path.splitext(output_cutline)[1].lower()
        if ext == ".gpkg":
            drv_name = "GPKG"
        elif ext == ".shp":
            drv_name = "ESRI Shapefile"
        elif ext in (".json", ".geojson"):
            drv_name = "GeoJSON"
        else:
            output_cutline = os.path.splitext(output_cutline)[0] + ".gpkg"
            drv_name = "GPKG"
            _log("warning", f"Unrecognized cutline extension; writing GeoPackage instead: {output_cutline}")

        out_drv = ogr.GetDriverByName(drv_name)
        if out_drv is None:
            _log("error", f"OGR driver not available: {drv_name}")
            return None, None
        if gdal.VSIStatL(output_cutline) is not None:
            out_drv.DeleteDataSource(output_cutline)

        if drv_name == "GeoJSON":
            gdal.SetConfigOption("GDAL_GEOJSON_WRITE_CRS", "YES")

        out_ds = out_drv.CreateDataSource(output_cutline)
        out_lyr = out_ds.CreateLayer("cutline", srs=srs, geom_type=ogr.wkbPolygon)
        out_lyr.CreateField(ogr.FieldDefn("DN", ogr.OFTInteger))

        feat = ogr.Feature(out_lyr.GetLayerDefn())
        feat.SetField("DN", 1)
        feat.SetGeometry(union_geom)
        out_lyr.CreateFeature(feat)
        feat = None
        out_ds = None

        _log("info", f"Cutline written: {output_cutline}")
        return output_cutline, overlap_pct

    except Exception as e:
        _log("exception", f"Error creating cutline from grid: {e}")
        return None, None


def create_cutline_file(v_shift: bool,
                        grid_files: list[str],
                        cutline_path: str,
                        input_metadata: dict) -> Optional[str]:
    """
    Create a cutline file from the provided grid files if vertical shift is applied.
    Otherwise, return None.

    TODO: what if more than one NWLD grids are involved?
    """
    if v_shift and grid_files:
        grid_file = None
        # Use the first NOAA grid file (or we could merge multiple grids)
        for gf in grid_files:
            if (gf.lower().find("nwld") != -1) or (gf.lower().find("underkeel_hydroid") != -1):
                grid_file = gf
                break
        if grid_file is None:
            return None, None
        if not os.path.isabs(grid_file):
            vyper_grids = os.environ.get("VYPER_GRIDS", "")

            for base_dir in [vyper_grids]:
                potential_path = os.path.join(base_dir, grid_file)
                if os.path.exists(potential_path):
                    grid_file = potential_path
                    break

        if os.path.exists(grid_file):
            cutline_path, overlap_pct = create_cutline_from_grid(grid_file, cutline_path,
                                                                 input_extent=input_metadata["extent"],
                                                                 input_wkt=input_metadata["wkt"],
                                                                 )
            if cutline_path:
                logger.info(f"Using cutline from grid: {cutline_path} for grid: {grid_file}")
        else:
            logger.warning(f"Grid file not found: {grid_file}")
    else:
        cutline_path = None
    return cutline_path, overlap_pct


def clip_raster_to_cutline(input_path: str, cutline_path: str, output_path: str) -> Optional[str]:
    """
    Clips a raster to a cutline while preserving original resolution and metadata.
    This creates a pre-masked file where all data points are guaranteed to be 
    within the grid's valid area for the subsequent transformation.
    """
    try:
        # Get original metadata to ensure we match resolution and nodata
        ds_in = gdal.Open(input_path, gdal.GA_ReadOnly)
        if ds_in is None:
            return None

        # Get input NoData and GeoTransform
        gt = ds_in.GetGeoTransform()
        x_res, y_res = abs(gt[1]), abs(gt[5])
        band = ds_in.GetRasterBand(1)
        nodata = band.GetNoDataValue() if band.GetNoDataValue() is not None else -9999.0

        # Use gdal.Warp to clip. We DO NOT change the CRS yet.
        # This keeps the math local and simple.
        warp_options = gdal.WarpOptions(
            format="GTiff",
            cutlineDSName=cutline_path,
            cropToCutline=True,  # Shrink the file extent to the grid overlap
            srcNodata=nodata,
            dstNodata=nodata,
            xRes=x_res,
            yRes=y_res,
            resampleAlg="near",
            creationOptions=["COMPRESS=DEFLATE", "TILED=YES"]
        )

        # Run the clip
        ds_out = gdal.Warp(output_path, ds_in, options=warp_options)

        if ds_out:
            # Transfer metadata tags (like Vyperdatum_Metadata)
            ds_out.SetMetadata(ds_in.GetMetadata())
            ds_out.FlushCache()
            ds_out = None
            ds_in = None
            return output_path

        return None
    except Exception as e:
        logging.error(f"Error in clip_raster_to_cutline: {e}")
        return None


def add_vyper_tag(raster_file: str, pipe: str, crs_to: pp.CRS, steps: list) -> None:
    """
    Add a Vyperdatum tag to the raster file to indicate it has been processed.
    """
    ds = gdal.Open(raster_file, gdal.GA_Update)
    if ds is None:
        logger.error(f"Failed to open {raster_file} to add Vyperdatum tag.")
        return

    # pipe = re.sub(r"\s{2,}", " ", pipe).strip()
    to_wkt = crs_to.to_wkt()
    # to_wkt = re.sub(r"\s{2,}", " ", to_wkt).strip()
    buffer = io.StringIO()
    sys.stdout = buffer
    pp.show_versions()
    sys.stdout = sys.__stdout__
    pyproj_versions = buffer.getvalue()
    # pyproj_versions = re.sub(r"\s{2,}", " ", buffer.getvalue()).strip()
    crs_h, crs_v = crs_utils.crs_components(crs_to, raise_no_auth=False)

    vyper_meta = {"description": ("This file is the output of a transformation pipeline "
                                  "executed using Vyperdatum software by NOAA's OCS, NBS branch."),
                  "vyperdatum_version": version("vyperdatum"),
                  "steps": steps,
                  "proj_pipeline": pipe,
                  "wkt": to_wkt,
                  "crs_horizontal": crs_h if crs_h else "",
                  "crs_vertical": crs_v if crs_v else "",
                  "pyproj_versions": pyproj_versions,
                  }
    vyper_meta = json.dumps(vyper_meta)
    ds.SetMetadataItem("Vyperdatum_Metadata", vyper_meta)    
    ds.FlushCache()
    ds = None
    return
