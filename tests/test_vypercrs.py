from vyperdatum.vypercrs import *


def test_vertical_derived_crs():
    cs = VerticalDerivedCRS('mllw', 'nad83', 'NAD83(2011) Height to NOAA Mean Lower Low Water',
                            'VDatum gtx grid transformation')

    assert cs.datum_name == 'mllw'
    assert cs.base_datum_name == 'nad83'
    assert cs.conversion_name == 'NAD83(2011) Height to NOAA Mean Lower Low Water'
    assert cs.conversion_method == 'VDatum gtx grid transformation'
    assert cs.coordinate_type == 'vertical'
    assert cs.coordinate_axis == ('height',)
    assert cs.coordinate_units == 'm'

    assert cs._base_crs.to_wkt() == 'BASEVERTCRS["nad83",VDATUM["nad83"],ID["EPSG",6319]]'
    assert cs._deriving_conversion.to_wkt() == 'DERIVINGCONVERSION["NAD83(2011) Height to NOAA Mean Lower Low Water",METHOD["VDatum gtx grid transformation", ID["EPSG",1084]]]'
    assert cs._vertical_datum.to_wkt() == 'VDATUM["mllw"]'
    assert cs._coordinate_system.to_wkt() == 'CS[vertical,1],AXIS["gravity-related height (H)",up],LENGTHUNIT["metre",1]'

    expected_out = 'VERTCRS["mllw",BASEVERTCRS["nad83",VDATUM["nad83"],ID["EPSG",6319]],DERIVINGCONVERSION["NAD83(2011) '
    expected_out += 'Height to NOAA Mean Lower Low Water",METHOD["VDatum gtx grid transformation", ID["EPSG",1084]]],'
    expected_out += 'VDATUM["mllw"],CS[vertical,1],AXIS["gravity-related height (H)",up],LENGTHUNIT["metre",1]]'
    assert expected_out == cs.to_wkt()
    assert cs.to_crs()


def test_derived_parameter_file():
    cs = VerticalDerivedCRS('mllw', 'nad83', 'NAD83(2011) Height to NOAA Mean Lower Low Water',
                            'VDatum gtx grid transformation')
    cs.add_parameter_file('NOAA VDatum', 'g2012bu0', 'core\\geoid12b\\g2012bu0.gtx', 'NAD83 to Geoid12B', '10/23/2012')

    expected_out = 'DERIVINGCONVERSION["NAD83(2011) Height to NOAA Mean Lower Low Water",METHOD["VDatum gtx grid '
    expected_out += 'transformation", ID["EPSG",1084]],PARAMETERFILE["g2012bu0", "core\\geoid12b\\g2012bu0.gtx", '
    expected_out += 'ID["NOAA VDatum", "NAD83 to Geoid12B", "10/23/2012"]]]'
    assert cs._deriving_conversion.to_wkt() == expected_out
    assert cs.to_crs()


def test_vertical_pipeline_crs():
    cs = VerticalPipelineCRS("NOAA Chart Datum")
    cs.add_pipeline("proj=pipeline step proj=vgridshift grids=core\\geoid12b\\g2012bu0.gtx step proj=vgridshift grids=REGION\\tss.gtx",
                    "TXlagmat01_8301")
    cs.add_pipeline("proj=pipeline step proj=vgridshift grids=core\\geoid12b\\g2012bu0.gtx step proj=vgridshift grids=REGION\\tss.gtx",
                    "TXlaggal01_8301")

    assert cs.regions == ['TXlagmat01_8301', 'TXlaggal01_8301']
    assert cs.pipeline_string == 'proj=pipeline step proj=vgridshift grids=core\\geoid12b\\g2012bu0.gtx step proj=vgridshift grids=REGION\\tss.gtx'
    assert cs.datum_name == 'NOAA Chart Datum'
    assert cs.coordinate_type == 'vertical'
    assert cs.coordinate_axis == ('height',)
    assert cs.coordinate_units == 'm'

    expected_out = 'VERTCRS["NOAA Chart Datum",VDATUM["NOAA Chart Datum"],CS[vertical,1],AXIS["gravity-related height ' \
                   '(H)",up],LENGTHUNIT["metre",1],REMARK["regions=[TXlagmat01_8301,TXlaggal01_8301],' \
                   'pipeline=proj=pipeline step proj=vgridshift grids=core\\geoid12b\\g2012bu0.gtx ' \
                   'step proj=vgridshift grids=REGION\\tss.gtx"]]'
    assert expected_out == cs.to_wkt()
    assert cs.to_crs()


def test_transformation_inv_nad83():
    cs = VerticalPipelineCRS("NOAA Chart Datum")
    cs.add_pipeline("proj=pipeline step proj=vgridshift grids=core\\geoid12b\\g2012bu0.gtx step proj=vgridshift grids=REGION\\tss.gtx step proj=vgridshift grids=REGION\\mllw.gtx",
                    "TXlagmat01_8301")
    cs.add_pipeline("proj=pipeline step proj=vgridshift grids=core\\geoid12b\\g2012bu0.gtx step proj=vgridshift grids=REGION\\tss.gtx step proj=vgridshift grids=REGION\\mllw.gtx",
                    "TXlaggal01_8301")

    cstwo = VerticalPipelineCRS("nad83")
    pipe = get_transformation_pipeline(cs, cstwo, "TXlaggal01_8301")
    assert pipe == 'proj=pipeline step inv proj=vgridshift grids=TXlaggal01_8301\\mllw.gtx ' \
                   'step inv +inv proj=vgridshift grids=TXlaggal01_8301\\tss.gtx ' \
                   'step inv proj=vgridshift grids=core\\geoid12b\\g2012bu0.gtx'


def test_transformation_tss():
    cs = VerticalPipelineCRS("tss")
    cs.add_pipeline("proj=pipeline step proj=vgridshift grids=core\\geoid12b\\g2012bu0.gtx step proj=vgridshift grids=REGION\\tss.gtx",
                    "TXlagmat01_8301")

    cstwo = VerticalPipelineCRS("mllw")
    cstwo.add_pipeline("proj=pipeline step proj=vgridshift grids=core\\geoid12b\\g2012bu0.gtx step proj=vgridshift grids=REGION\\tss.gtx step proj=vgridshift grids=REGION\\mllw.gtx",
                       "TXlagmat01_8301")

    pipe = get_transformation_pipeline(cs, cstwo, "TXlagmat01_8301")
    assert pipe == 'proj=pipeline step proj=vgridshift grids=TXlagmat01_8301\\mllw.gtx'


def test_transformation_noregion():
    cs = VerticalPipelineCRS("tss")
    cs.add_pipeline(
        "proj=pipeline step proj=vgridshift grids=core\\geoid12b\\g2012bu0.gtx step proj=vgridshift grids=REGION\\tss.gtx",
        "TXlagmat01_8301")

    cstwo = VerticalPipelineCRS("mllw")
    cstwo.add_pipeline(
        "proj=pipeline step proj=vgridshift grids=core\\geoid12b\\g2012bu0.gtx step proj=vgridshift grids=REGION\\tss.gtx step proj=vgridshift grids=REGION\\mllw.gtx",
        "TXlaggal01_8301")

    try:
        pipe = get_transformation_pipeline(cs, cstwo, "TXlagmat01_8301")
        assert False
    except NotImplementedError:  # region specified was not in the cstwo object
        assert True


def test_transformation_unsupported_name():
    cs = VerticalPipelineCRS("tss")
    cs.add_pipeline(
        "proj=pipeline step proj=vgridshift grids=core\\geoid12b\\g2012bu0.gtx step proj=vgridshift grids=REGION\\tss.gtx",
        "TXlagmat01_8301")

    cstwo = VerticalPipelineCRS("some_bs")
    cstwo.add_pipeline(
        "proj=pipeline step proj=vgridshift grids=core\\geoid12b\\g2012bu0.gtx step proj=vgridshift grids=REGION\\tss.gtx step proj=vgridshift grids=REGION\\mllw.gtx",
        "TXlaggal01_8301")

    try:
        pipe = get_transformation_pipeline(cs, cstwo, "TXlagmat01_8301")
        assert False
    except NotImplementedError:  # name specified in cstwo was not in the datum definition dictionary
        assert True


if __name__ == '__main__':
    test_derived_parameter_file()
    test_transformation_inv_nad83()
    test_transformation_noregion()
    test_transformation_tss()
    test_transformation_unsupported_name()
    test_vertical_derived_crs()
    test_vertical_pipeline_crs()
