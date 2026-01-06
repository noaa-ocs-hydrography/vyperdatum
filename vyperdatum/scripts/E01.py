from vyperdatum.transformer import Transformer
from vyperdatum.utils.raster_utils import raster_metadata

# input_file = r"C:\Users\mohammad.ashkezari\Desktop\E01001_MB_VR_MLLW_2of5.bag"
# output_file = r"C:\Users\mohammad.ashkezari\Desktop\E01001_MB_VR_NAVD88_2of5.bag"

# crs_from = "EPSG:6335+NOAA:98"
# crs_to = "EPSG:6335+EPSG:5703"
# tf = Transformer(crs_from=crs_from, crs_to=crs_to )                
# tf.transform_raster(input_file=input_file,
#                     output_file=output_file,
#                     overview=False,
#                     pre_post_checks=True,
#                     vdatum_check=False
#                     )




# https://vlab.noaa.gov/redmine/issues/148720
# ------------------------------------------------------------------------
# input_file = r"C:\Users\mohammad.ashkezari\Desktop\wgs\E01096_MB_2m_MLLW_1of7.bag"
# output_file = r"C:\Users\mohammad.ashkezari\Desktop\wgs\E01096_MB_2m_MLLW_1of7.bag"

# meta = raster_metadata(input_file)
# print(meta["h_authcode"])
# print(meta["v_authcode"])
# crs_from = "EPSG:6335+NOAA:98"
# crs_to = "EPSG:6335+EPSG:5703"
# tf = Transformer(crs_from=crs_from, crs_to=crs_to )                
# tf.transform_raster(input_file=input_file,
#                     output_file=output_file,
#                     overview=False,
#                     pre_post_checks=True,
#                     vdatum_check=False
#                     )


