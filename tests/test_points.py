from pytest import approx

from vyperdatum.points import *


def test_points_setup():
    # these tests assume you have the vdatum path setup in VyperCore
    # first time, you need to run it with the path to the vdatum folder, vp = VyperPoints('path\to\vdatum')
    vp = VyperPoints()
    assert os.path.exists(vp.vdatum.vdatum_path)
    assert vp.vdatum.grid_files
    assert vp.vdatum.polygon_files


def test_transform_dataset():
    vp = VyperPoints()
    x = np.array([-76.19698, -76.194, -76.198])
    y = np.array([37.1299, 37.1399, 37.1499])
    z = np.array([10.5, 11.0, 11.5])
    vp.transform_points('nad83', 'mllw', x, y, z=z, include_vdatum_uncertainty=False)

    assert (x == vp.x).all()
    assert (y == vp.y).all()
    assert (vp.z == np.array([47.735, 48.219, 48.685])).all()

    assert vp.out_crs.to_wkt() == 'VERTCRS["mllw",VDATUM["mllw"],' \
                                  'CS[vertical,1],AXIS["gravity-related height (H)",up],LENGTHUNIT["metre",1],' \
                                  'REMARK["regions=[MDVAchb12_8301],' \
                                  'pipeline=proj=pipeline step proj=vgridshift grids=core\\geoid12b\\g2012bu0.gtx ' \
                                  'step +inv proj=vgridshift grids=REGION\\tss.gtx ' \
                                  'step proj=vgridshift grids=REGION\\mllw.gtx"]]'


def test_transform_dataset_mhw():
    vp = VyperPoints()
    x = np.array([-76.19698, -76.194, -76.198])
    y = np.array([37.1299, 37.1399, 37.1499])
    z = np.array([10.5, 11.0, 11.5])
    vp.transform_points('noaa chart height', 'noaa chart datum', x, y, z=z, include_vdatum_uncertainty=False)

    assert (x == vp.x).all()
    assert (y == vp.y).all()
    assert (vp.z == np.array([11.227, 11.724, 12.218])).all()

    assert vp.out_crs.to_wkt() == 'VERTCRS["noaa chart datum",VDATUM["noaa chart datum"],' \
                                  'CS[vertical,1],AXIS["gravity-related height (H)",up],LENGTHUNIT["metre",1],' \
                                  'REMARK["regions=[MDVAchb12_8301],' \
                                  'pipeline=proj=pipeline step proj=vgridshift grids=core\\geoid12b\\g2012bu0.gtx ' \
                                  'step +inv proj=vgridshift grids=REGION\\tss.gtx ' \
                                  'step proj=vgridshift grids=REGION\\mllw.gtx"]]'


def test_transform_dataset_geoid():
    vp = VyperPoints()
    x = np.array([-76.19698, -76.194, -76.198])
    y = np.array([37.1299, 37.1399, 37.1499])
    z = np.array([10.5, 11.0, 11.5])
    vp.transform_points('navd88', 'noaa chart datum', x, y, z=z, include_vdatum_uncertainty=False)

    assert (x == vp.x).all()
    assert (y == vp.y).all()
    assert (vp.z == np.array([10.995, 11.493, 11.989])).all()

    assert vp.out_crs.to_wkt() == 'VERTCRS["noaa chart datum",VDATUM["noaa chart datum"],' \
                                  'CS[vertical,1],AXIS["gravity-related height (H)",up],LENGTHUNIT["metre",1],' \
                                  'REMARK["regions=[MDVAchb12_8301],' \
                                  'pipeline=proj=pipeline step proj=vgridshift grids=core\\geoid12b\\g2012bu0.gtx ' \
                                  'step +inv proj=vgridshift grids=REGION\\tss.gtx ' \
                                  'step proj=vgridshift grids=REGION\\mllw.gtx"]]'


def test_transform_dataset_inv_geoid():
    vp = VyperPoints()
    x = np.array([-76.19698, -76.194, -76.198])
    y = np.array([37.1299, 37.1399, 37.1499])
    z = np.array([10.765, 11.262, 11.758])
    vp.transform_points('noaa chart datum', 'navd88', x, y, z=z, include_vdatum_uncertainty=False)

    assert (x == vp.x).all()
    assert (y == vp.y).all()
    assert (vp.z == np.array([10.5, 11.0, 11.5])).all()

    assert vp.out_crs.to_wkt() == 'VERTCRS["navd88",VDATUM["navd88"],' \
                                  'CS[vertical,1],AXIS["gravity-related height (H)",up],LENGTHUNIT["metre",1],' \
                                  'REMARK["regions=[MDVAchb12_8301],' \
                                  'pipeline=proj=pipeline step proj=vgridshift grids=core\\geoid12b\\g2012bu0.gtx"]]'


def test_transform_dataset_2d_noop():
    vp = VyperPoints()
    x = np.array([898745.505, 898736.854, 898728.203])
    y = np.array([256015.372, 256003.991, 255992.610])
    z = np.array([10.5, 11.0, 11.5])
    vp.transform_points(3631, 'mllw', x, y, z=z, include_vdatum_uncertainty=False, force_input_vertical_datum='mllw')

    assert vp.x == approx(np.array([-75.7918, -75.7919, -75.792]), abs=0.0001)
    assert vp.y == approx(np.array([36.0157, 36.0156, 36.0155]), abs=0.0001)
    assert vp.z == approx(z, abs=0.001)

    assert vp.out_crs.to_wkt() == 'VERTCRS["mllw",VDATUM["mllw"],' \
                                  'CS[vertical,1],AXIS["gravity-related height (H)",up],LENGTHUNIT["metre",1],' \
                                  'REMARK["regions=[NCinner11_8301],' \
                                  'pipeline=proj=pipeline step proj=vgridshift grids=core\\geoid12b\\g2012bu0.gtx step ' \
                                  '+inv proj=vgridshift grids=REGION\\tss.gtx step proj=vgridshift grids=REGION\\mllw.gtx"]]'
