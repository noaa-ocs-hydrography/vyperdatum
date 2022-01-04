from pytest import approx

from vyperdatum.points import *
from vyperdatum.vdatum_validation import vdatum_answers

gvc = VyperCore()
data_folder = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data')
vdatum_answer = vdatum_answers[gvc.datum_data.vdatum_version]


def test_points_setup():
    # these tests assume you have the vdatum path setup in VyperCore
    # first time, you need to run it with the path to the vdatum folder, vp = VyperPoints('path\to\vdatum')
    vp = VyperPoints()
    assert os.path.exists(vp.datum_data.vdatum_path)
    assert vp.datum_data.grid_files
    assert vp.datum_data.polygon_files
    assert vp.datum_data.vdatum_version
    assert vp.datum_data.regions


def _transform_dataset(region: str):
    vp = VyperPoints()
    x = vdatum_answer[region]['x']
    y = vdatum_answer[region]['y']
    z = vdatum_answer[region]['z_nad83']
    vp.transform_points((6319, 'ellipse'), 'mllw', x, y, z=z, include_vdatum_uncertainty=False)

    assert vp.x == approx(x, abs=0.0001)
    assert vp.y == approx(y, abs=0.0001)
    assert vp.z == approx(vdatum_answer[region]['z_mllw'], abs=0.002)


def _transform_dataset_sampled(region: str):
    vp = VyperPoints()
    x = vdatum_answer[region]['x']
    y = vdatum_answer[region]['y']
    z = vdatum_answer[region]['z_nad83']
    vp.transform_points((6319, 'ellipse'), 'mllw', x, y, z=z, include_vdatum_uncertainty=False, sample_distance=0.0005)

    # sampled points workflow does not return new xy coordinates, we can't just expand the sampled points to get new xy
    assert vp.x is None
    assert vp.y is None
    assert vp.z == approx(vdatum_answer[region]['z_mllw'], abs=0.002)
    

def test_transform_north_carolina_dataset():
    _transform_dataset('north_carolina')


def test_transform_texas_dataset():
    _transform_dataset('texas')


def test_transform_california_dataset():
    _transform_dataset('california')


def test_transform_alaska_southeast_dataset():
    _transform_dataset('alaska_southeast')


def test_transform_north_carolina_dataset_sampled():
    _transform_dataset_sampled('north_carolina')


def test_transform_texas_dataset_sampled():
    _transform_dataset_sampled('texas')


def test_transform_california_dataset_sampled():
    _transform_dataset_sampled('california')


def test_transform_alaska_southeast_dataset_sampled():
    _transform_dataset_sampled('alaska_southeast')


def _transform_dataset_direction():
    vp = VyperPoints()
    x = vdatum_answer['north_carolina']['x']
    y = vdatum_answer['north_carolina']['y']
    z = vdatum_answer['north_carolina']['z_nad83']

    # assumes positive up input, and mllw means positive up output
    vp.transform_points((6319, 'ellipse'), 'mllw', x, y, z=z, include_vdatum_uncertainty=False)
    assert vp.z == approx(vdatum_answer['north_carolina']['z_mllw'], abs=0.002)

    # if we want positive down output, we need to use an epsg with positive down axis direction for mllw
    vp = VyperPoints()
    vp.transform_points((6319, 'ellipse'), 5866, x, y, z=z, include_vdatum_uncertainty=False)
    assert vp.z == approx(-vdatum_answer['north_carolina']['z_mllw'], abs=0.002)
