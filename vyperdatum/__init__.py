from osgeo import gdal

from vyperdatum.__version__ import __version__

version = gdal.VersionInfo()
major = int(version[0])
minor = int(version[1:3])
bug = int(version[3:5])
if not (major == 3 and minor >= 1):
    msg = f'The version of GDAL must be >= 3.1.\
            Version found: {major}.{minor}.{bug}'
    raise ValueError(msg)

