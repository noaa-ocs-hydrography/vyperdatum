import os
from pyproj import Transformer

from vyperdatum.pipeline import *
from vyperdatum.core import VyperCore


vc = VyperCore()  # run this once so that the path to the grids is added in pyproj


def test_get_regional_pipeline_upperlower():
    pipe = get_regional_pipeline('Ellipse', 'TSS', 'CAORblan01_8301', r'core\geoid12b\g2012bu0.gtx')
    assert pipe == get_regional_pipeline('ellipse', 'tss', 'CAORblan01_8301', r'core\geoid12b\g2012bu0.gtx')


def test_get_regional_pipeline_nad83_tss():
    pipe = get_regional_pipeline('ellipse', 'TSS', 'CAORblan01_8301', r'core\geoid12b\g2012bu0.gtx')
    assert pipe.count('+step +proj') == 1
    assert pipe.count('+step +inv +proj') == 1
    assert pipe.count('gtx') == 2

    # can't specify a region like this in a test, it limits your test to a specific version of vdatum where that region
    #   exists, and is in the same state as your current version

    # transformer = Transformer.from_pipeline(pipe)
    # result = transformer.transform(xx=-124.853, yy=41.227, zz=0)
    # assert result == (-124.853, 41.227000000000004, 30.86302107201744)


def test_get_regional_pipeline_tss_nad83():
    pipe = get_regional_pipeline('tss', 'ellipse', 'CAORblan01_8301', r'core\geoid12b\g2012bu0.gtx')
    assert pipe.count('+step +inv +proj') == 1
    assert pipe.count('+step +proj') == 1
    assert pipe.count('gtx') == 2

    # can't specify a region like this in a test, it limits your test to a specific version of vdatum where that region
    #   exists, and is in the same state as your current version

    # transformer = Transformer.from_pipeline(pipe)
    # result = transformer.transform(xx=-124.853, yy=41.227, zz=0)
    # assert result == (-124.853, 41.227000000000004, -30.86302107201744)


def test_get_regional_pipeline_mllw():
    pipe = get_regional_pipeline('ellipse', 'mllw', 'CAORblan01_8301', r'core\geoid12b\g2012bu0.gtx')
    assert pipe.count('+step +proj') == 2
    assert pipe.count('+step +inv +proj') == 1
    assert pipe.count('gtx') == 3
    assert pipe.count('mllw') == 1

    # can't specify a region like this in a test, it limits your test to a specific version of vdatum where that region
    #   exists, and is in the same state as your current version

    # transformer = Transformer.from_pipeline(pipe)
    # result = transformer.transform(xx=-124.853, yy=41.227, zz=0)
    # assert result == (-124.853, 41.227000000000004, 31.97132104264427)


def test_get_regional_pipeline_mhw():
    pipe = get_regional_pipeline('ellipse', 'mhw', 'CAORblan01_8301', r'core\geoid12b\g2012bu0.gtx')
    assert pipe.count('+step +proj') == 2
    assert pipe.count('+step +inv +proj') == 1
    assert pipe.count('gtx') == 3
    assert pipe.count('mhw') == 1

    # can't specify a region like this in a test, it limits your test to a specific version of vdatum where that region
    #   exists, and is in the same state as your current version

    # transformer = Transformer.from_pipeline(pipe)
    # result = transformer.transform(xx=-124.853, yy=41.227, zz=0)
    # assert result == (-124.853, 41.227000000000004, 30.11322104560066)


def test_get_regional_pipeline_null():
    pipe = get_regional_pipeline('mllw', 'mllw', 'CAORblan01_8301', r'core\geoid12b\g2012bu0.gtx')
    assert pipe is None


if __name__ == '__main__':
    test_get_regional_pipeline_mhw()
    test_get_regional_pipeline_mllw()
    test_get_regional_pipeline_nad83_tss()
    test_get_regional_pipeline_null()
    test_get_regional_pipeline_tss_nad83()
    test_get_regional_pipeline_upperlower()
