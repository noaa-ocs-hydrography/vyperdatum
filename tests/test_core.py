from pytest import approx

from vyperdatum.core import *


data_folder = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data')


def test_core_setup():
    # these tests assume you have the vdatum path setup in VyperCore
    # first time, you need to run it with the path to the vdatum folder, vc = VyperCore('path\to\vdatum')
    vc = VyperCore()
    assert os.path.exists(vc.vdatum.vdatum_path)
    assert vc.vdatum.grid_files
    assert vc.vdatum.polygon_files


def test_regions():
    vc = VyperCore()
    vc.set_region_by_bounds(-75.79179, 35.80674, -75.3853, 36.01585)
    assert vc.regions == ['NCcoast11_8301', 'NCinner11_8301']


def test_is_alaska():
    vc = VyperCore()
    vc.set_region_by_bounds(-75.79179, 35.80674, -75.3853, 36.01585)
    assert not vc.is_alaska()
    vc.set_region_by_bounds(-136.56527, 56.21873, -135.07113, 56.77662)
    assert vc.is_alaska()


def test_out_of_bounds():
    vc = VyperCore()
    vc.set_region_by_bounds(-155.29119, 57.12611, -154.56609, 57.67068)

    assert vc.regions == []
    try:
        vc.is_alaska()
    except ValueError:  # no regions, so this will fail with valueerror exception
        assert True


def test_set_input_datum():
    vc = VyperCore()
    vc.set_region_by_bounds(-75.79179, 35.80674, -75.3853, 36.01585)
    vc.set_input_datum('mllw')

    assert vc.in_crs.datum_name == 'mllw'
    assert vc.in_crs.pipeline_string == 'proj=pipeline step proj=vgridshift grids=core\\geoid12b\\g2012bu0.gtx ' \
                                        'step +inv proj=vgridshift grids=REGION\\tss.gtx ' \
                                        'step proj=vgridshift grids=REGION\\mllw.gtx'
    assert vc.in_crs.regions == ['NCcoast11_8301', 'NCinner11_8301']


def test_set_output_datum():
    vc = VyperCore()
    vc.set_region_by_bounds(-75.79179, 35.80674, -75.3853, 36.01585)
    vc.set_output_datum('geoid12b')

    assert vc.out_crs.datum_name == 'geoid12b'
    assert vc.out_crs.pipeline_string == 'proj=pipeline step proj=vgridshift grids=core\\geoid12b\\g2012bu0.gtx'
    assert vc.out_crs.regions == ['NCcoast11_8301', 'NCinner11_8301']


def test_transform_dataset():
    vc = VyperCore()
    vc.set_region_by_bounds(-75.79179, 35.80674, -75.3853, 36.01585)
    vc.set_input_datum('nad83')
    vc.set_output_datum('mllw')
    x = np.array([-75.79180, -75.79190, -75.79200])
    y = np.array([36.01570, 36.01560, 36.01550])
    z = np.array([10.5, 11.0, 11.5])
    newx, newy, newz, _, _ = vc.transform_dataset(x, y, z, include_vdatum_uncertainty=False)

    assert (x == newx).all()
    assert (y == newy).all()
    assert (newz == np.array([49.518, 50.018, 50.518])).all()

    assert vc.out_crs.to_wkt() == 'VERTCRS["mllw",VDATUM["mllw"],' \
                                  'CS[vertical,1],AXIS["gravity-related height (H)",up],LENGTHUNIT["metre",1],' \
                                  'REMARK["regions=[NCcoast11_8301,NCinner11_8301],' \
                                  'pipeline=proj=pipeline step proj=vgridshift grids=core\\geoid12b\\g2012bu0.gtx ' \
                                  'step +inv proj=vgridshift grids=REGION\\tss.gtx ' \
                                  'step proj=vgridshift grids=REGION\\mllw.gtx"]]'


def test_transform_dataset_alaska():
    vc = VyperCore()
    vc.set_region_by_bounds(-136.56527, 56.21873, -135.07113, 56.77662)
    vc.set_input_datum('nad83')
    vc.set_output_datum('mllw')
    x = np.array([-136.0, -136.1, -136.2])
    y = np.array([56.25, 56.35, 56.45])
    z = np.array([10.5, 11.0, 11.5])
    newx, newy, newz, _, _ = vc.transform_dataset(x, y, z, include_vdatum_uncertainty=False)

    assert approx(x == newx, 0.01)
    assert approx(y == newy, 0.01)
    assert approx(newz == np.array([14.932, 15.128, 15.232]), 0.001)

    assert vc.out_crs.to_wkt() == 'VERTCRS["mllw",VDATUM["mllw"],' \
                                  'CS[vertical,1],AXIS["gravity-related height (H)",up],LENGTHUNIT["metre",1],' \
                                  'REMARK["regions=[AKglacier00_8301,AKwhale00_8301],pipeline=proj=pipeline ' \
                                  'step proj=vgridshift grids=core\\xgeoid17b\\AK_17B.gtx step +inv proj=vgridshift ' \
                                  'grids=REGION\\tss.gtx step proj=vgridshift grids=REGION\\mllw.gtx"]]'


def test_transform_dataset_inv():
    vc = VyperCore()
    vc.set_region_by_bounds(-75.79179, 35.80674, -75.3853, 36.01585)
    vc.set_input_datum('mllw')
    vc.set_output_datum('nad83')
    x = np.array([-75.79180, -75.79190, -75.79200])
    y = np.array([36.01570, 36.01560, 36.01550])
    z = np.array([49.490, 49.990, 50.490])
    newx, newy, newz, _, _ = vc.transform_dataset(x, y, z, include_vdatum_uncertainty=False)

    assert (x == newx).all()
    assert (y == newy).all()
    assert (newz == np.array([10.5, 11.0, 11.5])).all()

    assert vc.out_crs.to_wkt() == 'VERTCRS["nad83",VDATUM["nad83"],' \
                                  'CS[vertical,1],AXIS["gravity-related height (H)",up],LENGTHUNIT["metre",1],' \
                                  'REMARK["regions=[],pipeline="]]'


def test_transform_dataset_unc():
    vc = VyperCore()
    vc.set_region_by_bounds(-75.79179, 35.80674, -75.3853, 36.01585)
    vc.set_input_datum('nad83')
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
    # if you provide an EPSG that is a 2d system, it assumes the z provided is at nad83
    vc = VyperCore()
    x = np.array([898745.505, 898736.854, 898728.203])
    y = np.array([256015.372, 256003.991, 255992.610])
    z = np.array([10.5, 11.0, 11.5])

    vc.set_input_datum(3631, extents=(min(x), min(y), max(x), max(y)))  # testing with NorthCarolina nad83 ft us
    vc.set_output_datum('mllw')

    newx, newy, newz, newunc, _ = vc.transform_dataset(x, y, z)

    assert (newx == approx(np.array([-75.7917999, -75.7918999, -75.7919999]), 0.000001))
    assert (newy == approx(np.array([36.0156999, 36.01559999, 36.01549999]), 0.000001))
    assert (newz == np.array([49.518, 50.018, 50.518])).all()  # no vert transformation with 2d source epsg
    assert (newunc == np.array([0.065, 0.065, 0.065])).all()  # ncinner.mllw=1.5, conus.navd88=5.0


def test_transform_dataset_region_index():
    vc = VyperCore()
    vc.set_region_by_bounds(-75.79179, 35.80674, -75.3853, 36.01585)
    vc.set_input_datum('nad83')
    vc.set_output_datum('mllw')
    x = np.array([-75.79180, -75.79190, -75.79200])
    y = np.array([36.01570, 36.01560, 36.01550])
    z = np.array([10.5, 11.0, 11.5])
    newx, newy, newz, newunc, newregion = vc.transform_dataset(x, y, z, include_vdatum_uncertainty=True, include_region_index=True)

    assert (x == newx).all()
    assert (y == newy).all()
    assert (newz == np.array([49.518, 50.018, 50.518])).all()
    assert (newunc == np.array([0.065, 0.065, 0.065])).all()  # ncinner.mllw=1.5, conus.navd88=5.0
    assert np.array(vc.regions)[newregion].tolist() == ['NCinner11_8301', 'NCinner11_8301', 'NCinner11_8301']


def test_transform_dataset_with_log():
    logfile = os.path.join(data_folder, 'newlog.txt')
    vc = VyperCore(logfile=logfile)

    vc.set_region_by_bounds(-75.79179, 35.80674, -75.3853, 36.01585)
    vc.set_input_datum('nad83')
    vc.set_output_datum('mllw')
    x = np.array([-75.79180, -75.79190, -75.79200])
    y = np.array([36.01570, 36.01560, 36.01550])
    z = np.array([10.5, 11.0, 11.5])
    newx, newy, newz, _, _ = vc.transform_dataset(x, y, z, include_vdatum_uncertainty=False)

    assert os.path.exists(logfile)
    vc.close()
    os.remove(logfile)
    assert not os.path.exists(logfile)
