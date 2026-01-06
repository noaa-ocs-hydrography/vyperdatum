import os
from vyperdatum.transformer import Transformer
from vyperdatum.utils.raster_utils import raster_metadata, update_raster_wkt
from vyperdatum.utils.vdatum_rest_utils import vdatum_cross_validate
import pyproj as pp
from osgeo import gdal


def get_tiff_files(parent_dir: str, extention: str) -> list:
    tiff_files = []
    for (dirpath, dirnames, filenames) in os.walk(parent_dir):
        for filename in filenames:
            if filename.endswith(extention):
                tiff_files.append(os.sep.join([dirpath, filename]))
    return tiff_files


def remove_second_band(src_path: str, dst_path: str) -> str:
    """
    Remove band 2 from a raster and write the output to a new folder,
    preserving spatial reference, geotransform, and metadata.

    Notes
    -----
    - Overviews/pyramids are not copied; rebuild with `gdaladdo` if needed.
    - If the source has fewer than 2 bands, this raises a ValueError.
    """
    gdal.UseExceptions()

    ds = gdal.Open(src_path, gdal.GA_ReadOnly)
    if ds is None:
        raise RuntimeError(f"Failed to open {src_path}")

    band_count = ds.RasterCount
    if band_count < 2:
        raise ValueError(f"Input has only {band_count} band(s); nothing to drop.")

    # Build band list: keep band 1 and bands 3..N
    band_list = [1] + list(range(3, band_count + 1))

    os.makedirs(os.path.split(dst_path)[0], exist_ok=True)
    driver_name = "GTiff"

    # Translate with the band selection
    translate_opts = gdal.TranslateOptions(
        bandList=band_list,
        format=driver_name,
        creationOptions=["TILED=YES", "COMPRESS=LZW"]
    )

    out_ds = gdal.Translate(dst_path, ds, options=translate_opts)
    if out_ds is None:
        raise RuntimeError("gdal.Translate failed to create the output dataset.")

    # (Optional) sanity pass to ensure band-level attributes are carried over.
    # gdal.Translate typically copies these, but we enforce them just in case.
    # Map: src bands 1,3,4,... -> out bands 1,2,3,...
    mapping = {src_idx: out_idx for out_idx, src_idx in enumerate(band_list, start=1)}
    for src_idx, out_idx in mapping.items():
        sb = ds.GetRasterBand(src_idx)
        ob = out_ds.GetRasterBand(out_idx)

        # NoData
        ndv = sb.GetNoDataValue()
        if ndv is not None:
            ob.SetNoDataValue(ndv)

        # Scale/offset/units/description
        scale = sb.GetScale()
        if scale is not None:
            ob.SetScale(scale)
        offset = sb.GetOffset()
        if offset is not None:
            ob.SetOffset(offset)
        unit = sb.GetUnitType()
        if unit:
            ob.SetUnitType(unit)
        desc = sb.GetDescription()
        if desc:
            ob.SetDescription(desc)

        # Color table & interpretation
        ct = sb.GetColorTable()
        if ct is not None:
            ob.SetColorTable(ct)
        interp = sb.GetColorInterpretation()
        if interp is not None:
            ob.SetColorInterpretation(interp)

        # Band metadata
        ob.SetMetadata(sb.GetMetadata())

    out_ds.FlushCache()
    out_ds = None
    ds = None
    return dst_path




if __name__ == "__main__":
    parent_dir = r"C:\Users\mohammad.ashkezari\Documents\projects\vyperdatum\untrack\data\raster\PBB\Original\FL2205-TB-C"
    parent_dir = r"C:\Users\mohammad.ashkezari\Documents\projects\vyperdatum\untrack\data\raster\PBB\Original\FL1812-TB-N"
    parent_dir = r"C:\Users\mohammad.ashkezari\Documents\projects\vyperdatum\untrack\data\raster\PBB\Original\2020_ngs_topobathyDEM_michael_J1219754"
    parent_dir = r"C:\Users\mohammad.ashkezari\Documents\projects\vyperdatum\untrack\data\raster\PBB\Original\3_band_dem"
    files = get_tiff_files(parent_dir, extention=".tif")
    
    # files = [r"C:\Users\mohammad.ashkezari\Documents\projects\vyperdatum\untrack\data\raster\PBB\Original\FL1812-TB-N\2018_315000e_3080000n_tpu.tif"]
    crs_from = "EPSG:6346"
    crs_to = "EPSG:6346+NOAA:98"

    # steps = [{'crs_from': 'EPSG:6346', 'crs_to': 'EPSG:6318', 'v_shift': False},
    #          {'crs_from': 'EPSG:6318+EPSG:5703', 'crs_to': 'EPSG:6319', 'v_shift': True},
    #          {'crs_from': 'EPSG:6319', 'crs_to': 'EPSG:6318+NOAA:98', 'v_shift': True},
    #          {'crs_from': 'EPSG:6318', 'crs_to': 'EPSG:6346', 'v_shift': False}
    #          ]
    for i, input_file in enumerate(files[:]):
        print(f"{i+1}/{len(files)}: {input_file}")
        tf = Transformer(crs_from=crs_from,
                         crs_to=crs_to,
                        #  steps=steps
                         )
        
        prc_file = input_file.replace("Original", "Processed")
        remove_second_band(src_path=input_file, dst_path=prc_file)
        output_file = input_file.replace("Original", "Manual")
        tf.transform_raster(input_file=prc_file,
                            output_file=output_file,
                            overview=False,
                            pre_post_checks=True,
                            vdatum_check=True
                            )                 
        print(f'\n{"*"*50} {i+1}/{len(files)} Completed {"*"*50}\n')
