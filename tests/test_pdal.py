import pytest
import pyproj as pp
from vyperdatum.drivers.pdal_based import PDAL
from vyperdatum.transformer import Transformer
from vyperdatum.utils.crs_utils import auth_code


def test_fetch_entwine():
    pdl = PDAL(input_file="https://na-c.entwine.io/dublin/ept.json",
               output_file=r"C:\Users\mohammad.ashkezari\Documents\projects\vyperdatum\untrack\data\pdal\entwine.las")
    succeed = pdl.fetch_entwine(bounds=None, resolution=20, output_format="writers.las")
    assert succeed, "fetch_entwine failed!"
    return


def test_transform():
    fname = r"C:\Users\mohammad.ashkezari\Documents\projects\vyperdatum\untrack\data\point\laz\ma2021_cent_east_Job1082403.laz"
    oname = r"C:\Users\mohammad.ashkezari\Documents\projects\vyperdatum\untrack\data\point\laz\_t_ma2021_cent_east_Job1082403.laz"
    p = PDAL(input_file=fname, output_file=oname)
    crs_from = "EPSG:6348+EPSG:5703"
    crs_to = "EPSG:6348+NOAA:5320"
    steps = ["EPSG:6348+EPSG:5703", "EPSG:6318+EPSG:5703", "EPSG:6318+NOAA:5320", "EPSG:6348+NOAA:5320"]
    tf = Transformer(crs_from=crs_from, crs_to=crs_to, steps=steps)
    p.transform(tf)
    wkt = p.wkt(fname=oname)
    assert auth_code(pp.CRS(wkt)) == "EPSG:6348+NOAA:5320", ("Transformed CRS"
                                                             f" code is {auth_code(pp.CRS(wkt))}"
                                                             " but expected 'EPSG:6348+NOAA:5320'")
    return
