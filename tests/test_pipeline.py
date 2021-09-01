import os
from pyproj import Transformer

from vyperdatum.pipeline import *
from vyperdatum.core import VyperCore


def get_test_grid():
    vc = VyperCore()  # load this to get the cached vdatum path
    # first time, you need to run it with the path to the vdatum folder, vc = VyperCore('path\to\vdatum')
    if not os.path.exists(vc.vdatum.vdatum_path):
        raise EnvironmentError('You have to run VyperCore once and set the vdatum path in order for this to work')
    tstgrid = os.path.join(vc.vdatum.vdatum_path, 'CAORblan01_8301')
    return tstgrid


def test_get_regional_pipeline_upperlower():
    pipe = get_regional_pipeline('NAD83', 'TSS', get_test_grid())
    assert pipe == get_regional_pipeline('nad83', 'tss', get_test_grid())


def test_get_regional_pipeline_nad83_tss():
    pipe = get_regional_pipeline('NAD83', 'TSS', get_test_grid())
    assert pipe.count('+step +proj') == 1
    assert pipe.count('+step +inv +proj') == 1
    assert pipe.count('gtx') == 2
    transformer = Transformer.from_pipeline(pipe)
    result = transformer.transform(xx=-124.853, yy=41.227, zz=0)
    assert result == (-124.853, 41.227000000000004, 30.86302107201744)


def test_get_regional_pipeline_tss_nad83():
    pipe = get_regional_pipeline('tss', 'nad83', get_test_grid())
    assert pipe.count('+step +inv +proj') == 1
    assert pipe.count('+step +proj') == 1
    assert pipe.count('gtx') == 2
    transformer = Transformer.from_pipeline(pipe)
    result = transformer.transform(xx=-124.853, yy=41.227, zz=0)
    assert result == (-124.853, 41.227000000000004, -30.86302107201744)


def test_get_regional_pipeline_mllw():
    pipe = get_regional_pipeline('nad83', 'mllw', get_test_grid())
    assert pipe.count('+step +proj') == 2
    assert pipe.count('+step +inv +proj') == 1
    assert pipe.count('gtx') == 3
    assert pipe.count('mllw') == 1
    transformer = Transformer.from_pipeline(pipe)
    result = transformer.transform(xx=-124.853, yy=41.227, zz=0)
    assert result == (-124.853, 41.227000000000004, 31.97132104264427)


def test_get_regional_pipeline_mhw():
    pipe = get_regional_pipeline('nad83', 'mhw', get_test_grid())
    assert pipe.count('+step +proj') == 2
    assert pipe.count('+step +inv +proj') == 1
    assert pipe.count('gtx') == 3
    assert pipe.count('mhw') == 1
    transformer = Transformer.from_pipeline(pipe)
    result = transformer.transform(xx=-124.853, yy=41.227, zz=0)
    assert result == (-124.853, 41.227000000000004, 30.11322104560066)


def test_get_regional_pipeline_null():
    pipe = get_regional_pipeline('mllw', 'mllw', get_test_grid())
    assert pipe is None


if __name__ == '__main__':
    test_get_regional_pipeline_mhw()
    test_get_regional_pipeline_mllw()
    test_get_regional_pipeline_nad83_tss()
    test_get_regional_pipeline_null()
    test_get_regional_pipeline_tss_nad83()
    test_get_regional_pipeline_upperlower()
