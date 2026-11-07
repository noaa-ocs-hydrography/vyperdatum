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



    T = Transformer(crs_from="EPSG:6318",
                    crs_to="EPSG:6318+NOAA:98",
                    )                                                           
    # T = Transformer(crs_from=vector_wkt(input_file),
    #                 crs_to=f"{pp.CRS(vector_wkt(input_file)).to_2d().to_string()}+NOAA:98"
    #                 )
    assert T.transform_vector(input_file=input_file, output_file=transformed_file), "Hudson river vector transformation failed"


def test_transform_vector_missing_file_returns_false(tmp_path, caplog):
    """
    A missing input file must return False and log the error, rather than
    raising UnboundLocalError from the cleanup.
    """
    tf = Transformer(crs_from="EPSG:6318", crs_to="EPSG:6346")
    success = tf.transform_vector(input_file=str(tmp_path / "missing.gpkg"),
                                  output_file=str(tmp_path / "out.gpkg"))
    assert success is False
    assert "Exception in `transform_vector()`" in caplog.text
