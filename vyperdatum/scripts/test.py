

# (proj94) PS C:\Users\mohammad.ashkezari\Documents\projects\vyperdatum\vyperdatum\scripts> projinfo -t EPSG:9989 -s EPSG:9990+NOAA:98 --spatial-test intersects --hide-ballpark
# Candidate operations found: 1
# -------------------------------------
# Operation No. 1:

# INVERSE(NOAA):20190, Inverse of 'ITRF2020 + MLLW (National_Water_Level_Datum/nwldatum_4.7.0_20240621) height to ITRF2020', 0.173205080756888 m, 20009 U.S. Maritime Limits / EEZ

# PROJ string:
# +proj=pipeline
#   +step +proj=axisswap +order=2,1
#   +step +proj=unitconvert +xy_in=deg +xy_out=rad
#   +step +proj=vgridshift
#         +grids=us_noaa_nos_MLLW-ITRF2020_2020.0_(nwldatum_4.7.0_20240621).tif
#         +multiplier=1
#   +step +proj=unitconvert +xy_in=rad +xy_out=deg
#   +step +proj=axisswap +order=2,1

# WKT2:2019 string:



from vyperdatum.utils.crs_utils import pipeline_string


crs_from = "EPSG:9989"
crs_to = "EPSG:9990+NOAA:98"


print(pipeline_string(crs_from, crs_to))