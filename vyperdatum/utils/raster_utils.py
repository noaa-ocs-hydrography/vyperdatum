import os
import pathlib
import logging
from osgeo import gdal
import numpy as np
from typing import Union, Optional
import pyproj as pp
from vyperdatum.utils.spatial_utils import overlapping_regions, overlapping_extents
from vyperdatum.utils.crs_utils import commandline, pipeline_string
from vyperdatum.enums import VDATUM


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
        metadata |= {"band_descriptions": [ds.GetRasterBand(i+1).GetDescription()
                                           for i in range(ds.RasterCount)]}
        # metadata |= {"band_stats": [band_stats(ds.GetRasterBand(i+1).ReadAsArray())
        #                             for i in range(ds.RasterCount)]}
        metadata |= {"compression": ds.GetMetadata("IMAGE_STRUCTURE").get("COMPRESSION", None)}
        metadata |= {"vertical_datum_wkt": gdal_metadata.get("VERTICALDATUMWKT", None)} #Input Vertical Datum WKT (Xipe)
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
        ds = None

        input_crs = pp.CRS(metadata["wkt"])
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


def warp(input_file: str,
         output_file: str,
         apply_vertical: bool,
         crs_from: Union[pp.CRS, str],
         crs_to: Union[pp.CRS, str],
         input_metadata: dict,
         warp_kwargs: Optional[dict] = None
         ):
    """
    A gdal-warp wrapper to transform an NBS raster (GTiff) file with 3 bands:
    Elevation, Uncertainty, and Contributors.

    Parameters
    ----------
    input_file: str
        Path to the input raster file (gdal supported).
    output_file: str
        Path to the transformed raster file.
    apply_vertical: bool
        Apply GDAL vertical shift.
    crs_from: pyproj.crs.CRS or input used to create one
        Projection of input data.
    crs_to: pyproj.crs.CRS or input used to create one
        Projection of output data.
    input_metadata: dict
        Dictionary containing metadata generated by vyperdatum.raster_utils.raster_metadata()
    warp_kwargs: dict
        gdal kwargs.

    Returns
    --------
    str:
        Absolute path to the transformed file.
    """
    if isinstance(crs_from, pp.CRS):
        crs_from = crs_to_code_auth(crs_from)
    if isinstance(crs_to, pp.CRS):
        crs_to = crs_to_code_auth(crs_to)

    if not apply_vertical:
        gdal.Warp(destNameOrDestDS=output_file,
                  srcDSOrSrcDSTab=input_file,
                  dstSRS=crs_to,
                  srcSRS=crs_from,
                  # xRes=input_metadata["resolution"][0],
                  # yRes=abs(input_metadata["resolution"][1]),
                  # outputBounds=input_metadata["extent"],
                  **(warp_kwargs or {})
                  )
    else:
        # horizontal CRS MUST be identical for both source and target

        #  replace with gdal.Warp() once the nodata fix is online, at PROJ 9.6.0?
        pipe = pipeline_string(crs_from=crs_from, crs_to=crs_to)
        stdout, stderr = commandline(command="gdalwarp",
                                     args=["-ct", f'{pipe}',
                                           "-wo", "sample_grid=yes",
                                           "-wo", "sample_steps=all",
                                           "-wo", "apply_vertical_shift=yes",
                                           "-tr", f"{input_metadata['resolution'][0]}", f"{abs(input_metadata['resolution'][1])}",
                                           "-te", f"{input_metadata['extent'][0]}", f"{input_metadata['extent'][1]}", f"{input_metadata['extent'][2]}", f"{input_metadata['extent'][3]}",
                                           f'{input_file}', f'{output_file}'])

        print("ppppppppppppppppppppppp")
        print(pipe)
        print(">>>>>>>>>>>>>>>>>>>>>>>")
        print(stdout)
        print("eeeeeeeeeeeeeeeeeeeeeee")
        print(stderr)
        #######################################################

        if isinstance(warp_kwargs.get("srcBands"), list):
            ds_in = gdal.Open(input_file, gdal.GA_ReadOnly)
            ds_out = gdal.Open(output_file, gdal.GA_ReadOnly)
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
                if b in warp_kwargs.get("srcBands"):
                    out_shape = ds_out.GetRasterBand(b).ReadAsArray().shape
                    in_shape = ds_in.GetRasterBand(b).ReadAsArray().shape
                    if out_shape != in_shape:
                        logger.error(f"Band {b} dimensions has changed from"
                                     f"{in_shape} to {out_shape}")
                    ds_temp.GetRasterBand(b).WriteArray(ds_out.GetRasterBand(b).ReadAsArray())
                    ds_temp.GetRasterBand(b).SetDescription(ds_out.GetRasterBand(b).GetDescription())
                    ds_temp.GetRasterBand(b).SetNoDataValue(ds_out.GetRasterBand(b).GetNoDataValue())
                else:
                    ds_temp.GetRasterBand(b).WriteArray(ds_in.GetRasterBand(b).ReadAsArray())
                    ds_temp.GetRasterBand(b).SetDescription(ds_in.GetRasterBand(b).GetDescription())
                    ds_temp.GetRasterBand(b).SetNoDataValue(ds_in.GetRasterBand(b).GetNoDataValue())
            ds_in, ds_out = None, None
            ds_temp.FlushCache()
            driver.CreateCopy(output_file, ds_temp)
            ds_temp = None
            gdal.Unlink(mem_path)

    # preserve_raster_size(input_file=input_file, output_file=output_file)

    if input_metadata["compression"] and input_metadata["driver"].lower() == "gtiff":
        output_file_copy = str(output_file)+".tmp"
        os.rename(output_file, output_file_copy)
        raster_compress(output_file_copy, output_file,
                        input_metadata["driver"], input_metadata['compression']
                        )
        os.remove(output_file_copy)

    return output_file


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
    Update the WKT of a raster file.

    Parameters
    -----------
    input_file: str
        Absolute path to the input raster file.
    wkt: str
        New WKT to update the raster file.
    """
    ds = gdal.Open(input_file, gdal.GA_Update)
    ds.SetProjection(wkt)
    ds.FlushCache()
    ds = None
    return
