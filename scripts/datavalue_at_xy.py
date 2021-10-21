from osgeo import gdal


def get_value_at_xy(x: float, y: float, fname: str = r"C:\vdatum_all_20201203\vdatum\core\geoid12b\g2012bu0.gtx", add_threesixty: bool = True):
    driver = gdal.GetDriverByName('gtx')
    dataset = gdal.Open(fname)
    band = dataset.GetRasterBand(1)

    cols = dataset.RasterXSize
    rows = dataset.RasterYSize

    transform = dataset.GetGeoTransform()

    xOrigin = transform[0]
    yOrigin = transform[3]
    pixelWidth = transform[1]
    pixelHeight = -transform[5]

    data = band.ReadAsArray(0, 0, cols, rows)

    if add_threesixty:
        col = int(((x + 360) - xOrigin) / pixelWidth)
    else:
        col = int((x - xOrigin) / pixelWidth)
    row = int((yOrigin - y) / pixelHeight)

    return data[row][col]