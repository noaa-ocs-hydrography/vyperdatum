import os
import pathlib
import shutil
from importlib.metadata import version
import io
import sys
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
from vyperdatum.utils.raster_utils import raster_metadata, update_raster_wkt
from vyperdatum.utils.vdatum_rest_utils import vdatum_cross_validate
from vyperdatum.drivers import vrbag, laz, npz, pdal_based
from vyperdatum.pipeline import nwld_ITRF2020_steps, nwld_NAD832011_steps

logger = logging.getLogger("root_logger")
gdal.UseExceptions()


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
            raise ValueError("Invalid transformation pipeline.")
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
                  vdatum_check: bool = False
                  ):
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
        None
        """
        if not os.path.isfile(input_file):
            raise FileNotFoundError(f"The input file not found at {input_file}.")

        if vrbag.is_vr(fname=input_file):
            logger.info(f"Identified as vrbag file: {input_file}")
            self.transform_vrbag(input_file=input_file,
                                 output_file=output_file,
                                 pre_post_checks=pre_post_checks,
                                 vdatum_check=vdatum_check
                                 )
        elif laz.LAZ(input_file=input_file, invalid_error=False).is_valid:
            logger.info(f"Identified as laz file: {input_file}")
            self.transform_laz(input_file=input_file,
                               output_file=output_file,
                               pre_post_checks=pre_post_checks,
                               vdatum_check=vdatum_check
                               )
        elif npz.NPZ(input_file=input_file, invalid_error=False).is_valid:
            logger.info(f"Identified as npz file: {input_file}")
            self.transform_npz(input_file=input_file,
                               output_file=output_file,
                               pre_post_checks=pre_post_checks,
                               vdatum_check=vdatum_check
                               )
        elif pathlib.Path(input_file).suffix.lower() in self.gdal_extensions():
            logger.info(f"Identified as GDAL-supported raster file: {input_file}")
            self.transform_raster(input_file=input_file,
                                  output_file=output_file,
                                  pre_post_checks=pre_post_checks,
                                  vdatum_check=vdatum_check
                                  )
        elif pdal_based.PDAL(input_file=input_file,
                             output_file=output_file, invalid_error=False).is_valid:
            logger.info(f"Identified as PDAL-supported file: {input_file}")
            self.transform_pdal(input_file=input_file,
                                output_file=output_file,
                                pre_post_checks=pre_post_checks,
                                vdatum_check=vdatum_check
                                )
        # elif vector files
        else:
            raise NotImplementedError(f"Unsupported input file: {input_file}")
        return

    def transform_points(self,
                         x: Union[float, int, list, np.ndarray],
                         y: Union[float, int, list, np.ndarray],
                         z: Union[float, int, list, np.ndarray],
                         always_xy: bool = False,
                         vdatum_check: bool = True,
                         area_of_interest: Optional[AreaOfInterest] = None,
                         authority: Optional[str] = None,
                         accuracy: Optional[float] = None,
                         allow_ballpark: Optional[bool] = False,
                         force_over: bool = False,
                         only_best: Optional[bool] = True
                         ) -> tuple[Optional[Union[list, np.ndarray]],
                                    Optional[Union[list, np.ndarray]],
                                    Optional[Union[list, np.ndarray]]]:
        """
        Conduct point transformation between two coordinate reference systems.        

        Parameters
        ----------
        x: numeric scalar or array
           Input x coordinate(s).
        y: numeric scalar or array
           Input y coordinate(s).
        z: numeric scalar or array, optional
           Input z coordinate(s).
        always_xy: bool, default=False
            If true, the transform method will accept as input and return as output
            coordinates using the traditional GIS order, that is longitude, latitude
            for geographic CRS and easting, northing for most projected CRS.
        vdatum_check: bool, default=True
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
        allow_ballpark: bool, optional, default=False
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
        """

        try:
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
                    csv_path = os.path.join(os.getcwd(), "vdatum_check.csv")
                    vdatum_df.to_csv(csv_path, index=False)
                    logger.info(f"{Fore.RED}Vdatum checks on point data failed. "
                                f"VDatum API outputs stored at: {csv_path}")
                    print(Style.RESET_ALL)
                    return None, None, None

        except Exception:
            logger.exception("Error while running the point transformation.")
            return None, None, None
        return xt, yt, zt

    def transform_vrbag(self,
                        input_file: str,
                        output_file: str,
                        pre_post_checks: bool = True,
                        vdatum_check: bool = True
                        ):
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
        None
        """
        if not os.path.isfile(input_file):
            raise FileNotFoundError(f"The input file not found at {input_file}.")
        if not vrbag.is_vr(fname=input_file):
            msg = (f"The following file is not a valid variable resolution bag file: {input_file}")
            logger.exception(msg)
            raise TypeError(msg)
        try:
            pathlib.Path(os.path.split(output_file)[0]).mkdir(parents=True, exist_ok=True)
            shutil.copy2(input_file, output_file)
            if pre_post_checks:
                drivers_utils.vrbag_pre_transformation_checks(file_path=input_file,
                                                              source_crs=self.crs_from
                                                              )
            vrbag.transform(fname=output_file, tf=self, point_transformation=True, vdatum_check=vdatum_check)
            if pre_post_checks:
                drivers_utils.vrbag_post_transformation_checks(file_path=output_file,
                                                               target_crs=self.crs_to
                                                               )
        except Exception as e:
            logger.exception(f"Exception in `transform_vrbag()`: {str(e)}")
            if os.path.isfile(output_file):
                os.remove(output_file)
        return

    def transform_laz(self,
                      input_file: str,
                      output_file: str,
                      pre_post_checks: bool = True,
                      vdatum_check: bool = True
                      ):
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
        None
        """
        if not os.path.isfile(input_file):
            raise FileNotFoundError(f"The input file not found at {input_file}.")
        try:
            pathlib.Path(os.path.split(output_file)[0]).mkdir(parents=True, exist_ok=True)
            shutil.copy2(input_file, output_file)
            lz = laz.LAZ(input_file=output_file)
            if pre_post_checks:
                drivers_utils.laz_pre_transformation_checks(file_path=input_file,
                                                            source_crs=self.crs_from
                                                            )
            lz.transform(transformer_instance=self, vdatum_check=vdatum_check)
            if pre_post_checks:
                drivers_utils.laz_post_transformation_checks(file_path=output_file,
                                                             target_crs=self.crs_to
                                                             )
        except Exception as e:
            logger.exception(f"Exception in `transform_laz()`: {str(e)}")
            if os.path.isfile(output_file):
                os.remove(output_file)
        return

    def transform_npz(self,
                      input_file: str,
                      output_file: str,
                      pre_post_checks: bool = True,
                      vdatum_check: bool = True
                      ):
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
        None
        """
        if not os.path.isfile(input_file):
            raise FileNotFoundError(f"The input file not found at {input_file}.")
        try:
            pathlib.Path(os.path.split(output_file)[0]).mkdir(parents=True, exist_ok=True)
            shutil.copy2(input_file, output_file)
            nz = npz.NPZ(input_file=output_file)
            if pre_post_checks:
                drivers_utils.npz_pre_transformation_checks(file_path=input_file,
                                                            source_crs=self.crs_from
                                                            )
            nz.transform(transformer_instance=self, vdatum_check=vdatum_check)
            if pre_post_checks:
                drivers_utils.npz_post_transformation_checks(file_path=input_file,
                                                             target_crs=self.crs_to
                                                             )
        except Exception as e:
            logger.exception(f"Exception in `transform_npz()`: {str(e)}")
            if os.path.isfile(output_file):
                os.remove(output_file)
        return

    def transform_pdal(self,
                       input_file: str,
                       output_file: str,
                       pre_post_checks: bool = True,
                       vdatum_check: bool = True
                       ):
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
        None
        """
        # TODO implement vdatum_check
        if not input_file.lower().startswith("http") and not os.path.isfile(input_file):
            raise FileNotFoundError(f"The input file not found at {input_file}.")
        try:
            pathlib.Path(os.path.split(output_file)[0]).mkdir(parents=True, exist_ok=True)
            pdl = pdal_based.PDAL(input_file=input_file, output_file=output_file)
            if pre_post_checks:
                drivers_utils.pdal_pre_transformation_checks(file_path=input_file,
                                                             source_crs=self.crs_from
                                                             )
            pdl.transform(transformer_instance=self, vdatum_check=vdatum_check)
            if pre_post_checks:
                drivers_utils.pdal_post_transformation_checks(file_path=input_file,
                                                              target_crs=self.crs_to
                                                              )
        except Exception as e:
            logger.exception(f"Exception in `transform_pdal()`: {e}")
            if os.path.isfile(output_file):
                os.remove(output_file)
        return

    def transform_raster(self,
                         input_file: str,
                         output_file: str,
                         overview: bool = False,
                         pre_post_checks: bool = True,
                         vdatum_check: bool = True,
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
            for step in steps:
                pipe = crs_utils.pipeline_string(step["crs_from"], step["crs_to"], input_metadata)
                concat_pipe = f"{concat_pipe} {pipe.split('+proj=pipeline')[1]}"
                if step["v_shift"]:
                    v_shift = True
            return concat_pipe, v_shift

        self._validate_input_file(input_file)
        try:
            success = False
            pathlib.Path(os.path.split(output_file)[0]).mkdir(parents=True, exist_ok=True)
            input_metadata = raster_metadata(input_file)
            pipe, v_shift = steps_to_concat_pipe(self.steps, input_metadata)

            logger.info(f"Transformation Steps: {self.steps}")
            logger.info(f"Concatenated PROJ pipeline:\n{pipe}\n")
            output_vrt = output_file.replace(".tif", ".vrt")
            with gdal.Open(input_file, gdal.GA_ReadOnly) as input_ds:
                geotransform = input_ds.GetGeoTransform()
                xres, yres = geotransform[1], geotransform[5]
            ds = gdal.Warp(output_vrt, input_file, format="vrt",
                           outputType=gdal.gdalconst.GDT_Float32,
                           warpOptions=["APPLY_VERTICAL_SHIFT=YES",
                                        "SAMPLE_GRID=YES",
                                        "SAMPLE_STEPS=ALL"],
                           errorThreshold=0,
                           xRes=xres,
                           yRes=yres,
                           outputBounds=input_metadata["extent"],
                           coordinateOperation=pipe
                           )
            pipe = re.sub(r"\s{2,}", " ", pipe).strip()
            to_wkt = self.crs_to.to_wkt()
            to_wkt = re.sub(r"\s{2,}", " ", to_wkt).strip()
            buffer = io.StringIO()
            sys.stdout = buffer
            pp.show_versions()
            sys.stdout = sys.__stdout__
            pyproj_versions = re.sub(r"\s{2,}", " ", buffer.getvalue()).strip()
            crs_h, crs_v = crs_utils.crs_components(self.crs_to, raise_no_auth=False)

            vyper_meta = {"description": ("This file is the output of a transformation pipeline "
                                          f"executed using Vyperdatum ({version('vyperdatum')})"
                                          " software by NOAA's OCS, NBS branch."),
                          "vyperdatum_version": version("vyperdatum"),
                          "steps": self.steps,
                          "proj_pipeline": pipe,
                          "wkt": to_wkt,
                          "crs_horizontal": crs_h if crs_h else "",
                          "crs_vertical": crs_v if crs_v else "",
                          "pyproj_versions": pyproj_versions,
                          }
            vyper_meta = json.dumps(vyper_meta)
            ds.SetMetadataItem("Vyperdatum_Metadata", vyper_meta)

            output_ds = gdal.Translate(output_file, ds, format="GTiff",
                                       outputType=gdal.GDT_Float32,
                                       creationOptions=["COMPRESS=DEFLATE", "TILED=YES"])
            output_ds = None
            update_raster_wkt(output_file, to_wkt)
            input_metadata = raster_metadata(input_file)
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
                efile = open(Path(output_file).parent.absolute()/Path(f"{os.path.split(input_file)[1]}_error.txt"), "w")
                efile.write(str(e))
                efile.close()
        finally:
            if os.path.isfile(output_vrt):
                os.remove(output_vrt)
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
