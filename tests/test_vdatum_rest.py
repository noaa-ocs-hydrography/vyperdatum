
# import pytest
# from vyperdatum.utils.raster_utils import raster_metadata
# from vyperdatum.utils.vdatum_rest_utils import (api_crs_aliases,
#                                                 vdatum_transform_point,
#                                                 vdatum_cross_validate_raster
#                                                 )


# @pytest.mark.parametrize("input_file, vdatum_h_crs, vdatum_v_crs", [
#     (r"C:\Users\mohammad.ashkezari\Documents\projects\vyperdatum\untrack\data\raster\NVD\VA_input.tif", "ITRF2014", "LMSL"),
#     (r"C:\Users\mohammad.ashkezari\Documents\projects\vyperdatum\untrack\data\raster\BlueTopo\BC25L26L\Modeling_BC25L26L_20230919.tiff", "NAD83_2011", "MLLW"),
#     (r"C:\Users\mohammad.ashkezari\Documents\projects\vyperdatum\untrack\data\raster\BlueTopo\BC25L26L\_03_6318_5703_Modeling_BC25L26L_20230919.tiff", "NAD83_2011", "NAVD88"),
#     ])
# def test_api_crs_aliases(input_file: str, vdatum_h_crs: str, vdatum_v_crs: str):
#     meta = raster_metadata(input_file, verbose=False)
#     h_crs, v_crs = api_crs_aliases(meta["wkt"])
#     assert h_crs == vdatum_h_crs, (f"Horizontal CRS name ({h_crs}) didn't match"
#                                    f" Vdatum's alias ({vdatum_h_crs}) for {input_file}.")
#     assert v_crs == vdatum_v_crs, (f"Vertical CRS name ({v_crs}) didn't match"
#                                    f" Vdatum's alias ({vdatum_v_crs}) for {input_file}.")


# def test_vdatum_transform_point():
#     xx, yy, zz = -70.7, 43, 0
#     tx, ty, tz = -70.7, 43, -1.547
#     points, _ = vdatum_transform_point(s_x=xx, s_y=yy, s_z=zz, region="contiguous",
#                                        s_h_frame="NAD83_2011", s_v_frame="MLLW",
#                                        s_h_zone=None,
#                                        t_h_frame="NAD83_2011", t_v_frame="NAVD88",
#                                        t_h_zone=None
#                                        )
#     assert pytest.approx(points[0], abs=.01) == tx, "x coordinate should remain unchanged."
#     assert pytest.approx(points[1], abs=.01) == ty, "y coordinate should remain unchanged."
#     assert pytest.approx(points[2], abs=.2) == tz, (f"Vdatum transferred value ({points[2]})"
#                                                     f" doesn't match the expected value ({tz})")


# @pytest.mark.parametrize("s_file, t_file", [
#     # (r"C:\Users\mohammad.ashkezari\Documents\projects\vyperdatum\untrack\data\raster\BlueTopo\BC25L26L\Modeling_BC25L26L_20230919.tiff",
#     #  r"C:\Users\mohammad.ashkezari\Documents\projects\vyperdatum\untrack\data\raster\BlueTopo\BC25L26L\_03_6318_5703_Modeling_BC25L26L_20230919.tiff"
#     #  ),
#     (r"C:\Users\mohammad.ashkezari\Documents\projects\vyperdatum\untrack\data\raster\PBB\Original\FL1703-TB-N\ellipsoid\FL1703-TB-N_US4FL2BJ_ellipsoidal_dem.tif",
#      r"C:\Users\mohammad.ashkezari\Documents\projects\vyperdatum\untrack\data\raster\PBB\Manual\FL1703-TB-N\ellipsoid\FL1703-TB-N_US4FL2BJ_ellipsoidal_dem.tif"
#      )
#     ])
# def test_vdatum_cross_validate_raster(s_file: str, t_file: str):
#     passed, cross_df = vdatum_cross_validate_raster(s_file=s_file,
#                                                     t_file=t_file,
#                                                     n_sample=20,
#                                                     sampling_band=1,
#                                                     region=None,
#                                                     pivot_h_crs="EPSG:6318",
#                                                     s_h_frame=None,
#                                                     s_v_frame=None,
#                                                     s_h_zone=None,
#                                                     t_h_frame=None,
#                                                     t_v_frame=None,
#                                                     t_h_zone=None
#                                                     )
#     assert passed, f"Transformed raster inconsistent with Vdatum ({t_file})."
