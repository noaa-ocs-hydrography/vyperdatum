import os
import vyperdatum
from enum import Enum
import pyproj as pp


class RootEnum(Enum):
    ...


class ASSETS(Enum):
    DIR = os.path.join(os.path.split(vyperdatum.__file__)[0], "assets")


class PROJDB(RootEnum):
    """
    Proj db attributes.

    Attributes
    ----------
    FILE_NAME
    """
    # DIR = os.path.join(ASSETS.DIR.value, "datums")
    DIR = pp.datadir.get_data_dir()
    FILE_NAME = "proj.db"

    VIEW_CRS = "crs_view"
    TABLE_VERTICAL_CRS = "vertical_crs"
    TABLE_GRID_TRANS = "grid_transformation"
    TABLE_OTHER_TRANS = "other_transformation"
    TABLE_CONCAT_OPS = "concatenated_operation"


class VDATUM(RootEnum):
    DIR = os.path.join(ASSETS.DIR.value, "vdatum")
    # from https://vdatum.noaa.gov/docs/services.html  (accessed on July 16, 2024)
    H_FRAMES = ["NAD27", "NAD83_1986", "NAD83_2011", "NAD83_NSRS2007", "NAD83_MARP00",
                "NAD83_PACP00", "WGS84_G1674", "ITRF2014", "IGS14", "ITRF2008", "IGS08",
                "ITRF2005", "IGS2005", "WGS84_G1150", "ITRF2000", "IGS00", "IGb00",
                "ITRF96", "WGS84_G873", "ITRF94", "ITRF93", "ITRF92", "SIOMIT92",
                "WGS84_G730", "ITRF91", "ITRF90", "ITRF89", "ITRF88", "WGS84_TRANSIT",
                "WGS84_G1762", "WGS84_G2139"]
    V_FRAMES = ["NAVD88", "NGVD29", "ASVD02", "W0_USGG2012", "GUVD04", "NMVD03", "PRVD02",
                "VIVD09", "CRD", "EGM2008", "EGM1996", "EGM1984", "XGEOID16B", "XGEOID17B",
                "XGEOID18B", "XGEOID19B", "XGEOID20B", "IGLD85", "LWD_IGLD85", "OHWM_IGLD85",
                "CRD", "LMSL", "MLLW", "MLW", "MTL", "DTL", "MHW", "MHHW", "LWD", "NAD27",
                "NAD83_1986", "NAD83_2011", "NAD83_NSRS2007", "NAD83_MARP00", "NAD83_PACP00",
                "WGS84_G1674", "ITRF2014", "IGS14", "ITRF2008", "IGS08", "ITRF2005", "IGS2005",
                "WGS84_G1150", "ITRF2000", "IGS00", "IGb00", "ITRF96", "WGS84_G873", "ITRF94",
                "ITRF93", "ITRF92", "SIOMIT92", "WGS84_G730", "ITRF91", "ITRF90", "ITRF89",
                "ITRF88", "WGS84_TRANSIT", "WGS84_G1762", "WGS84_G2139"]


class VRBAG(RootEnum):
    NDV_REF = 1000000
    NO_REF_INDEX = 0xffffffff

class DATUM_DOI(RootEnum):
    REGIONAL = {"url": "https://zenodo.org/records/14201516/files/regional.zip?download=1",
                "dir_name": "regional"
                }
