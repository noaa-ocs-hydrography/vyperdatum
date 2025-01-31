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

if assets_util.datums_missing(datums_dir=PROJDB.DIR.value):
    logger.info("Datum files not found in the assets directory.")
    assets_util.download_datums(doi=DATUM_DOI.REGIONAL.value)

os.environ["PROJ_DEBUG"] = "2"
os.environ["PROJ_ONLY_BEST_DEFAULT"] = "YES"
os.environ["PROJ_DATA"] = PROJDB.DIR.value
db = DB(db_dir=PROJDB.DIR.value)
assert "NOAA" in pp.database.get_authorities(), ("The authority 'NOAA' not found in proj.db. "
                                                 "Check if the latest database is used.")
