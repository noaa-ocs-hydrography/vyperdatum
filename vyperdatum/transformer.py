import os
from os import path
import pathlib
import shutil
import copy
import logging
from pathlib import Path
import re
import json
from typing import Union, Optional
from colorama import Fore, Style
import pyproj as pp
from pyproj._transformer import AreaOfInterest
import numpy as np
from osgeo import gdal, osr, ogr
from tqdm import tqdm
from vyperdatum.utils import raster_utils, crs_utils, drivers_utils
from vyperdatum.utils.raster_utils import (raster_metadata,
                                           update_raster_wkt,
                                           overwrite_with_original,
                                           apply_nbs_band_standards,
                                           add_vyper_tag,
                                           create_cutline_from_grid)
from vyperdatum.utils.vdatum_rest_utils import vdatum_cross_validate
from vyperdatum.drivers import vrbag, laz, npz, pdal_based, gparq, xyz
from vyperdatum.pipeline import nwld_ITRF2020_steps, nwld_NAD832011_steps

logger = logging.getLogger("root_logger")
gdal.UseExceptions()

# os.environ["CPL_DEBUG"] = "ON"
# os.environ["CPL_LOG_ERRORS"] = "ON"
# os.environ["PROJ_DEBUG"] = "3"


# Pass 1 tiling
PASS1_TILED_PIXEL_THRESHOLD = 250_000_000
PASS1_DEFAULT_TILE_SIZE = 4096


def _pass1_warp_tiled(input_file, output_vrt_path, warp_kwargs_template,
                      cut_metadata, tile_size):
    """Run Pass 1 as a tiled warp.

    Writes one GeoTIFF per tile into a subdirectory next to
    ``output_vrt_path``, then builds a VRT mosaic referencing the tiles
    at ``output_vrt_path``. Returns the path to the tiles subdirectory
    so the caller can clean it up.

    On any tile failure, all tiles written so far and the subdirectory
    are removed and the exception is re-raised.
    """
    minx, miny, maxx, maxy = cut_metadata["extent"]
    W, H = (int(s.strip()) for s in str(cut_metadata["dimensions"]).split("x"))
    xres = (maxx - minx) / W
    yres = (maxy - miny) / H

    tiles_dir = Path(output_vrt_path).parent / f"{Path(output_vrt_path).stem}_tiles"
    tiles_dir.mkdir(parents=True, exist_ok=True)

    n_tiles_x = (W + tile_size - 1) // tile_size
    n_tiles_y = (H + tile_size - 1) // tile_size
    total_tiles = n_tiles_x * n_tiles_y
    logger.info(f"Pass 1 tiled mode: {W}x{H} pixels -> {n_tiles_x}x{n_tiles_y} = {total_tiles} tiles (up to {tile_size}px each)")

    tile_paths = []
    try:
        for tj in range(n_tiles_y):
            for ti in range(n_tiles_x):
                px0 = ti * tile_size
                py0 = tj * tile_size
                px1 = min((ti + 1) * tile_size, W)
                py1 = min((tj + 1) * tile_size, H)
                tw = px1 - px0
                th = py1 - py0
                tile_minx = minx + px0 * xres
                tile_maxx = minx + px1 * xres
                tile_maxy = maxy - py0 * yres
                tile_miny = maxy - py1 * yres

                tile_path = str(tiles_dir / f"tile_{ti:04d}_{tj:04d}.tif")
                kw = dict(warp_kwargs_template)
                kw["outputBounds"] = (tile_minx, tile_miny, tile_maxx, tile_maxy)
                kw["width"] = tw
                kw["height"] = th

                idx = tj * n_tiles_x + ti + 1
                logger.info(f"Pass 1 tile {idx}/{total_tiles}: {tw}x{th} px at pixel ({px0},{py0})")
                tds = gdal.Warp(tile_path, input_file, **kw)
                if tds is None:
                    raise RuntimeError(f"Pass 1 tile warp returned None for tile ({ti},{tj})")
                tds = None
                tile_paths.append(tile_path)

        vrt_ds = gdal.BuildVRT(output_vrt_path, tile_paths)
        if vrt_ds is None:
            raise RuntimeError("BuildVRT returned None for Pass 1 tile mosaic")
        vrt_ds = None
        return tiles_dir
    except Exception:
        for tp in tile_paths:
            try:
                if os.path.exists(tp):
                    os.remove(tp)
            except Exception as e:
                logger.warning(f"Could not delete partial tile {tp}: {e}")
        try:
            if tiles_dir.exists():
                shutil.rmtree(str(tiles_dir))
        except Exception as e:
            logger.warning(f"Could not remove tiles directory {tiles_dir}: {e}")
        raise


class Transformer():
    def __init__(self,
                 crs_from: Union[pp.CRS, int, str],
                 crs_to: Union[pp.CRS, int, str],
                 steps: Optional[list[str]] = None
                 ) -> None:
        """

        Raises
        ----------
        ValueError
            If the transformation steps cannot be validated.

        Parameters
        ----------
        crs_from: pyproj.crs.CRS or input used to create one
            Projection of input data.
        crs_to: pyproj.crs.CRS or input used to create one
            Projection of output data.
        steps: Optional[list[dict]]
            A list of dicts containing source and target CRSs in form of `authority:code`,
            and a boolean key to signify if the step impose a vertical shift. This parameter
            represents the overall transformation steps connecting the `crs_from` to `crs_to`.
            When `None` is passed, vyperdatum will attempt to automatically determine the steps
            from `crs_from` to `crs_to`.
            Example:
            steps = [{"crs_from": "EPSG:6346", "crs_to": "EPSG:6318", "v_shift": False},
                     {"crs_from": "EPSG:6319", "crs_to": "EPSG:6318+NOAA:98", "v_shift": True},
                     {"crs_from": "EPSG:6318", "crs_to": "EPSG:6346", "v_shift": False}
                    ]
        """

        if not isinstance(crs_from, pp.CRS):
            crs_from = pp.CRS(crs_from)
        if not isinstance(crs_to, pp.CRS):
            crs_to = pp.CRS(crs_to)
        self.crs_from = crs_from
        self.crs_to = crs_to
        self.steps = steps
        if not self.steps:
            # self.steps = [crs_utils.auth_code(self.crs_from), crs_utils.auth_code(self.crs_to)]
            h0, v0 = crs_utils.crs_components(self.crs_from)
            h1, v1 = crs_utils.crs_components(self.crs_to)
            # self.steps = nwld_ITRF2020_steps(h0, v0, h1, v1)
            self.steps = nwld_NAD832011_steps(h0, v0, h1, v1)
        if not crs_utils.validate_transform_steps_dict(self.steps):
            raise ValueError(f"Invalid transformation pipeline: {self.steps}.")
        return

    @classmethod
    def from_GTiff_raster(cls,
                          input_file: str,
                          crs_to: Union[pp.CRS, int, str],
                          steps: Optional[list[dict]]) -> "Transformer":
        """
        Create a Transformer instance from a GeoTiff raster file.

        Raises
        ----------
        FileNotFoundError
            If the input file is not found.
        ValueError
            If the input raster does not have the `Vyperdatum_Metadata` metadata tag.

        Parameters
        ----------
        input_file: str
            Path to the input raster file.
        crs_to: pyproj.crs.CRS or input used to create one
            Projection of output data.
        steps: Optional[list[dict]]
            A list of dicts containing source and target CRSs in form of `authority:code`,
            and a boolean key to signify if the step impose a vertical shift. This parameter
            represents the overall transformation steps connecting the `crs_from` to `crs_to`.
            When `None` is passed, vyperdatum will attempt to automatically determine the steps.        
        """
        if not os.path.isfile(input_file):
            raise FileNotFoundError(f"The input file not found at {input_file}.")
        meta = raster_utils.raster_metadata(input_file)
        if "Vyperdatum_Metadata" not in meta:
            raise ValueError("The input raster file does not have the `Vyperdatum_Metadata` tag.")
        vyperdatum_metadata = json.loads(meta["Vyperdatum_Metadata"])
        crs_from = pp.CRS(vyperdatum_metadata["wkt"])
        return cls(crs_from=crs_from, crs_to=crs_to, steps=steps)

    @staticmethod
    def gdal_extensions() -> list[str]:
        """
        Return a lower-cased list of driver names supported by gdal.

        Returns
        -------
        list[str]
        """
        return sorted(
            ["." + gdal.GetDriver(i).ShortName.lower() for i in range(gdal.GetDriverCount())]
            + [".tif", ".tiff"]
            )

    def _validate_input_file(self, input_file: str) -> bool:
        """
        Check if the input file (`input_file`) exists and supported by GDAL.

        Raises
        -------
        FileNotFoundError:
            If the input raster file is not found.
        NotImplementedError:
            If the input vector file is not supported by gdal.

        Parameters
        -----------
        input_file: str
            Path to the input raster file (gdal supported).

        Returns
        -----------
        bool
            True if passes all checks, otherwise False.
        """
        passed = False
        if "vsimem" not in [s.lower() for s in input_file.split("/")] and not os.path.isfile(input_file):
            raise FileNotFoundError(f"The input raster file not found at {input_file}.")
        if pathlib.Path(input_file).suffix.lower() not in self.gdal_extensions():
            raise NotImplementedError(f"{pathlib.Path(input_file).suffix} is not supported")
        passed = True
        return passed

    def transform(self,
                  input_file: str,
                  output_file: str,
                  pre_post_checks: bool = True,
                  vdatum_check: bool = False,
                  **kwargs
                  ) -> bool:
        """
        Top-level transform method.

        Parameters
        -----------
        input_file: str
            Path to the input file.
        output_file: str
            Path to the output transformed file.
        pre_post_checks: bool, default=True
            If True, runs a series of validation checks, such as validating the input and output
            CRSs, before and after transformation operation.

        Raises
        -------
        FileNotFoundError:
            If the input  file is not found.
        NotImplementedError:
            If the input file is not supported by vyperdatum.

        Returns
        -----------
        bool:
            True if successful, otherwise False.
        """
        try:
            success = False    
            if not os.path.isfile(input_file):
                raise FileNotFoundError(f"The input file not found at {input_file}.")

            if vrbag.is_vr(fname=input_file):
                logger.info(f"Identified as vrbag file: {input_file}")
                success = self.transform_vrbag(input_file=input_file,
                                               output_file=output_file,
                                               pre_post_checks=pre_post_checks,
                                               vdatum_check=vdatum_check
                                               )
            elif gparq.GeoParquet(input_file=input_file, invalid_error=False).is_valid:
                logger.info(f"Identified as geoparquet file: {input_file}")
                success = self.transform_geoparquet(input_file=input_file,
                                                    output_file=output_file,
                                                    pre_post_checks=pre_post_checks,
                                                    vdatum_check=vdatum_check
                                                    )
            elif laz.LAZ(input_file=input_file, invalid_error=False).is_valid:
                logger.info(f"Identified as laz file: {input_file}")
                success = self.transform_laz(input_file=input_file,
                                             output_file=output_file,
                                             pre_post_checks=pre_post_checks,
                                             vdatum_check=vdatum_check
                                             )
            elif npz.NPZ(input_file=input_file, invalid_error=False).is_valid:
                logger.info(f"Identified as npz file: {input_file}")
                success = self.transform_npz(input_file=input_file,
                                             output_file=output_file,
                                             pre_post_checks=pre_post_checks,
                                             vdatum_check=vdatum_check
                                             )
            elif xyz.XYZ(input_file=input_file, invalid_error=False).is_valid:
                logger.info(f"Identified as xyz file: {input_file}")
                success = self.transform_xyz(input_file=input_file,
                                             output_file=output_file,
                                             pre_post_checks=pre_post_checks,
                                             vdatum_check=vdatum_check,
                                             **kwargs
                                             )
            elif pathlib.Path(input_file).suffix.lower() in self.gdal_extensions():
                logger.info(f"Identified as GDAL-supported raster file: {input_file}")
                success = self.transform_raster(input_file=input_file,
                                                output_file=output_file,
                                                pre_post_checks=pre_post_checks,
                                                vdatum_check=vdatum_check
                                                )
            elif pdal_based.PDAL(input_file=input_file,
                                 output_file=output_file, invalid_error=False).is_valid:
                logger.info(f"Identified as PDAL-supported file: {input_file}")
                success = self.transform_pdal(input_file=input_file,
                                              output_file=output_file,
                                              pre_post_checks=pre_post_checks,
                                              vdatum_check=vdatum_check
                                              )
            # elif vector files
            else:
                raise NotImplementedError(f"Unsupported input file: {input_file}")
        finally:
            return success

    def transform_points(self,
                         x: Union[list, np.ndarray],
                         y: Union[list, np.ndarray],
                         z: Union[list, np.ndarray],
                         always_xy: bool = False,
                         vdatum_check: bool = False,
                         area_of_interest: Optional[AreaOfInterest] = None,
                         authority: Optional[str] = None,
                         accuracy: Optional[float] = None,
                         allow_ballpark: Optional[bool] = True,
                         force_over: bool = False,
                         only_best: Optional[bool] = True
                         ) -> tuple[Optional[Union[list, np.ndarray]],
                                    Optional[Union[list, np.ndarray]],
                                    Optional[Union[list, np.ndarray]]]:
        """
        Conduct point transformation between two coordinate reference systems.        

        Parameters
        ----------
        x: numeric array
           Input x coordinate(s).
        y: numeric array
           Input y coordinate(s).
        z: numeric array, optional
           Input z coordinate(s).
        always_xy: bool, default=False
            If true, the transform method will accept as input and return as output
            coordinates using the traditional GIS order, that is longitude, latitude
            for geographic CRS and easting, northing for most projected CRS.
        vdatum_check: bool, default=False
            If True, a random sample of the transformed data are compared with transformation
            outcomes produced by Vdatum REST API.
        area_of_interest: :class:`.AreaOfInterest`, optional
            The area of interest to help select the transformation.
        authority: str, optional
            When not specified, coordinate operations from any authority will be
            searched, with the restrictions set in the
            authority_to_authority_preference database table related to the
            authority of the source/target CRS themselves. If authority is set
            to “any”, then coordinate operations from any authority will be
            searched. If authority is a non-empty string different from "any",
            then coordinate operations will be searched only in that authority
            namespace (e.g. EPSG).
        accuracy: float, optional
            The minimum desired accuracy (in metres) of the candidate
            coordinate operations.
        allow_ballpark: bool, optional, default=True
            Set to False to disallow the use of Ballpark transformation
            in the candidate coordinate operations. Default is to allow.
        force_over: bool, default=False
            If True, it will to force the +over flag on the transformation.
            Requires PROJ 9+.
        only_best: bool, optional, default=True
            Can be set to True to cause PROJ to error out if the best
            transformation known to PROJ and usable by PROJ if all grids known and
            usable by PROJ were accessible, cannot be used. Best transformation should
            be understood as the transformation returned by
            :c:func:`proj_get_suggested_operation` if all known grids were
            accessible (either locally or through network).
            Note that the default value for this option can be also set with the
            :envvar:`PROJ_ONLY_BEST_DEFAULT` environment variable, or with the
            ``only_best_default`` setting of the ``proj.ini`` file.
            The only_best kwarg overrides the default value if set.
            Requires PROJ 9.2+.

        Returns
        -----------
        bool:
            True if successful, otherwise False.            
        numeric scalar or array:
           Transformed x coordinate(s).
        numeric scalar or array
           Transformed y coordinate(s).
        numeric scalar or array, optional
           Transformed z coordinate(s).
        """

        try:
            success = False
            xt, yt, zt = x.copy(), y.copy(), z.copy()
            for i in range(len(self.steps)):
                logger.info(f"Step {i+1}/{len(self.steps)}:"
                            f" {self.steps[i]['crs_from']} --> {self.steps[i]['crs_to']}")
                xt, yt, zt = pp.Transformer.from_crs(crs_from=pp.CRS(self.steps[i]["crs_from"]),
                                                     crs_to=pp.CRS(self.steps[i]["crs_to"]),
                                                     always_xy=always_xy,
                                                     area_of_interest=area_of_interest,
                                                     authority=authority,
                                                     accuracy=accuracy,
                                                     allow_ballpark=allow_ballpark,
                                                     force_over=force_over,
                                                     only_best=only_best
                                                     ).transform(xt, yt, zt)
            success = True
            if vdatum_check:
                vdatum_cv, vdatum_df = vdatum_cross_validate(s_wkt=pp.CRS(self.steps[0]["crs_from"]).to_wkt(),
                                                             t_wkt=pp.CRS(self.steps[-1]["crs_to"]).to_wkt(),
                                                             n_sample=20,
                                                             s_raster_metadata=None,
                                                             t_raster_metadata=None,
                                                             s_point_samples=list(zip(x, y, z)),
                                                             t_point_samples=list(zip(xt, yt, zt)),
                                                             tolerance=0.3,
                                                             raster_sampling_band=1,
                                                             region=None,
                                                             pivot_h_crs="EPSG:6318",
                                                             s_h_frame=None,
                                                             s_v_frame=None,
                                                             s_h_zone=None,
                                                             t_h_frame=None,
                                                             t_v_frame=None,
                                                             t_h_zone=None
                                                            )
                if not vdatum_cv:
                    success = False
                    csv_path = os.path.join(os.getcwd(), "vdatum_check.csv")
                    vdatum_df.to_csv(csv_path, index=False)
                    logger.info(f"{Fore.RED}Vdatum checks on point data failed. "
                                f"VDatum API outputs stored at: {csv_path}")
                    print(Style.RESET_ALL)
                    return success, None, None, None

        except Exception:
            logger.exception("Error while running the point transformation.")
            return success, None, None, None
        finally:
            return success, xt, yt, zt

    def transform_vrbag(self,
                        input_file: str,
                        output_file: str,
                        pre_post_checks: bool = True,
                        vdatum_check: bool = True
                        ) -> bool:
        """
        Transform variable resolution BAG file.

        Parameters
        -----------
        input_file: str
            Path to the input vrbag file.
        output_file: str
            Path to the output transformed vrbag file.
        pre_post_checks: bool, default=True
            If True, runs a series of validation checks, such as validating the input and output
            CRSs, before and after transformation operation.
        vdatum_check: bool, default=True
            If True, a random sample of the transformed data are compared with transformation
            outcomes produced by Vdatum REST API.

        Raises
        -------
        FileNotFoundError:
            If the input file is not found.
        TypeError
            If the passed BAG file is not a valid variable resolution bag file.

        Returns
        -----------
        bool:
            True if successful, otherwise False.
        """
        try:
            success = False
            if not os.path.isfile(input_file):
                raise FileNotFoundError(f"The input file not found at {input_file}.")
            if not vrbag.is_vr(fname=input_file):
                msg = (f"The following file is not a valid variable resolution bag file: {input_file}")
                logger.exception(msg)
                raise TypeError(msg)
            pathlib.Path(os.path.split(output_file)[0]).mkdir(parents=True, exist_ok=True)
            shutil.copy2(input_file, output_file)
            if pre_post_checks:
                drivers_utils.vrbag_pre_transformation_checks(file_path=input_file,
                                                              source_crs=self.crs_from
                                                              )
            success = vrbag.transform(fname=output_file,
                                      tf=self, point_transformation=True,
                                      vdatum_check=vdatum_check)
            if pre_post_checks:
                drivers_utils.vrbag_post_transformation_checks(file_path=output_file,
                                                               target_crs=self.crs_to
                                                               )
        except Exception as e:
            logger.exception(f"Exception in `transform_vrbag()`: {str(e)}")
            if os.path.isfile(output_file):
                os.remove(output_file)
        finally:
            return success

    def transform_laz(self,
                      input_file: str,
                      output_file: str,
                      pre_post_checks: bool = True,
                      vdatum_check: bool = True
                      ) -> bool:
        """
        Transform point-cloud LAZ file.

        Parameters
        -----------
        input_file: str
            Path to the input laz file.
        output_file: str
            Path to the output transformed laz file.
        pre_post_checks: bool, default=True
            If True, runs a series of validation checks, such as validating the input and output
            CRSs, before and after transformation operation.
        vdatum_check: bool, default=True
            If True, a random sample of the transformed data are compared with transformation
            outcomes produced by Vdatum REST API.

        Raises
        -------
        FileNotFoundError:
            If the input file is not found.
        TypeError
            If the passed LAZ file is not valid.

        Returns
        -----------
        bool:
            True if successful, otherwise False.
        """
        try:
            success = False
            if not os.path.isfile(input_file):
                raise FileNotFoundError(f"The input file not found at {input_file}.")
            pathlib.Path(os.path.split(output_file)[0]).mkdir(parents=True, exist_ok=True)
            shutil.copy2(input_file, output_file)
            lz = laz.LAZ(input_file=output_file)
            if pre_post_checks:
                drivers_utils.laz_pre_transformation_checks(file_path=input_file,
                                                            source_crs=self.crs_from
                                                            )
            success = lz.transform(transformer_instance=self, vdatum_check=vdatum_check)
            if pre_post_checks:
                drivers_utils.laz_post_transformation_checks(file_path=output_file,
                                                             target_crs=self.crs_to
                                                             )
        except Exception as e:
            logger.exception(f"Exception in `transform_laz()`: {str(e)}")
            if os.path.isfile(output_file):
                os.remove(output_file)
        finally:
            return success

    def transform_xyz(self,
                      input_file: str,
                      output_file: str,
                      pre_post_checks: bool = True,
                      vdatum_check: bool = True,
                      **kwargs
                      ) -> bool:
        """
        Transform point-cloud XYZ file.

        Parameters
        -----------
        input_file: str
            Path to the input xyz file.
        output_file: str
            Path to the output transformed xyz file.
        pre_post_checks: bool, default=True
            If True, runs a series of validation checks, such as validating the input and output
            CRSs, before and after transformation operation.
        vdatum_check: bool, default=True
            If True, a random sample of the transformed data are compared with transformation
            outcomes produced by Vdatum REST API.

        Raises
        -------
        FileNotFoundError:
            If the input file is not found.
        TypeError
            If the passed xyz file is not valid.

        Returns
        -----------
        bool:
            True if successful, otherwise False.
        """
        try:
            success = False
            if not os.path.isfile(input_file):
                raise FileNotFoundError(f"The input file not found at {input_file}.")
            pathlib.Path(os.path.split(output_file)[0]).mkdir(parents=True, exist_ok=True)
            xyz_ins = xyz.XYZ(input_file=input_file, **kwargs)

            success = xyz_ins.transform(transformer_instance=self,
                                        output_file=output_file,
                                        pre_post_checks=pre_post_checks,
                                        vdatum_check=vdatum_check)
        except Exception as e:
            logger.exception(f"Exception in `transform_xyz()`: {str(e)}")
            if os.path.isfile(output_file):
                os.remove(output_file)
        finally:
            return success

    def transform_geoparquet(self,
                             input_file: str,
                             output_file: str,
                             pre_post_checks: bool = True,
                             vdatum_check: bool = True
                             ) -> bool:
        """
        Transform a geoparquet point file.

        Parameters
        -----------
        input_file: str
            Path to the input geoparquet file.
        output_file: str
            Path to the output transformed file.
        pre_post_checks: bool, default=True
            If True, runs a series of validation checks, such as validating the input and output
            CRSs, before and after transformation operation.
        vdatum_check: bool, default=True
            If True, a random sample of the transformed data are compared with transformation
            outcomes produced by Vdatum REST API.

        Raises
        -------
        FileNotFoundError:
            If the input file is not found.
        TypeError
            If the passed file is not valid.

        Returns
        -----------
        bool:
            True if successful, otherwise False.
        """
        try:
            success = False
            if not os.path.isfile(input_file):
                raise FileNotFoundError(f"The input file not found at {input_file}.")
            pathlib.Path(os.path.split(output_file)[0]).mkdir(parents=True, exist_ok=True)
            gp = gparq.GeoParquet(input_file=input_file)

            success = gp.transform(transformer_instance=self,
                                   output_file=output_file,
                                   pre_post_checks=pre_post_checks,
                                   vdatum_check=vdatum_check)
        except Exception as e:
            logger.exception(f"Exception in `transform_geoparquet()`: {str(e)}")
            if os.path.isfile(output_file):
                os.remove(output_file)
        finally:
            return success

    def transform_npz(self,
                      input_file: str,
                      output_file: str,
                      pre_post_checks: bool = True,
                      vdatum_check: bool = True
                      ) -> bool:
        """
        Transform a numpy npz file.

        Parameters
        -----------
        input_file: str
            Path to the input npz file.
        output_file: str
            Path to the output transformed npz file.
        pre_post_checks: bool, default=True
            If True, runs a series of validation checks, such as validating the input and output
            CRSs, before and after transformation operation.
        vdatum_check: bool, default=True
            If True, a random sample of the transformed data are compared with transformation
            outcomes produced by Vdatum REST API.

        Raises
        -------
        FileNotFoundError:
            If the input file is not found.
        TypeError
            If the passed npz file is not valid.

        Returns
        -----------
        bool:
            True if successful, otherwise False.
        """
        try:
            success = False
            if not os.path.isfile(input_file):
                raise FileNotFoundError(f"The input file not found at {input_file}.")
            pathlib.Path(os.path.split(output_file)[0]).mkdir(parents=True, exist_ok=True)
            shutil.copy2(input_file, output_file)
            nz = npz.NPZ(input_file=output_file)
            if pre_post_checks:
                drivers_utils.npz_pre_transformation_checks(file_path=input_file,
                                                            source_crs=self.crs_from
                                                            )
            success = nz.transform(transformer_instance=self, vdatum_check=vdatum_check)
            if pre_post_checks:
                drivers_utils.npz_post_transformation_checks(file_path=input_file,
                                                             target_crs=self.crs_to
                                                             )
        except Exception as e:
            logger.exception(f"Exception in `transform_npz()`: {str(e)}")
            if os.path.isfile(output_file):
                os.remove(output_file)
        finally:
            return success

    def transform_pdal(self,
                       input_file: str,
                       output_file: str,
                       pre_post_checks: bool = True,
                       vdatum_check: bool = True
                       ) -> bool:
        """
        Transform point-cloud data using PDAL.

        Parameters
        -----------
        input_file: str
            Path to the input file.
        output_file: str
            Path to the output transformed file.
        pre_post_checks: bool, default=True
            If True, runs a series of validation checks, such as validating the input and output
            CRSs, before and after transformation operation.
        vdatum_check: bool, default=True
            If True, a random sample of the transformed data are compared with transformation
            outcomes produced by Vdatum REST API.

        Raises
        -------
        FileNotFoundError:
            If the input file is not found.
        TypeError
            If the passed file is not valid.

        Returns
        -----------
        bool:
            True if successful, otherwise False.
        """
        # TODO implement vdatum_check in pd.transform()
        try:
            success = False
            if not input_file.lower().startswith("http") and not os.path.isfile(input_file):
                raise FileNotFoundError(f"The input file not found at {input_file}.")
            pathlib.Path(os.path.split(output_file)[0]).mkdir(parents=True, exist_ok=True)
            pdl = pdal_based.PDAL(input_file=input_file, output_file=output_file)
            if pre_post_checks:
                drivers_utils.pdal_pre_transformation_checks(file_path=input_file,
                                                             source_crs=self.crs_from
                                                             )
            success = pdl.transform(transformer_instance=self, vdatum_check=vdatum_check)
            if pre_post_checks:
                drivers_utils.pdal_post_transformation_checks(file_path=input_file,
                                                              target_crs=self.crs_to
                                                              )
        except Exception as e:
            logger.exception(f"Exception in `transform_pdal()`: {e}")
            if os.path.isfile(output_file):
                os.remove(output_file)
        finally:
            return success

    def transform_raster(self,
                         input_file: str,
                         output_file: str,
                         overview: bool = True,
                         pre_post_checks: bool = True,
                         vdatum_check: bool = True,
                         _allow_different_horizontal_crs: bool = False,
                         ) -> bool:
        """
        Transform the gdal-supported input rater file (`input_file`) and store the
        transformed file on the local disk (`output_file`).

        Horizontal CRS limitation
        -------------------------
        As of this release, raster transformation requires the input and
        output horizontal CRSs to match. The current pipeline anchors the
        output to the input's pixel grid (origin, resolution, dimensions)
        which is well-defined only when both ends share a horizontal CRS;
        across different horizontal CRSs the existing code path produces
        non-elevation bands that are silently misregistered. Attempting to
        run such a transformation raises ``NotImplementedError`` by
        default. The bypass parameter ``_allow_different_horizontal_crs``
        is intended for development testing only and should not be used
        in production until the different-horizontal-CRS path has been
        properly implemented.

        Raises
        -------
        FileNotFoundError:
            If the input raster file is not found.
        NotImplementedError:
            If the input file is not supported by gdal, or if the input
            and output horizontal CRSs differ and the bypass flag is not
            set.

        Parameters
        -----------
        input_file: str
            Path to the input raster file (gdal supported).
        output_file: str
            Path to the transformed raster file.
        overview: bool, default=True
            If True, overview bands are added to the output raster file (only GTiff support).
        pre_post_checks: bool, default=True
            If True, runs a series of validation checks, such as validating the input and output
            CRSs, before and after transformation operation.
        vdatum_check: bool, default=True
            If True, a random sample of the transformed data are compared with transformation
            outcomes produced by Vdatum REST API.
        _allow_different_horizontal_crs: bool, default=False
            Development bypass for the horizontal-CRS-equality safety
            check. Leave at its default in production. Setting True
            permits transformations across different horizontal CRSs but
            does not guarantee correct results.


        Returns
        --------
        bool:
            True if successful, otherwise False.
        """
        def steps_to_concat_pipe(steps, input_metadata):
            concat_pipe = "+proj=pipeline "
            v_shift = False
            grid_files = []  # Track grid files used
            for step in steps:
                pipe = crs_utils.pipeline_string(step["crs_from"], step["crs_to"], input_metadata)
                concat_pipe = f"{concat_pipe} {pipe.split('+proj=pipeline')[1]}"
                if step["v_shift"]:
                    v_shift = True
            grid_files = re.findall(r'\+grids=([^\s]+)', concat_pipe)
            return concat_pipe, v_shift, grid_files

        # Horizontal-CRS equality check. Same-horizontal-CRS is the only
        # path that is fully validated. Different-horizontal-CRS produces
        # a result whose output pixel grid is undefined relative to the
        # input and whose non-elevation bands are silently misregistered
        # by overwrite_with_original. The check is performed before any
        # other work and before the ``try`` block, so a misconfigured
        # call fails loudly rather than being caught and written to a
        # ``*_error.txt`` file alongside other transformation errors.
        try:
            h_from, _ = crs_utils.crs_components(self.crs_from, raise_no_auth=False)
            h_to, _ = crs_utils.crs_components(self.crs_to, raise_no_auth=False)
        except Exception:
            h_from, h_to = None, None
        if (
            not _allow_different_horizontal_crs
            and h_from is not None
            and h_to is not None
            and h_from != h_to
        ):
            raise NotImplementedError(
                "transform_raster currently requires the input and output "
                "horizontal CRSs to match. "
                f"Input horizontal CRS:  {h_from}. "
                f"Output horizontal CRS: {h_to}. "
                "The existing pipeline anchors the output to the input's "
                "pixel grid, which is well-defined only when both ends "
                "share a horizontal CRS. Cross-CRS raster transformation "
                "(for example UTM to Geographic, or UTM to State Plane) "
                "is on the roadmap but not yet implemented. For now, "
                "convert to point-cloud format (e.g. GeoParquet, LAZ) "
                "and use the corresponding driver, which handles "
                "different horizontal CRSs correctly."
            )

        self._validate_input_file(input_file)
        try:
            success = False
            input_file_cut = None
            ds = None
            ds_pass1 = None
            output_ds = None
            temp_pass1 = None
            tiles_dir = None
            if not str(output_file).lower().startswith("/vsimem/"):
                pathlib.Path(os.path.split(output_file)[0]).mkdir(parents=True, exist_ok=True)
            input_metadata = raster_metadata(input_file)
            pipe, v_shift, grid_files = steps_to_concat_pipe(self.steps, input_metadata)

            logger.info(f"Transformation Steps: {self.steps}")
            logger.info(f"Concatenated PROJ pipeline:\n{pipe}\n")
            output_vrt = Path(output_file).with_suffix(".vrt")
            with gdal.Open(input_file, gdal.GA_ReadOnly) as input_ds:
                geotransform = input_ds.GetGeoTransform()
                xres, yres = geotransform[1], geotransform[5]



            # Create cutline if vertical shift and NWLD grids are involved, otherwise return None
            # TODO: what if more than one NWLD grids are involved?
            cutline_path, overlap_pct = raster_utils.create_cutline_file(v_shift, grid_files,
                                                                         cutline_path=str(Path(output_file).parent / f"{Path(output_file).stem}_cutline.gpkg"),
                                                                         input_metadata=input_metadata
                                                                         )
            original_input_file = copy.deepcopy(input_file)
            original_metadata = copy.deepcopy(input_metadata)
            wopt = ["SAMPLE_GRID=YES", "SAMPLE_STEPS=ALL"]
            if v_shift:
                wopt.append("APPLY_VERTICAL_SHIFT=YES")


            # if cutline_path and overlap_pct < 50:
            if cutline_path:
                # When the overlap between the input raster and the underlying
                # NWLD/underkeel grid is small, a single gdal.Warp combining
                # coordinate transformation and cutline masking can fail or
                # produce incorrect output. The work is therefore split into
                # two passes: Pass 1 applies the coordinate transformation
                # against the cutline-clipped input, and Pass 2 expands the
                # transformed result back to the original extent while masking
                # pixels outside the cutline polygon to NoData. The clip,
                # Pass 1, and Pass 2 are all anchored to the input raster's
                # pixel grid so the output is pixel-for-pixel registered with
                # the input (same-CRS case).
                input_file = raster_utils.clip_raster_to_cutline(input_file, cutline_path,
                                                                 output_path=str(Path(output_file).parent / f"{Path(output_file).stem}_cut_to_grid{Path(output_file).suffix}"))
                input_file_cut = input_file
                cut_metadata = raster_metadata(input_file_cut)

                # PASS 1: Transform mathematically.
                #
                # Pass 1's output is materialized as a real GeoTIFF rather
                # than a VRT. Writing format='vrt' produces a lazy dataset
                # that stores the coordinate operation pipeline and
                # evaluates pixel values on demand against the underlying
                # cut file. When Pass 2 later reads from such a VRT and
                # asks for output pixels outside Pass 1's safe-evaluation
                # region (because Pass 2 expands the extent back to the
                # full original input), GDAL re-runs the embedded pipeline
                # against the NWLD or underkeel grid for those pixels. If
                # the requested pixels fall over partial-coverage grid
                # cells (the case when the input raster crosses a grid
                # boundary, e.g. the Great Lakes Tile40 case), the
                # evaluation returns nodata and the warp aborts with
                # "Cannot determine source window". Materializing Pass 1
                # to a flat GeoTIFF resolves all pixels eagerly, leaving
                # Pass 2 to read a plain raster with no embedded
                # transformer.
                temp_pass1 = str(output_vrt).replace('.vrt', '_pass1.tif')
                cop = ["COMPRESS=DEFLATE", "TILED=YES"]
                if original_metadata["driver"].lower() == "gtiff":
                    cop.append("BIGTIFF=YES")                
                warp_kwargs_pass1 = {
                    "format": "GTiff",
                    "outputType": gdal.gdalconst.GDT_Float32,
                    "warpOptions": wopt,
                    "errorThreshold": 0,
                    "xRes": abs(xres),
                    "yRes": abs(yres),
                    "coordinateOperation": pipe,
                    "dstNodata": original_metadata["band_no_data"][0],
                    "creationOptions": cop,
                }

                same_crs_branch = not (crs_utils.multiple_geodetic_crs(self.steps) or crs_utils.multiple_projections(self.steps))
                cut_W, cut_H = 0, 0
                if same_crs_branch:
                    dims = cut_metadata.get("dimensions")
                    if dims and "x" in str(dims):
                        cut_W = int(str(dims).split("x")[0].strip())
                        cut_H = int(str(dims).split("x")[1].strip())
                    else:
                        raise ValueError(f"Aborting: Cut metadata dimensions are invalid or empty for Pass 1 processing.")

                tile_size = int(os.environ.get("VYPER_PASS1_TILE_SIZE", str(PASS1_DEFAULT_TILE_SIZE)))
                use_tiled_pass1 = same_crs_branch and (cut_W * cut_H > PASS1_TILED_PIXEL_THRESHOLD)

                if use_tiled_pass1:
                    temp_pass1 = str(output_vrt).replace('.vrt', '_pass1.vrt')
                    tiles_dir = _pass1_warp_tiled(input_file, temp_pass1, warp_kwargs_pass1,
                                                  cut_metadata, tile_size)
                    ds_pass1 = gdal.Open(temp_pass1)
                    if ds_pass1 is None:
                        raise RuntimeError(f"Could not open Pass 1 VRT mosaic: {temp_pass1}")
                else:
                    if same_crs_branch:
                        warp_kwargs_pass1["outputBounds"] = cut_metadata["extent"]
                        warp_kwargs_pass1["width"] = cut_W
                        warp_kwargs_pass1["height"] = cut_H
                    ds_pass1 = gdal.Warp(temp_pass1, input_file, **warp_kwargs_pass1)

                # PASS 2: Expand to the original input's pixel grid and
                # apply the cutline as a mask only. Pass 1's output is
                # already in the target CRS, so Pass 2 must not invoke any
                # coordinate transformation. To prevent GDAL from inferring
                # an unwanted pipeline (which can re-apply the vertical
                # shift over partial-coverage grid regions and fail with
                # "Cannot determine source window"), srcSRS and dstSRS are
                # both explicitly set to the target CRS WKT so the warp is
                # known to be an extent-only operation. cropToCutline is
                # deliberately not set; with cropToCutline=True, GDAL
                # overrides the explicit outputBounds with the cutline
                # polygon's envelope, producing an output on a grid that
                # does not match the input. Using cutlineDSName alone
                # leaves outputBounds in charge and converts pixels
                # outside the cutline polygon to dstNodata. srcNodata is
                # set to the same value as dstNodata so Pass 1's filled
                # NoData regions are treated as transparent during the
                # expansion.
                _pass2_crs_wkt = self.crs_to.to_wkt()
                _pass2_nodata = original_metadata["band_no_data"][0]
                warp_kwargs_pass2 = {
                    "format": "vrt",
                    "outputType": gdal.gdalconst.GDT_Float32,
                    "errorThreshold": 0,
                    "resampleAlg": "near",
                    "xRes": abs(xres),
                    "yRes": abs(yres),
                    "cutlineDSName": cutline_path,
                    "srcSRS": _pass2_crs_wkt,
                    "dstSRS": _pass2_crs_wkt,
                    "srcNodata": _pass2_nodata,
                    "dstNodata": _pass2_nodata,
                }

                if not (crs_utils.multiple_geodetic_crs(self.steps) or crs_utils.multiple_projections(self.steps)):
                    warp_kwargs_pass2["outputBounds"] = original_metadata["extent"]
                    dims = original_metadata.get("dimensions")
                    if dims and "x" in str(dims):
                        warp_kwargs_pass2["width"] = int(str(dims).split("x")[0].strip())
                        warp_kwargs_pass2["height"] = int(str(dims).split("x")[1].strip())
                    else:
                        raise ValueError(f"Aborting: Original metadata dimensions are invalid or empty for Pass 2 processing.")

                # Warp the output of Pass 1 (no coordinateOperation needed, it's already transformed)
                ds = gdal.Warp(output_vrt, ds_pass1, **warp_kwargs_pass2)

            else:
                warp_kwargs = {
                    "format": "vrt",
                    "outputType": gdal.gdalconst.GDT_Float32,
                    "warpOptions": wopt,
                    "errorThreshold": 0,
                    "xRes": abs(xres),
                    "yRes": abs(yres),
                    "coordinateOperation": pipe,
                    "dstNodata": original_metadata["band_no_data"][0]
                }
                if not (crs_utils.multiple_geodetic_crs(self.steps) or crs_utils.multiple_projections(self.steps)):
                    warp_kwargs["outputBounds"] = original_metadata["extent"]
                ds = gdal.Warp(output_vrt, input_file, **warp_kwargs)

            # FUSE might have already created a file with the same name; check
            # for an existing output and rename to avoid overwriting it.
            if gdal.VSIStatL(output_file) is not None:
                suffix = "_vyperdatum"
                op = Path(output_file)
                new_name = f"{op.stem}{suffix}{op.suffix}"
                output_file = str(op.with_name(new_name))

            cop = ["COMPRESS=DEFLATE"]
            if input_metadata["driver"].lower() == "gtiff":
                cop.extend(["TILED=YES", "BIGTIFF=YES"])
                try:
                    bx, by = input_metadata["block_size"][0]
                    if by > 1 and bx % 16 == 0 and by % 16 == 0:
                        cop.extend([f"BLOCKXSIZE={int(bx)}", f"BLOCKYSIZE={int(by)}"])
                    else:
                        cop.extend([f"BLOCKXSIZE=256", f"BLOCKYSIZE=256"])
                except Exception as e:
                    logger.warning("Could not parse block size from input raster metadata. "
                                   f"Found invalid block_size value: {input_metadata.get('block_size')}."
                                   f"\n Exception: {str(e)}")
            if input_metadata["driver"].lower() == "bag":
                try:
                    block_size = min(int(input_metadata["block_size"][0][0]),
                                     int(input_metadata["block_size"][0][1]))  # take the smaller block size (x, y)
                    cop.append(f"BLOCK_SIZE={block_size}")
                except Exception as e:
                    logger.warning("Could not parse block size from input raster metadata. "
                                   f"Found invalid block_size value: {input_metadata['block_size'][0]}."
                                   f"\n Exception: {str(e)}")

            output_ds = gdal.Translate(output_file, ds, format=input_metadata["driver"],
                                       outputType=gdal.GDT_Float32,
                                       creationOptions=cop)
            if gdal.VSIStatL(output_file) is None:
                logger.error(f"Output raster was not created: {output_file}")
                logger.error(f"GDAL last error: {gdal.GetLastErrorMsg()}")
                return False
            output_ds = None
            ds = None

            # Reference for non-elevation bands is always the original input.
            # After the cutline-anchored two-pass warp, output dimensions
            # match the original input exactly in the same-CRS case, so
            # bands can be copied verbatim. In the different-CRS case,
            # overwrite_with_original falls back to GDAL resampling and
            # logs a warning (see its docstring).
            overwrite_with_original(original_input_file, output_file)

            update_raster_wkt(output_file, self.crs_to.to_wkt())
            apply_nbs_band_standards(output_file)
            add_vyper_tag(output_file, pipe, self.crs_to, self.steps)
            input_metadata = original_metadata
            output_metadata = raster_metadata(output_file)

            if pre_post_checks:
                raster_utils.raster_post_transformation_checks(source_meta=input_metadata,
                                                               target_meta=output_metadata,
                                                               target_crs=self.crs_to,
                                                               vertical_transform=v_shift
                                                               )
            success = True
            if vdatum_check:
                vdatum_cv, vdatum_df = vdatum_cross_validate(s_wkt=input_metadata["wkt"],
                                                             t_wkt=output_metadata["wkt"],
                                                             n_sample=20,
                                                             s_raster_metadata=input_metadata,
                                                             t_raster_metadata=output_metadata,
                                                             s_point_samples=None,
                                                             t_point_samples=None,
                                                             tolerance=0.3,
                                                             raster_sampling_band=1,
                                                             region=None,
                                                             pivot_h_crs="EPSG:6318",
                                                             s_h_frame=None,
                                                             s_v_frame=None,
                                                             s_h_zone=None,
                                                             t_h_frame=None,
                                                             t_v_frame=None,
                                                             t_h_zone=None
                                                             )
                csv_path = os.path.join(os.path.split(output_file)[0],
                                        os.path.split(output_file)[1].split(".")[0] + "_vdatum_check.csv")
                vdatum_df.to_csv(csv_path, index=False)
                if not vdatum_cv:
                    success = False
                    logger.info(f"{Fore.RED}VDatum API outputs stored at: {csv_path}")
                    print(Style.RESET_ALL)

            if overview and input_metadata["driver"].lower() == "gtiff":
                raster_utils.add_overview(raster_file=output_file,
                                          compression="DEFLATE"
                                          )

        except Exception as e:
            out_dir = Path(output_file).parent.absolute()
            if str(output_file).lower().startswith("/vsimem/"):
                out_dir = Path(os.getcwd())

            efile = open(out_dir / f"{os.path.split(input_file)[1]}_error.txt", "w")
            efile.write(str(e))
            efile.close()
        finally:
            ds, ds_pass1, output_ds = None, None, None
            def safe_remove(path):
                if path is None:
                    return
                if gdal.VSIStatL(path) is not None:
                    try:
                        gdal.Unlink(path)
                    except Exception as e:
                        logger.warning(f"Could not delete temporary file {path}. Exception: {str(e)}")
            safe_remove(output_vrt)
            safe_remove(temp_pass1)
            safe_remove(cutline_path)
            safe_remove(input_file_cut)
            if tiles_dir is not None:
                try:
                    if Path(str(tiles_dir)).exists():
                        shutil.rmtree(str(tiles_dir))
                except Exception as e:
                    logger.warning(f"Could not delete Pass 1 tiles directory {tiles_dir}. Exception: {str(e)}")
            return success

    def transform_vector(self,
                         input_file: str,
                         output_file: str
                         ) -> bool:
        """
        Transform the gdal-supported input vector file (`input_file`) and store the
        transformed file on the local disk (`output_file`).

        Raises
        -------
        FileNotFoundError:
            If the input vector file is not found.
        NotImplementedError:
            If the input vector file is not supported by gdal.

        Parameters
        -----------
        input_file: str
            Path to the input vector file (gdal supported).
        output_file: str
            Path to the transformed vector file.

        Returns
        --------
        bool:
            True if successful, otherwise False.
        """
        try:
            self._validate_input_file(input_file)
            pathlib.Path(os.path.split(output_file)[0]).mkdir(parents=True, exist_ok=True)
            pbar, success = None, False
            ds = gdal.OpenEx(input_file)
            driver = ogr.GetDriverByName(ds.GetDriver().ShortName)
            inSpatialRef = osr.SpatialReference()
            inSpatialRef.ImportFromWkt(self.crs_from.to_wkt())
            outSpatialRef = osr.SpatialReference()
            outSpatialRef.ImportFromWkt(self.crs_to.to_wkt())
            coordTrans = osr.CoordinateTransformation(inSpatialRef, outSpatialRef)
            inDataSet = driver.Open(input_file)
            if os.path.exists(output_file):
                driver.DeleteDataSource(output_file)
            outDataSet = driver.CreateDataSource(output_file)
            layer_count = inDataSet.GetLayerCount()
            for layer_index in range(layer_count):
                inLayer = inDataSet.GetLayer(layer_index)
                outLayer = outDataSet.CreateLayer(inLayer.GetName(), geom_type=ogr.wkbMultiPolygon)
                inLayerDefn = inLayer.GetLayerDefn()
                for i in range(0, inLayerDefn.GetFieldCount()):
                    fieldDefn = inLayerDefn.GetFieldDefn(i)
                    outLayer.CreateField(fieldDefn)
                outLayerDefn = outLayer.GetLayerDefn()
                inFeature = inLayer.GetNextFeature()
                feature_count = inLayer.GetFeatureCount()
                pbar = tqdm(total=feature_count)
                feature_counter = 0
                while inFeature:
                    geom = inFeature.GetGeometryRef()
                    geom.Transform(coordTrans)
                    outFeature = ogr.Feature(outLayerDefn)
                    outFeature.SetGeometry(geom)
                    for i in range(0, outLayerDefn.GetFieldCount()):
                        outFeature.SetField(outLayerDefn.GetFieldDefn(i).GetNameRef(), inFeature.GetField(i))
                    outLayer.CreateFeature(outFeature)
                    outFeature = None
                    inFeature = inLayer.GetNextFeature()
                    feature_counter += 1
                    pbar.update(1)
                    pbar.set_description(f"Processing Layer {layer_index+1} / {layer_count}")
            inDataSet, outDataSet, ds = None, None, None
            success = True
        finally:
            if pbar:
                pbar.close()
            return success
