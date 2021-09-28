from pytest import approx

from vyperdatum.raster import *
from vyperdatum.vdatum_validation import vdatum_answers


test_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'tiff', 'test.tiff')
gvc = VyperCore()
data_folder = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data')
vdatum_answer = vdatum_answers[gvc.vdatum.vdatum_version]


def test_core_setup():
    # these tests assume you have the vdatum path setup in VyperCore
    # first time, you need to run it with the path to the vdatum folder, vc = VyperCore('path\to\vdatum')
    vc = VyperCore()
    assert os.path.exists(vc.vdatum.vdatum_path)
    assert vc.vdatum.grid_files
    assert vc.vdatum.polygon_files


def test_find_testdata():
    assert os.path.exists(test_file)


def test_raster_initialize():
    # test the auto initialize vs manually initializing
    vr_one = VyperRaster()
    vr_one.initialize(test_file)
    vr_two = VyperRaster(test_file)

    assert vr_one.input_file == test_file
    assert vr_one.geotransform == (339262.0, 4.0, 0.0, 4693254.0, 0.0, -4.0)

    # actual raster extents
    assert vr_one.min_x == 339262.0
    assert vr_one.min_y == 4684786.0
    assert vr_one.max_x == 345630.0
    assert vr_one.max_y == 4693254.0

    # those same extents, but in NAD83(2011) geographic coordinates, epsg=6319
    assert vr_one.geographic_min_x == approx(-70.94997811389081, abs=0.0000001)
    assert vr_one.geographic_min_y == approx(42.29873069934964, abs=0.0000001)
    assert vr_one.geographic_max_x == approx(-70.87503006957049, abs=0.0000001)
    assert vr_one.geographic_max_y == approx(42.37624115875231, abs=0.0000001)

    assert vr_one.input_file == vr_two.input_file
    assert vr_one.geotransform == vr_two.geotransform

    assert vr_one.min_x == vr_two.min_x
    assert vr_one.min_y == vr_two.min_y
    assert vr_one.max_x == vr_two.max_x
    assert vr_one.max_y == vr_two.max_y

    assert vr_one.geographic_min_x == vr_two.geographic_min_x
    assert vr_one.geographic_min_y == vr_two.geographic_min_y
    assert vr_one.geographic_max_x == vr_two.geographic_max_x
    assert vr_one.geographic_max_y == vr_two.geographic_max_y


def test_raster_data():
    # test initializing and checking the data pulled from the raster, use these four cells in all tests
    vr = VyperRaster()
    vr.initialize(test_file)
    assert vr.layernames == ['Elevation', 'Uncertainty', 'Contributor']

    elev_idx = vr._get_elevation_layer_index()
    unc_idx = vr._get_uncertainty_layer_index()
    cont_idx = vr._get_contributor_layer_index()

    assert elev_idx == 0
    assert unc_idx == 1
    assert cont_idx == 2

    elev_layer = vr.layers[elev_idx]
    unc_layer = vr.layers[unc_idx]
    cont_layer = vr.layers[cont_idx]

    test_x_coord = vr.min_x + 100 * vr.resolution_x
    test_y_coord = vr.min_y + 100 * vr.resolution_y
    assert test_x_coord == 339662.0
    assert test_y_coord == 4685186.0

    assert np.isnan(vr.layers[0][0][0])
    assert elev_layer[100][100] == approx(vdatum_answer['rastertest']['elev'][0], abs=0.001)
    assert elev_layer[1050][100] == approx(vdatum_answer['rastertest']['elev'][1], abs=0.001)
    assert elev_layer[400][400] == approx(vdatum_answer['rastertest']['elev'][2], abs=0.001)

    assert np.isnan(vr.layers[1][0][0])
    assert unc_layer[100][100] == approx(vdatum_answer['rastertest']['unc'][0], abs=0.001)
    assert unc_layer[1050][100] == approx(vdatum_answer['rastertest']['unc'][1], abs=0.001)
    assert unc_layer[400][400] == approx(vdatum_answer['rastertest']['unc'][2], abs=0.001)

    assert np.isnan(vr.layers[2][0][0])
    assert cont_layer[100][100] == vdatum_answer['rastertest']['cont'][0]
    assert cont_layer[1050][100] == vdatum_answer['rastertest']['cont'][1]
    assert cont_layer[400][400] == vdatum_answer['rastertest']['cont'][2]
    

def test_raster_datum_sep():
    vr = VyperRaster(test_file)
    vr.set_input_datum('ellipse')
    vr.set_output_datum('mllw')
    vr.get_datum_sep()

    # assert vr.raster_vdatum_sep[100][100] == approx(vdatum_answer['rastertest']['mllw'][0] - vdatum_answer['rastertest']['elev'][0], abs=0.001)
    # assert vr.raster_vdatum_sep[1050][100] == approx(vdatum_answer['rastertest']['mllw'][1] - vdatum_answer['rastertest']['elev'][1], abs=0.001)
    # assert vr.raster_vdatum_sep[400][400] == approx(vdatum_answer['rastertest']['mllw'][2] - vdatum_answer['rastertest']['elev'][2], abs=0.001)

    assert vr.raster_vdatum_sep[100][100] == approx(29.163, abs=0.001)
    assert vr.raster_vdatum_sep[1050][100] == approx(29.291, abs=0.001)
    assert vr.raster_vdatum_sep[400][400] == approx(29.148, abs=0.001)

    assert vr.raster_vdatum_uncertainty[100][100] == approx(0.196, abs=0.001)
    assert vr.raster_vdatum_uncertainty[1050][100] == approx(0.196, abs=0.001)
    assert vr.raster_vdatum_uncertainty[400][400] == approx(0.196, abs=0.001)

    assert vr.raster_vdatum_region_index[100][100] == 0
    assert vr.raster_vdatum_region_index[1050][100] == 0
    assert vr.raster_vdatum_region_index[400][400] == 0

    # region index is just an index for the regions attribute
    assert vr.regions[0].find('MENHMAgome') != -1
    # see if the data is fully covered by the vdatum regions
    assert vr.is_covered


def test_raster_apply_sep():
    vr = VyperRaster(test_file)
    vr.set_input_datum('mllw')
    vr.set_output_datum('ellipse')
    vr.get_datum_sep()
    layers, layernames, layernodata = vr.apply_sep(allow_points_outside_coverage=True)

    elev_layer = layers[0]
    unc_layer = layers[1]
    cont_layer = layers[2]

    # restart validation work here
    assert np.isnan(elev_layer[0][0])
    assert elev_layer[100][100] == approx(-39.773, abs=0.001)
    assert elev_layer[1050][100] == approx(-50.591, abs=0.001)
    assert elev_layer[400][400] == approx(-39.708, abs=0.001)

    assert np.isnan(unc_layer[0][0])
    assert unc_layer[100][100] == approx(1.21, abs=0.001)
    assert unc_layer[1050][100] == approx(1.429, abs=0.001)
    assert unc_layer[400][400] == approx(12.316, abs=0.001)

    assert np.isnan(cont_layer[0][0])
    assert cont_layer[100][100] == 124.0
    assert cont_layer[1050][100] == 214.0
    assert cont_layer[400][400] == 396.0


def test_raster_transform_raster():
    vr = VyperRaster(test_file)
    layers, layernames, layernodata = vr.transform_raster('ellipse', 'mllw', allow_points_outside_coverage=True)

    elev_layer = layers[0]
    unc_layer = layers[1]
    cont_layer = layers[2]

    assert np.isnan(elev_layer[0][0])
    assert elev_layer[100][100] == approx(-39.773, abs=0.001)
    assert elev_layer[1050][100] == approx(-50.591, abs=0.001)
    assert elev_layer[400][400] == approx(-39.708, abs=0.001)

    assert np.isnan(unc_layer[0][0])
    assert unc_layer[100][100] == approx(1.21, abs=0.001)
    assert unc_layer[1050][100] == approx(1.429, abs=0.001)
    assert unc_layer[400][400] == approx(12.316, abs=0.001)

    assert np.isnan(cont_layer[0][0])
    assert cont_layer[100][100] == 124.0
    assert cont_layer[1050][100] == 214.0
    assert cont_layer[400][400] == 396.0


def test_raster_height_vs_sounding_input():
    vr = VyperRaster(test_file)
    layers, layernames, layernodata = vr.transform_raster('ellipse', 'mllw', allow_points_outside_coverage=True)
    test_x_coord = vr.min_x + 100 * vr.resolution_x
    test_y_coord = vr.min_y + 100 * vr.resolution_y
    assert test_x_coord == 339662.0
    assert test_y_coord == 4685186.0
    assert vr.layers[vr._get_elevation_layer_index()][100][100] == approx(-10.61, abs=0.001)
    assert vr.raster_vdatum_sep[100][100] == approx(-29.163, abs=0.001)

    # final elevation = -10.61 + -29.163 = -39.773
    elev_layer = layers[0]
    assert elev_layer[100][100] == approx(-39.773, abs=0.001)

    vr = VyperRaster(test_file)
    layers, layernames, layernodata = vr.transform_raster('ellipse', 5866, allow_points_outside_coverage=True)

    # final sounding = -1 * (-10.61 + 29.391) = -18.553
    elev_layer = layers[0]
    assert elev_layer[100][100] == approx(-18.553, abs=0.001)
    
    
def test_raster_height_vs_sounding_output():
    vr = VyperRaster(test_file)
    layers, layernames, layernodata = vr.transform_raster('mllw','ellipse', allow_points_outside_coverage=True)
    test_x_coord = vr.min_x + 100 * vr.resolution_x
    test_y_coord = vr.min_y + 100 * vr.resolution_y
    assert test_x_coord == 339662.0
    assert test_y_coord == 4685186.0
    assert vr.layers[vr._get_elevation_layer_index()][100][100] == approx(-10.61, abs=0.001)
    assert vr.raster_vdatum_sep[100][100] == approx(29.163, abs=0.001)

    # final elevation = -10.61 + 29.163 = 18.553
    elev_layer = layers[0]
    assert elev_layer[100][100] == approx(18.553, abs=0.001)

    vr = VyperRaster(test_file)
    layers, layernames, layernodata = vr.transform_raster(5866, 'ellipse', allow_points_outside_coverage=True)

    # final sounding = -1 * (-10.61 + 29.391) = -18.553
    elev_layer = layers[0]
    assert elev_layer[100][100] == approx(-18.553, abs=0.001)


def test_raster_forced_input_vertical_datum():
    # test
    vr = VyperRaster(test_file)
    # optional step saying the raster is at horiz=26919, vert=geoid12b
    # equivalent to -> vr.set_input_datum(26919, 'geoid12b')
    layers, layernames, layernodata = vr.transform_raster('mllw', 'geoid', allow_points_outside_coverage=True)

    test_x_coord = vr.min_x + 100 * vr.resolution_x
    test_y_coord = vr.min_y + 100 * vr.resolution_y
    assert test_x_coord == 339662.0
    assert test_y_coord == 4685186.0
    assert vr.layers[vr._get_elevation_layer_index()][100][100] == approx(-10.61, abs=0.001)
    assert vr.raster_vdatum_sep[100][100] == approx(1.613, abs=0.001)  # geoid12b to mllw

    # final sounding at mllw = -10.61 + 1.613 = -8.996
    elev_layer = layers[0]
    assert elev_layer[100][100] == approx(-8.996, abs=0.001)


def test_raster_write_to_geotiff():
    logfile = os.path.join(os.path.split(test_file)[0], 'test_log.txt')
    vr = VyperRaster(test_file, logfile=logfile)
    output_filename = os.path.join(os.path.split(test_file)[0], 'vyperdatum_file.tif')
    layers, layernames, layernodata = vr.transform_raster('geoid', 'mllw', allow_points_outside_coverage=True, output_filename=output_filename)
    assert os.path.exists(output_filename)

    ofile = gdal.Open(output_filename)
    newlayers = [ofile.GetRasterBand(i + 1).ReadAsArray() for i in range(ofile.RasterCount)]
    newnodatavalue = [ofile.GetRasterBand(i + 1).GetNoDataValue() for i in range(ofile.RasterCount)]
    newlayernames = [ofile.GetRasterBand(i + 1).GetDescription() for i in range(ofile.RasterCount)]
    ofile = None

    assert layers[0] == approx(newlayers[0], abs=0.001, nan_ok=True)
    assert layers[1] == approx(newlayers[1], abs=0.001, nan_ok=True)
    assert layers[2] == approx(newlayers[2], abs=0.001, nan_ok=True)

    assert newlayernames == newlayernames
    assert layernodata == newnodatavalue

    vr.close()  # have to close to close logger file handle
    os.remove(output_filename)
    assert not os.path.exists(output_filename)
    os.remove(logfile)
    assert not os.path.exists(logfile)


# def test_raster_write_to_geotiff_new2d():
#     # need to be clear about this process.  Are we warping?
#     logfile = os.path.join(os.path.split(test_file)[0], 'test_log.txt')
#     vr = VyperRaster(test_file, logfile=logfile)
#     output_filename = os.path.join(os.path.split(test_file)[0], 'vyperdatum_file_4326.tif')
#     # take the utm nad83 raster input, and write a geographic wgs84 raster with NOAA MLLW depths
#     layers, layernames, layernodata = vr.transform_raster('navd88', 'mllw', allow_points_outside_coverage=True, output_file=output_filename)

#     # original 26919 geotransform that we pulled from the file
#     assert vr.geotransform[0] == 339262.0
#     assert vr.geotransform[3] == 4693254.0
#     assert vr.geotransform[1] == 4.0
#     assert vr.geotransform[5] == -4.0
#     assert vr.geotransform[2] == 0.0
#     assert vr.geotransform[4] == 0.0

#     # since we supplied a new 2d crs for the output, we get his output_geotranform
#     assert vr.output_geotransform[0] == approx(-70.94997811389081, abs=0.000001)
#     assert vr.output_geotransform[3] == approx(42.37624115875231, abs=0.000001)
#     assert vr.output_geotransform[1] == approx(4.707791728663476e-05, abs=0.000001)
#     assert vr.output_geotransform[5] == approx(-3.661334879672518e-05, abs=0.000001)
#     assert vr.output_geotransform[2] == 0.0
#     assert vr.output_geotransform[4] == 0.0

#     assert os.path.exists(output_filename)

#     ofile = gdal.Open(output_filename)
#     newlayers = [ofile.GetRasterBand(i + 1).ReadAsArray() for i in range(ofile.RasterCount)]
#     newnodatavalue = [ofile.GetRasterBand(i + 1).GetNoDataValue() for i in range(ofile.RasterCount)]
#     newlayernames = [ofile.GetRasterBand(i + 1).GetDescription() for i in range(ofile.RasterCount)]
#     ofile = None

#     assert layers[0] == approx(newlayers[0], abs=0.001, nan_ok=True)
#     assert layers[1] == approx(newlayers[1], abs=0.001, nan_ok=True)
#     assert layers[2] == approx(newlayers[2], abs=0.001, nan_ok=True)

#     assert newlayernames == newlayernames
#     assert layernodata == newnodatavalue

#     vr.close()  # have to close to close logger file handle
#     os.remove(output_filename)
#     assert not os.path.exists(output_filename)
#     os.remove(logfile)
#     assert not os.path.exists(logfile)
