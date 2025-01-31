import logging
from osgeo import gdal
from typing import Union
import pyproj as pp
from vyperdatum.drivers import vrbag
from vyperdatum.drivers.laz import LAZ
from vyperdatum.drivers.npz import NPZ
from vyperdatum.drivers.pdal_based import PDAL
from vyperdatum.utils.crs_utils import auth_code


logger = logging.getLogger("root_logger")
gdal.UseExceptions()


def vrbag_pre_transformation_checks(file_path: str,
                                    source_crs: Union[pp.CRS, str]
                                    ) -> bool:
    """
    Run a number of sanity checks on the source file before transformation.
    Warns if a check fails.

    Parameters
    ----------
    file_path: str
        Path to the input file.
    source_crs: pyproj.crs.CRS or input used to create one
        The expected CRS object for the vrbag file.

    Returns
    ----------
    bool
        Returns True if all checks pass, otherwise False.
    """
    passed = True
    if ~isinstance(source_crs, pp.CRS):
        source_crs = pp.CRS(source_crs)
    source_auth = auth_code(source_crs)
    file_auth = auth_code(pp.CRS(vrbag.wkt(fname=file_path)))
    if source_auth != file_auth:
        passed = False
        logger.warning("The authority name/code registered in the "
                       f"input file is {file_auth}, but received {source_auth}"
                       )
    if not vrbag.is_vr(file_path):
        passed = False
        logger.warning(f"The input file ({file_path}) is not a valid Vrbag file.")
    return passed


def vrbag_post_transformation_checks(file_path: str,
                                     target_crs: Union[pp.CRS, str]
                                     ) -> bool:
    """
    Run a number of sanity checks on the transformed vrbag file.
    Warns if a check fails.

    Parameters
    ----------
    file_path: str
        Path to the input file.
    target_crs: pyproj.crs.CRS or input used to create one
        The expected CRS object for the transformed file.

    Returns
    ----------
    bool
        Returns True if all checks pass, otherwise False.
    """
    if ~isinstance(target_crs, pp.CRS):
        target_crs = pp.CRS(target_crs)
    passed = True
    target_auth = auth_code(target_crs)
    transformed_file_auth = auth_code(pp.CRS(vrbag.wkt(fname=file_path)))
    if target_auth != transformed_file_auth:
        passed = False
        logger.warning("The expected authority name/code of the "
                       f"transformed vrbag is {target_auth}, but received {transformed_file_auth}"
                       )
    if not vrbag.is_vr(file_path):
        passed = False
        logger.warning(f"The transformed file ({file_path}) is not a valid Vrbag file.")
    return passed


def laz_pre_transformation_checks(file_path: str,
                                  source_crs: Union[pp.CRS, str]
                                  ) -> bool:
    """
    Run a number of sanity checks on the source file before transformation.
    Warns if a check fails.

    Parameters
    ----------
    file_path: str
        Path to the input file.
    source_crs: pyproj.crs.CRS or input used to create one
        The expected CRS object for the laz file.

    Returns
    ----------
    bool
        Returns True if all checks pass, otherwise False.
    """
    passed = True
    if ~isinstance(source_crs, pp.CRS):
        source_crs = pp.CRS(source_crs)
    source_auth = auth_code(source_crs)
    laz = LAZ(input_file=file_path)
    file_auth = auth_code(pp.CRS(laz.wkt()))
    if source_auth != file_auth:
        passed = False
        logger.warning("The authority name/code registered in the "
                       f"input file is {file_auth}, but received {source_auth}"
                       )
    return passed


def laz_post_transformation_checks(file_path: str,
                                   target_crs: Union[pp.CRS, str]
                                   ) -> bool:
    """
    Run a number of sanity checks on the transformed laz file.
    Warns if a check fails.

    Parameters
    ----------
    file_path: str
        Path to the input file.
    target_crs: pyproj.crs.CRS or input used to create one
        The expected CRS object for the transformed file.

    Returns
    ----------
    bool
        Returns True if all checks pass, otherwise False.
    """
    if ~isinstance(target_crs, pp.CRS):
        target_crs = pp.CRS(target_crs)
    passed = True
    target_auth = auth_code(target_crs)
    laz = LAZ(input_file=file_path)
    transformed_file_auth = auth_code(pp.CRS(laz.wkt()))
    if target_auth != transformed_file_auth:
        passed = False
        logger.warning("The expected authority name/code of the "
                       f"transformed LAZ is {target_auth}, but received {transformed_file_auth}"
                       )
    return passed


def npz_pre_transformation_checks(file_path: str,
                                  source_crs: Union[pp.CRS, str]
                                  ) -> bool:
    """
    Run a number of sanity checks on the source file before transformation.
    Warns if a check fails.

    Parameters
    ----------
    file_path: str
        Path to the input file.
    source_crs: pyproj.crs.CRS or input used to create one
        The expected CRS object for the npz file.

    Returns
    ----------
    bool
        Returns True if all checks pass, otherwise False.
    """
    passed = True
    if ~isinstance(source_crs, pp.CRS):
        source_crs = pp.CRS(source_crs)
    source_auth = auth_code(source_crs)
    nz = NPZ(input_file=file_path)
    file_auth = auth_code(pp.CRS(nz.wkt()))
    if source_auth != file_auth:
        passed = False
        logger.warning("The authority name/code registered in the "
                       f"input file is {file_auth}, but received {source_auth}"
                       )
    return passed


def npz_post_transformation_checks(file_path: str,
                                   target_crs: Union[pp.CRS, str]
                                   ) -> bool:
    """
    Run a number of sanity checks on the transformed npz file.
    Warns if a check fails.

    Parameters
    ----------
    file_path: str
        Path to the input file.
    target_crs: pyproj.crs.CRS or input used to create one
        The expected CRS object for the transformed file.

    Returns
    ----------
    bool
        Returns True if all checks pass, otherwise False.
    """
    if ~isinstance(target_crs, pp.CRS):
        target_crs = pp.CRS(target_crs)
    passed = True
    target_auth = auth_code(target_crs)
    nz = NPZ(input_file=file_path)
    transformed_file_auth = auth_code(pp.CRS(nz.wkt()))
    if target_auth != transformed_file_auth:
        passed = False
        logger.warning("The expected authority name/code of the "
                       f"transformed NPZ is {target_auth}, but received {transformed_file_auth}"
                       )
    return passed


def pdal_pre_transformation_checks(file_path: str,
                                   source_crs: Union[pp.CRS, str]
                                   ) -> bool:
    """
    Run a number of sanity checks on the source file before transformation.
    Warns if a check fails.

    Parameters
    ----------
    file_path: str
        Path to the input file.
    source_crs: pyproj.crs.CRS or input used to create one
        The expected CRS object for the PDAL-supported file.

    Returns
    ----------
    bool
        Returns True if all checks pass, otherwise False.
    """
    passed = True
    if ~isinstance(source_crs, pp.CRS):
        source_crs = pp.CRS(source_crs)
    source_auth = auth_code(source_crs)
    pdl = PDAL(input_file=file_path, output_file="")
    file_auth = auth_code(pp.CRS(pdl.wkt(fname=file_path)))
    if source_auth != file_auth:
        passed = False
        logger.warning("The authority name/code registered in the "
                       f"input file is {file_auth}, but received {source_auth}"
                       )
    return passed


def pdal_post_transformation_checks(file_path: str,
                                    target_crs: Union[pp.CRS, str]
                                    ) -> bool:
    """
    Run a number of sanity checks on the transformed PDAL-supported file.
    Warns if a check fails.

    Parameters
    ----------
    file_path: str
        Path to the input file.
    target_crs: pyproj.crs.CRS or input used to create one
        The expected CRS object for the transformed file.

    Returns
    ----------
    bool
        Returns True if all checks pass, otherwise False.
    """
    if ~isinstance(target_crs, pp.CRS):
        target_crs = pp.CRS(target_crs)
    passed = True
    target_auth = auth_code(target_crs)
    pdl = PDAL(input_file=file_path, output_file="")
    transformed_file_auth = auth_code(pp.CRS(pdl.wkt(fname=file_path)))
    if target_auth != transformed_file_auth:
        passed = False
        logger.warning("The expected authority name/code of the "
                       f"transformed PDAL-supported file is {target_auth},"
                       f" but received {transformed_file_auth}"
                       )
    return passed
