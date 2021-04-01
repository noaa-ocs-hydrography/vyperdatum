# run in pydro38_test env

import os
from pyproj import CRS, Transformer


vdatum_dir = r'C:\Pydro_conda36\NOAA\supplementals\VDatum'
vdatum_area = 'MENHMAgome13_8301'

path = os.path.join(vdatum_dir, vdatum_area)
tss_gtx = os.path.join(path, 'tss.gtx')
mhw_gtx = os.path.join(path, 'mhw.gtx')
mllw_gtx = os.path.join(path, 'mllw.gtx')

xx = [-68.65085, -67.80085]
yy = [43.01885, 42.16885]
zz = [100, 100]

#source_crs = CRS.from_proj4('+init=epsg:4326')
source_crs = CRS.from_proj4('+init=epsg:4269')
target_crs = CRS.from_proj4(r'+init=epsg:4269 +geoidgrids=%s' %mllw_gtx)
transformer = Transformer.from_crs(source_crs, target_crs, always_xy=True)
result = transformer.transform(xx=xx, yy=yy, zz=zz)

print('Transform result:')
print(result)
#print(source_crs.to_wkt(pretty=True))
#print(target_crs.to_wkt(pretty=True))
#print(transformer)