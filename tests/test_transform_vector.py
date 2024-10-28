import pathlib
from osgeo import gdal, ogr
import numpy as np
import pyproj as pp
from vyperdatum.transformer import Transformer


def vector_wkt(vector_file: str):
    ds = gdal.OpenEx(vector_file)
    driver = ogr.GetDriverByName(ds.GetDriver().ShortName)
    ds = None
    dataSource = driver.Open(vector_file, 0)
    layer = dataSource.GetLayer()
    wkt = layer.GetSpatialRef().ExportToWkt()
    driver, layer = None, None
    return wkt


def test_transform_vector_Hudson():
    input_file = r"C:\Users\mohammad.ashkezari\Documents\projects\vyperdatum\untrack\data\vector\Modeling_Tile_Scheme_20240320.gpkg"
    transformed_file = (str(pathlib.Path(input_file).with_stem("_transformed_"
                                                               + pathlib.Path(input_file).stem)))
    T = Transformer(crs_from=vector_wkt(input_file),
                    crs_to=f"{pp.CRS(vector_wkt(input_file)).to_2d().to_string()}+NOAA:5502"
                    )
    assert T.transform_vector(input_file=input_file, output_file=transformed_file), "Hudson river vector transformation failed"
