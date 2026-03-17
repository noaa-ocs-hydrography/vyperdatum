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
            ``only_best_default`` setting of :ref:`proj-ini`.
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
                         overview: bool = False,
                         pre_post_checks: bool = True,
                         vdatum_check: bool = True
                         ) -> bool:
        """
        Transform the gdal-supported input rater file (`input_file`) and store the
        transformed file on the local disk (`output_file`).

        Raises
        -------
        FileNotFoundError:
            If the input raster file is not found.
        NotImplementedError:
            If the input file is not supported by gdal.

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

        self._validate_input_file(input_file)
        try:
            success = False
            input_file_cut = None
            ds = None
            ds_pass1 = None
            output_ds = None
            temp_vrt_pass1 = None
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
                print(">>>>>>>>>>>>>>>>>>> CUTLINE PATH <<<<<<<<<<<<<<<<<<<<<<<")
                # gdal warp may fail if overlap between the input raster and the underlying grid
                # is too small, in which case we will use cutline to clip the input raster to the
                # area of overlap. I realized if we combine the coordinate transformation and
                # cutline masking in one gdal.Warp operation, the output can be wrong/fail.
                # So I separated the cutting and warping into two passes:
                # the first pass only does coordinate transformation without cutline masking,
                # and the second pass applies cutline masking without coordinate transformation.
                input_file = raster_utils.clip_raster_to_cutline(input_file, cutline_path,
                                                                 output_path=str(Path(output_file).parent / f"{Path(output_file).stem}_cut_to_grid{Path(output_file).suffix}"))
                input_file_cut = input_file
                cut_metadata = raster_metadata(input_file_cut)

                # PASS 1: Transform mathematically
                temp_vrt_pass1 = str(output_vrt).replace('.vrt', '_pass1.vrt')
                warp_kwargs_pass1 = {
                    "format": "vrt",
                    "outputType": gdal.gdalconst.GDT_Float32,
                    "warpOptions": wopt,
                    "errorThreshold": 0,
                    "xRes": abs(xres),
                    "yRes": abs(yres),
                    "coordinateOperation": pipe,
                    "dstNodata": original_metadata["band_no_data"][0],
                }
                if not (crs_utils.multiple_geodetic_crs(self.steps) or crs_utils.multiple_projections(self.steps)):
                    warp_kwargs_pass1["outputBounds"] = cut_metadata["extent"]
                    warp_kwargs_pass1["width"] = int(cut_metadata["dimensions"].split("x")[0].strip())
                    warp_kwargs_pass1["height"] = int(cut_metadata["dimensions"].split("x")[1].strip())

                ds_pass1 = gdal.Warp(temp_vrt_pass1, input_file, **warp_kwargs_pass1)

                # PASS 2: Expand geometry and apply mask
                warp_kwargs_pass2 = {
                    "format": "vrt",
                    "outputType": gdal.gdalconst.GDT_Float32,
                    "xRes": abs(xres),
                    "yRes": abs(yres),
                    "cutlineDSName": cutline_path,
                    "cropToCutline": False,
                    "dstNodata": original_metadata["band_no_data"][0],
                }

                if not (crs_utils.multiple_geodetic_crs(self.steps) or crs_utils.multiple_projections(self.steps)):
                    warp_kwargs_pass2["outputBounds"] = original_metadata["extent"]
                    warp_kwargs_pass2["width"] = int(original_metadata["dimensions"].split("x")[0].strip())
                    warp_kwargs_pass2["height"] = int(original_metadata["dimensions"].split("x")[1].strip())

                # Warp the output of Pass 1 (no coordinateOperation needed, it's already transformed)
                ds = gdal.Warp(output_vrt, ds_pass1, **warp_kwargs_pass2)

            else:
                print(">>>>>>>>>>>>>>>>>>> NO CUTLINE PATH <<<<<<<<<<<<<<<<<<<<<<<")
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

            # FUSE might have already created a file with the same name, so we need to check
            if gdal.VSIStatL(output_file) is not None:
                suffix = "_vyperdatum"
                op = Path(output_file)
                new_name = f"{op.stem}{suffix}{op.suffix}"
                output_file = str(op.with_name(new_name))

            cop = ["COMPRESS=DEFLATE"]
            if input_metadata["driver"].lower() == "gtiff":
                cop.append("TILED=YES")
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

            # if overview and input_metadata["driver"].lower() == "gtiff":
            #     raster_utils.add_overview(raster_file=output_file,
            #                               compression=input_metadata["compression"]
            #                               )
            #     # raster_utils.add_rat(output_file)

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
            safe_remove(temp_vrt_pass1)
            safe_remove(cutline_path)
            safe_remove(input_file_cut)
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
