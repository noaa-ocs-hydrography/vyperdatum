"""
WKT spec http://docs.opengeospatial.org/is/18-010r7/18-010r7.html

Need something to build wkt for our custom datum transformations

Just do the vertical since there aren't any custom horiz transforms that we do.  We can do a compound CRS with the known
horiz later.  How do we handle these custom vert transformations though?  We have no EPSG registered datum, so it won't be
something we can directly use in pyproj.  We have to build our own pipeline from a source custom vert to a source custom
vert.
"""

import os
from typing import Union
from pyproj.crs import CRS, CompoundCRS, VerticalCRS as pyproj_VerticalCRS
import pyproj.datadir
from vyperdatum.pipeline import get_regional_pipeline, datum_definition
from vyperdatum.__version__ import __version__


NAD83_2D = 6318
NAD83_3D = 6319
ITRF2008_2D = 8999
ITRF2008_3D = 7911
ITRF2014_2D = 9000
ITRF2014_3D = 7912

frame_lookup = {CRS.from_epsg(NAD83_2D).name: 'NAD83',
                CRS.from_epsg(NAD83_3D).name: 'NAD83',
                CRS.from_epsg(ITRF2008_2D).name: 'ITRF2008',
                CRS.from_epsg(ITRF2008_3D).name: 'ITRF2008',
                CRS.from_epsg(ITRF2014_2D).name: 'ITRF2014',
                CRS.from_epsg(ITRF2014_3D).name: 'ITRF2014'}

geoid_frame_lookup = {r'core\geoid12b\g2012bu0.gtx': CRS.from_epsg(NAD83_2D).name,
                      r'core\geoid12b\g2012bp0.gtx': CRS.from_epsg(NAD83_2D).name,
                      r'core\xgeoid16b\ak.gtx': CRS.from_epsg(ITRF2008_2D).name,
                      r'core\xgeoid16b\conus.gtx': CRS.from_epsg(ITRF2008_2D).name,
                      r'core\xgeoid16b\hi.gtx': CRS.from_epsg(ITRF2008_2D).name,
                      r'core\xgeoid16b\prvi.gtx': CRS.from_epsg(ITRF2008_2D).name,
                      r'core\xgeoid17b\AK_17B.gtx': CRS.from_epsg(ITRF2008_2D).name,
                      r'core\xgeoid17b\CONUS_17B.gtx': CRS.from_epsg(ITRF2008_2D).name,
                      r'core\xgeoid17b\PRVI_17B.gtx': CRS.from_epsg(ITRF2008_2D).name,
                      r'core\xgeoid18b\AK_18B.gtx': CRS.from_epsg(ITRF2008_2D).name,
                      r'core\xgeoid18b\CONUS_18B.gtx': CRS.from_epsg(ITRF2008_2D).name,
                      r'core\xgeoid18b\PRVI_18B.gtx': CRS.from_epsg(ITRF2008_2D).name,
                      r'core\xgeoid18b\GU_18B.gtx': CRS.from_epsg(ITRF2008_2D).name,
                      r'core\xgeoid19b\CONUSPAC.pc.gtx': CRS.from_epsg(ITRF2008_2D).name,
                      r'core\xgeoid20b\conuspac.gtx': CRS.from_epsg(ITRF2014_2D).name,
                      r'core\xgeoid20b\as.gtx': CRS.from_epsg(ITRF2014_2D).name,
                      r'core\xgeoid20b\gu.gtx': CRS.from_epsg(ITRF2014_2D).name}

geoid_possibilities = ['geoid12b', 'xgeoid16b', 'xgeoid17b', 'xgeoid18b', 'xgeoid19b', 'xgeoid20b']

frame_to_3dcrs = {CRS.from_epsg(NAD83_2D).name: CRS.from_epsg(NAD83_3D),
                  CRS.from_epsg(ITRF2008_2D).name: CRS.from_epsg(ITRF2008_3D),
                  CRS.from_epsg(ITRF2014_2D).name: CRS.from_epsg(ITRF2014_3D)}

valid_grid_extensions = ['.tiff', '.tif', '.gtx']

