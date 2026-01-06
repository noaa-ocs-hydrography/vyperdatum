import pytest
import os
import pyproj as pp
from vyperdatum.transformer import Transformer
from vyperdatum.drivers.npz import NPZ
from vyperdatum.drivers.laz import LAZ
from vyperdatum.drivers.gparq import GeoParquet



# def test_6349_to_6319():
#     """
#     Verify the a point on NAD83_2011_NAVD88 (EPSG:6349) is transformed
#     correctly to NAD83_2011_3D (EPSG:6319).

#     If network is off then a noop is used for the transform and NAVD88 to
#     NAD83_2011_3D returns 0.0 leading to the test failure.
#     """

#     coords_lat_lon = (39, -76.5, 0)
#     x, y, z = Transformer(crs_from=6349, crs_to=6319).transform_points(*coords_lat_lon)
#     assert pytest.approx(x, abs=.01) == coords_lat_lon[0], "x coordinate should remain unchanged."
#     assert pytest.approx(y, abs=.01) == coords_lat_lon[1], "y coordinate should remain unchanged."
#     assert pytest.approx(z, abs=.01) == -33.29, "incorrect z coordinate transformation."


# @pytest.mark.parametrize("fname", [
#     r"C:\Users\mohammad.ashkezari\Documents\projects\vyperdatum\untrack\data\point\npz\2018_NCMP_MA_19TCF2495_BareEarth_1mGrid_transformed.bruty.bruty.npz",
#     r"C:\Users\mohammad.ashkezari\Documents\projects\vyperdatum\untrack\data\point\npz\W00405_MB_1m_MLLW_1of4_transformed.bruty.npz"
# ])
# def test_npz(fname):
#     npz = NPZ(fname)
#     x, y, z, u = npz.xyzu()
#     wkt = npz.wkt()
#     mmx, mmy, mmz, mmu = npz.minmax()
#     assert x.shape == y.shape == z.shape == u.shape, f"inconsistent data array dimensions in npz file: {fname}"  # noqa: E501
#     assert mmx.shape == mmy.shape == mmz.shape == mmu.shape, f"inconsistent minmax array dimensions in npz file: {fname}"  # noqa: E501
#     assert isinstance(wkt, str), f"unexpected wkt type in npz file: {fname}"


def test_transform_gparq():
    fname = r"C:\Users\mohammad.ashkezari\Documents\projects\vyperdatum\untrack\data\point\geoparquet\South_Locust_Point_&_Masonville_&_Ferry_Bar_&_Fairfield_2023_Elevation_MLLW_3ftx3ft.parquet"
    d, f = os.path.split(fname)
    output_file = os.path.join(d, f"transformed_{f}")
    crs_from = "EPSG:6347+NOAA:98"
    crs_to = "EPSG:6347+EPSG:5703"
    tf = Transformer(crs_from=crs_from, crs_to=crs_to)
    tf.transform(input_file=fname, output_file=output_file)
    gp = GeoParquet(output_file)
    auth_code = "+".join([":".join(pp.CRS(s).to_authority()) for s in pp.CRS(gp.wkt()).sub_crs_list])
    assert auth_code == crs_to, f"Incorrect WKT in the transformed geoparquet file: {output_file}"


# def test_transform_npz():
#     fname = r"C:\Users\mohammad.ashkezari\Documents\projects\vyperdatum\untrack\data\point\npz\W00405_MB_1m_MLLW_1of4_transformed.bruty.npz"
#     d, f = os.path.split(fname)
#     output_file = os.path.join(d, f"transformed_{f}")
#     crs_from = "EPSG:26919"
#     crs_to = "EPSG:26919+NOAA:5434"
#     steps = ["EPSG:26919", "EPSG:6319", "EPSG:6318+NOAA:5434", "EPSG:26919+NOAA:5434"]
#     tf = Transformer(crs_from=crs_from, crs_to=crs_to, steps=steps)
#     tf.transform(input_file=fname, output_file=output_file)
#     npz = NPZ(output_file)
#     auth_code = "+".join([":".join(pp.CRS(s).to_authority()) for s in pp.CRS(npz.wkt()).sub_crs_list])
#     assert auth_code == crs_to, f"Incorrect WKT in the transformed npz file: {output_file}"


# def test_transform_laz():
#     fname = r"C:\Users\mohammad.ashkezari\Documents\projects\vyperdatum\untrack\data\point\laz\ma2021_cent_east_Job1082403.laz"
#     d, f = os.path.split(fname)
#     output_file = os.path.join(d, f"transformed_{f}")
#     crs_from = "EPSG:6348+EPSG:5703"
#     crs_to = "EPSG:6348+NOAA:5320"
#     steps = ["EPSG:6348+EPSG:5703", "EPSG:6318+EPSG:5703", "EPSG:6318+NOAA:5320", "EPSG:6348+NOAA:5320"]
#     tf = Transformer(crs_from=crs_from, crs_to=crs_to, steps=steps)
#     tf.transform(input_file=fname, output_file=output_file)
#     lz = LAZ(output_file)
#     auth_code = "+".join([":".join(pp.CRS(s).to_authority()) for s in pp.CRS(lz.wkt()).sub_crs_list])
#     assert auth_code == crs_to, f"Incorrect WKT in the transformed laz file: {output_file}"


# def test_transform_vrbag():
#     fname = r"C:\Users\mohammad.ashkezari\Documents\projects\vyperdatum\untrack\data\point\vrbag\W00656_MB_VR_MLLW_5of5.bag"
#     d, f = os.path.split(fname)
#     output_file = os.path.join(d, f"transformed_{f}")
#     crs_from = "EPSG:32617+EPSG:5866"
#     crs_to = "EPSG:26917+EPSG:5866"
#     steps = ["EPSG:32617+EPSG:5866", "EPSG:9755", "EPSG:6318", "EPSG:26917+EPSG:5866"]
#     tf = Transformer(crs_from=crs_from, crs_to=crs_to, steps=steps)
#     tf.transform(input_file=fname, output_file=output_file)

#     auth_code = "+".join([":".join(pp.CRS(s).to_authority()) for s in pp.CRS(wkt).sub_crs_list])
#     assert auth_code == crs_to, f"Incorrect WKT in the transformed vrbag file: {output_file}"