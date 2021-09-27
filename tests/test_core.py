from pytest import approx

from vyperdatum.core import *
from vyperdatum.vdatum_validation import vdatum_answers

vc = VyperCore()
data_folder = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data')
vdatum_answer = vdatum_answers[vc.vdatum.vdatum_version]


def test_core_setup():
    # these tests assume you have the vdatum path setup in VyperCore
    # first time, you need to run it with the path to the vdatum folder, vc = VyperCore('path\to\vdatum')
    vc = VyperCore()
    assert os.path.exists(vc.vdatum.vdatum_path)
    assert vc.vdatum.grid_files
    assert vc.vdatum.polygon_files
    assert vc.vdatum.vdatum_version
    assert vc.vdatum.regions


def test_regions():
    vc = VyperCore()
    vc.set_input_datum((6318, 'mllw'))
    vc.set_region_by_bounds(-75.79179, 35.80674, -75.3853, 36.01585)
    assert len(vc.regions) == 2
    assert vc.regions[0].find('NCcoast') != -1
    assert vc.regions[1].find('NCinner') != -1


def test_3d_to_compound():
    vc = VyperCore()
    vc.set_input_datum((6319, 'mllw'))
    vc.set_region_by_bounds(-75.79179, 35.80674, -75.3853, 36.01585)
    assert len(vc.regions) == 2
    assert vc.regions[0].find('NCcoast') != -1
    assert vc.regions[1].find('NCinner') != -1


def test_out_of_bounds():
    vc = VyperCore()
    vc.set_input_datum((6318, 'mllw'))
    vc.set_region_by_bounds(-155.29119, 57.12611, -154.56609, 57.67068)
    assert vc.regions == []


def test_set_input_datum():
    vc = VyperCore()
    vc.set_input_datum(6318)
    vc.set_region_by_bounds(-75.79179, 35.80674, -75.3853, 36.01585)
    vc.set_input_datum('mllw')

    assert vc.in_crs.vyperdatum_str == 'mllw'
    assert vc.in_crs.pipeline_string == '[+proj=pipeline +step +proj=vgridshift grids=core\\geoid12b\\g2012bu0.gtx ' \
                                        '+step +inv +proj=vgridshift grids=NCcoast11_8301\\tss.gtx ' \
                                        '+step +proj=vgridshift grids=NCcoast11_8301\\mllw.gtx;' \
                                        '+proj=pipeline +step +proj=vgridshift grids=core\\geoid12b\\g2012bu0.gtx ' \
                                        '+step +inv +proj=vgridshift grids=NCinner11_8301\\tss.gtx ' \
                                        '+step +proj=vgridshift grids=NCinner11_8301\\mllw.gtx]'

    assert len(vc.regions) == 2
    assert vc.regions[0].find('NCcoast') != -1
    assert vc.regions[1].find('NCinner') != -1


def test_set_output_datum():
    vc = VyperCore()
    vc.set_input_datum(6318)
    vc.set_region_by_bounds(-75.79179, 35.80674, -75.3853, 36.01585)
    vc.set_output_datum('geoid')

    assert vc.out_crs.vyperdatum_str == 'geoid'
    assert vc.out_crs.pipeline_string == '[+proj=pipeline +step +proj=vgridshift grids=core\\geoid12b\\g2012bu0.gtx;+proj=pipeline +step +proj=vgridshift grids=core\\geoid12b\\g2012bu0.gtx]'
    assert len(vc.regions) == 2
    assert vc.regions[0].find('NCcoast') != -1
    assert vc.regions[1].find('NCinner') != -1


def _transform_region_dataset(region: str):
    vc = VyperCore()
    vc.set_input_datum(6318)
    vc.set_input_datum('ellipse')
    vc.set_output_datum((6318, 'mllw'))
    x = vdatum_answer[region]['x']
    y = vdatum_answer[region]['y']
    z = vdatum_answer[region]['z_nad83']
    newx, newy, newz, _, _ = vc.transform_dataset(x, y, z, include_vdatum_uncertainty=False)

    assert x == approx(newx, abs=0.00001)
    assert y == approx(newy, abs=0.00001)
    assert newz == approx(vdatum_answer[region]['z_mllw'], abs=0.001)

    vc = VyperCore()
    vc.set_input_datum(6318)
    vc.set_input_datum('ellipse')
    vc.set_output_datum((6318, 'mhw'))
    x = vdatum_answer[region]['x']
    y = vdatum_answer[region]['y']
    z = vdatum_answer[region]['z_nad83']
    newx, newy, newz, _, _ = vc.transform_dataset(x, y, z, include_vdatum_uncertainty=False)

    assert x == approx(newx, abs=0.00001)
    assert y == approx(newy, abs=0.00001)
    assert newz == approx(vdatum_answer[region]['z_mhw'], abs=0.001)


def test_transform_north_carolina_dataset():
    _transform_region_dataset('north_carolina')


def test_transform_texas_dataset():
    _transform_region_dataset('texas')


def test_transform_to_sounding_dataset():
    # vdatum online answer, 9/1/2021, epoch 2021.0, (-75.79180, 36.01570, 10.5) ->  z=49.504
    vc = VyperCore()
    vc.set_input_datum(6318)
    vc.set_input_datum('ellipse')
    vc.set_output_datum((6318, 5866))
    x = np.array([-75.79180, -75.79190, -75.79200])
    y = np.array([36.01570, 36.01560, 36.01550])
    z = np.array([10.5, 11.0, 11.5])
    newx, newy, newz, _, _ = vc.transform_dataset(x, y, z, include_vdatum_uncertainty=False)

    assert (x == newx).all()
    assert (y == newy).all()
    assert (newz == np.array([-49.518, -50.018, -50.518])).all()


def test_transform_dataset_inv():
    vc = VyperCore()
    vc.set_input_datum(6318)
    vc.set_input_datum('mllw')
    vc.set_output_datum('ellipse')
    x = np.array([-75.79180, -75.79190, -75.79200])
    y = np.array([36.01570, 36.01560, 36.01550])
    z = np.array([49.518, 50.018, 50.518])
    newx, newy, newz, _, _ = vc.transform_dataset(x, y, z, include_vdatum_uncertainty=False)

    assert (x == newx).all()
    assert (y == newy).all()
    assert (newz == np.array([10.5, 11.0, 11.5])).all()


def test_transform_dataset_unc():
    vc = VyperCore()
    vc.set_input_datum(6318)
    vc.set_region_by_bounds(-75.79179, 35.80674, -75.3853, 36.01585)
    vc.set_input_datum('ellipse')
    vc.set_output_datum('mllw')
    x = np.array([-75.79180, -75.79190, -75.79200])
    y = np.array([36.01570, 36.01560, 36.01550])
    z = np.array([10.5, 11.0, 11.5])
    newx, newy, newz, newunc, _ = vc.transform_dataset(x, y, z)

    assert (x == newx).all()
    assert (y == newy).all()
    assert (newz == np.array([49.518, 50.018, 50.518])).all()  # no vert transformation with 2d source epsg
    assert (newunc == np.array([0.065, 0.065, 0.065])).all()  # ncinner.mllw=1.5, conus.navd88=5.0


def test_transform_dataset_stateplane():
    # try out the built in transform from EPSG to nad83 to get the new horiz and vert
    vc = VyperCore()
    x = np.array([898745.505, 898736.854, 898728.203])
    y = np.array([256015.372, 256003.991, 255992.610])
    z = np.array([10.5, 11.0, 11.5])

    vc.set_input_datum((3631, 'ellipse'), extents=(min(x), min(y), max(x), max(y)))  # testing with NorthCarolina nad83 ft us
    vc.set_output_datum('mllw')

    newx, newy, newz, newunc, _ = vc.transform_dataset(x, y, z)

    assert newx == approx(np.array([-75.7917999, -75.7918999, -75.7919999]), abs=0.000001)
    assert newy == approx(np.array([36.0156999, 36.01559999, 36.01549999]), abs=0.000001)
    assert newz == approx(np.array([49.518, 50.018, 50.518]), abs=0.001)  # no vert transformation with 2d source epsg
    assert newunc == approx(np.array([0.065, 0.065, 0.065]), abs=0.001)  # ncinner.mllw=1.5, conus.navd88=5.0


def test_transform_dataset_region_index():
    vc = VyperCore()
    vc.set_input_datum((6318, 'ellipse'))
    vc.set_region_by_bounds(-75.79179, 35.80674, -75.3853, 36.01585)
    vc.set_output_datum('mllw')
    x = np.array([-75.79180, -75.79190, -75.79200])
    y = np.array([36.01570, 36.01560, 36.01550])
    z = np.array([10.5, 11.0, 11.5])
    newx, newy, newz, newunc, newregion = vc.transform_dataset(x, y, z, include_vdatum_uncertainty=True, include_region_index=True)

    assert (x == newx).all()
    assert (y == newy).all()
    assert (newz == np.array([49.518, 50.018, 50.518])).all()
    assert (newunc == np.array([0.065, 0.065, 0.065])).all()  # ncinner.mllw=1.5, conus.navd88=5.0
    newregionlist = np.array(vc.regions)[newregion].tolist()
    assert len(newregionlist) == 3
    assert newregionlist[0] == newregionlist[1] == newregionlist[2]
    assert newregionlist[0].find('NCinner') != -1


def test_transform_dataset_with_log():
    logfile = os.path.join(data_folder, 'newlog.txt')
    vc = VyperCore(logfile=logfile)
    vc.set_input_datum(6319)
    vc.set_region_by_bounds(-75.79179, 35.80674, -75.3853, 36.01585)
    vc.set_output_datum('mllw')
    x = np.array([-75.79180, -75.79190, -75.79200])
    y = np.array([36.01570, 36.01560, 36.01550])
    z = np.array([10.5, 11.0, 11.5])
    newx, newy, newz, _, _ = vc.transform_dataset(x, y, z, include_vdatum_uncertainty=False)

    assert os.path.exists(logfile)
    vc.close()
    os.remove(logfile)
    assert not os.path.exists(logfile)


def test_vdatum_software_compare():
    point_x = -122.4780505
    point_y = 47.7890222

    vdatum_sep_from_shapefile_nad83_mllw = 23.73747

    vdatum_online_nad83_mllw = 23.738
    vdatum_online_nad83_navd88 = 23.083
    vdatum_online_navd88_lmsl = -1.310
    vdatum_online_lmsl_mllw = 1.965

    vc = VyperCore()
    vc.set_input_datum(6319)
    vc.set_region_by_bounds(-122.4781505, 47.7890222, -122.4780505, 47.7891222)
    x = np.array([point_x])
    y = np.array([point_y])
    z = np.array([0.0])

    vc.set_input_datum('ellipse')
    vc.set_output_datum('mllw')
    _, _, vyperdatum_nad83_mllw, _, _ = vc.transform_dataset(x, y, z, include_vdatum_uncertainty=False,
                                                             include_region_index=False)
    vc.set_input_datum('ellipse')
    vc.set_output_datum('geoid')
    _, _, vyperdatum_nad83_navd88, _, _ = vc.transform_dataset(x, y, z, include_vdatum_uncertainty=False,
                                                               include_region_index=False)
    vc.set_input_datum('geoid')
    vc.set_output_datum('tss')
    _, _, vyperdatum_navd88_lmsl, _, _ = vc.transform_dataset(x, y, z, include_vdatum_uncertainty=False,
                                                              include_region_index=False)
    vc.set_input_datum('tss')
    vc.set_output_datum('mllw')
    _, _, vyperdatum_lmsl_mllw, _, _ = vc.transform_dataset(x, y, z, include_vdatum_uncertainty=False,
                                                            include_region_index=False)

    # currently there is this small difference between the nad83_geoid12b transformation that is in vyperdatum that is not
    # in vdatum online/vdatum sep from shapefile
    assert vdatum_online_nad83_mllw == approx(vyperdatum_nad83_mllw, abs=0.05)
    assert vdatum_online_nad83_navd88 == approx(vyperdatum_nad83_navd88, abs=0.05)
    assert vdatum_online_navd88_lmsl == vyperdatum_navd88_lmsl
    assert vdatum_online_lmsl_mllw == vyperdatum_lmsl_mllw
