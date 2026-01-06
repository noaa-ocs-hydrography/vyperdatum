from importlib.metadata import version
import logging
import os
import pathlib
import json
import time
import logging.config
from osgeo import gdal
import pyproj as pp
from vyperdatum.db import DB
from vyperdatum.enums import PROJDB, DATUM_DOI
from vyperdatum.utils import assets_util


logger = logging.getLogger("root_logger")


def validate_vyper_grids():
    dir_path = PROJDB.DIR.value
    if dir_path is None:
        raise EnvironmentError("VYPER_GRIDS environment variable is not set. "
                               "Please set it to the directory where the proj database "
                               "and the grid file are located.")

    if not os.path.exists(dir_path):
        raise FileNotFoundError(f"The directory specified by VYPER_GRIDS environment variable does not exist: {dir_path}")
    assert os.environ["VYPER_GRIDS"] == PROJDB.DIR.value
    assert os.environ["PROJ_DATA"] == PROJDB.DIR.value, ("PROJ_DATA environment variable is not set to the correct directory. "
                                                         "It should be set to the same directory specified by VYPER_GRIDS env variable.\n"
                                                         f"Current PROJ_DATA env var: {os.environ['PROJ_DATA']}\n"
                                                         f"Current VYPER_GRIDS env var: {os.environ['VYPER_GRIDS']}")

    selected_grid_files = [
        "us_noaa_nos_underkeel_hydroid-NAD83(2011)_2010.0_(nwldatum_4.7.0_20240621).tif",
        "us_noaa_nos_MLLW-NAD83(2011)_2010.0_(nwldatum_4.7.0_20240621).tif",
        "us_noaa_nos_LWD-NAD83(2011)_2010.0_(nwldatum_4.7.0_20240621).tif",
        "us_noaa_nos_LWD_IGLD85-NAD83(2011)_2010.0_(nwldatum_4.7.0_20240621).tif",
        "us_noaa_nos_survey_hydroid-NAD83(2011)_2010.0_(usace_1.0.0_20250501).tif",
        "us_noaa_nos_CRD-NAD83(2011)_2010.0_(nwldatum_4.7.0_20240621).tif",
        "us_noaa_g2018u0.tif",
        "us_noaa_g2012bu0.tif"]
    missing_grids = []
    for grid in selected_grid_files:
        if not os.path.exists(os.path.join(dir_path, grid)):
            missing_grids.append(grid)
    if len(missing_grids) > 0:
        raise FileNotFoundError(f"The following required grid files are missing in the directory specified by VYPER_GRIDS: {dir_path}\n"
                                f"{', '.join(missing_grids)}\n")
    logger.info(f"Vyperdatum grids directory is set to: {dir_path}")
    return


__version__ = version("vyperdatum")
log_configuration_dict = json.load(
    open(
        pathlib.Path(
            pathlib.Path(__file__).parent, "logging_conf.json"
        )
    )
)
logging.config.dictConfig(log_configuration_dict)
logging.Formatter.converter = time.gmtime

os.environ.update(PROJ_NETWORK="ON")
gdal.UseExceptions()


os.environ["PROJ_DEBUG"] = "2"
os.environ["PROJ_ONLY_BEST_DEFAULT"] = "YES"
os.environ["PROJ_DATA"] = PROJDB.DIR.value  # derived from os.environ.get("VYPER_GRIDS", None)
validate_vyper_grids()
db = DB(db_dir=PROJDB.DIR.value)
assert "NOAA" in pp.database.get_authorities(), ("The authority 'NOAA' not found in proj.db. "
                                                 "Check if the latest database is used.")
