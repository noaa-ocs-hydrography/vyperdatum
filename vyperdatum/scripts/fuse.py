from vyperdatum.transformer import Transformer
from osgeo import gdal



crs_from = "EPSG:6599+EPSG:5703"
crs_to = "EPSG:6339+NOAA:101"



input_file = r"C:\Users\mohammad.ashkezari\Desktop\clipped.tif"
output_file = r"C:\Users\mohammad.ashkezari\Desktop\clipped_trans.tif"
tf = Transformer(crs_from=crs_from,
                crs_to=crs_to,
                )

tf.transform(input_file=input_file,
            output_file=output_file,
            pre_post_checks=True,
            vdatum_check=False
            )


# ---------------------------------------------------------------
# crs_from = "EPSG:6346+NOAA:94"
# crs_to = "EPSG:6346+NOAA:93"



# # input_file = r"C:\Users\mohammad.ashkezari\Desktop\Fuse_Test\point\bag\Original\F00857\F00857_MB_50cm_LWD_1of1.bag"
# input_file = r"C:\Users\mohammad.ashkezari\Desktop\Fuse_Test\point\bag\Original\H11915\H11915_VB_5m_LWD_1of1.bag"
# tf = Transformer(crs_from=crs_from,
#                 crs_to=crs_to,
#                 )
# output_file = input_file.replace("Original", "Manual")
# tf.transform(input_file=input_file,
#             output_file=output_file,
#             pre_post_checks=True,
#             vdatum_check=False
#             )


# ---------------------------------------------------------------
# crs_from = "EPSG:6347"
# crs_to = "EPSG:6347+NOAA:98"

# input_file = r"C:\Users\mohammad.ashkezari\Desktop\Fuse_Test\raster\Original\nc\NC1901-TB-C_BLK-03_US4NC1AC_ellipsoidal_dem.tif"
# tf = Transformer(crs_from=crs_from,
#                  crs_to=crs_to,
#                  )
# output_file = input_file.replace("Original", "Manual")
# tf.transform_raster(input_file=input_file,
#                     output_file=output_file,
#                     overview=False,
#                     pre_post_checks=True,
#                     vdatum_check=True
#                     )




# ---------------------------------------------------------------

# PROJ9.4 produces an empty file (nodatavalues), PROJ6 fails and generates no file
# the target UTM zone is sets 17 which looks incorrect 


# crs_from = "EPSG:6347"
# crs_to = "EPSG:6346+NOAA:98"

# input_file = r"C:\Users\mohammad.ashkezari\Desktop\Fuse_Test\raster\Original\nc\NC1901-TB-C_BLK-03_US4NC1AC_ellipsoidal_dem.tif"
# tf = Transformer(crs_from=crs_from,
#                  crs_to=crs_to,
#                  )
# output_file = input_file.replace("Original", "Manual")
# tf.transform_raster(input_file=input_file,
#                     output_file=output_file,
#                     overview=False,
#                     pre_post_checks=True,
#                     vdatum_check=True
#                     )