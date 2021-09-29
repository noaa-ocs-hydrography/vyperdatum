from vyperdatum.vypercrs import *
from vyperdatum.__version__ import __version__


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
    cs = VerticalPipelineCRS(vdatum_version_string='vdatum_4.1.2', vert_datum_name="NOAA Chart Datum")
    cs.add_pipeline(
        "proj=pipeline step proj=vgridshift grids=core\\geoid12b\\g2012bu0.gtx step proj=vgridshift grids=TXlagmat01_8301\\tss.gtx",
        "TXlagmat01_8301")
    cs.add_pipeline(
        "proj=pipeline step proj=vgridshift grids=core\\geoid12b\\g2012bu0.gtx step proj=vgridshift grids=TXlaggal01_8301\\tss.gtx",
        "TXlaggal01_8301")

    assert cs.regions == ['TXlagmat01_8301', 'TXlaggal01_8301']
    assert cs.pipeline_string == '[proj=pipeline step proj=vgridshift grids=core\\geoid12b\\g2012bu0.gtx step proj=vgridshift grids=TXlagmat01_8301\\tss.gtx;' \
                                 'proj=pipeline step proj=vgridshift grids=core\\geoid12b\\g2012bu0.gtx step proj=vgridshift grids=TXlaggal01_8301\\tss.gtx]'
    assert cs.datum_name == 'NOAA Chart Datum'
    assert cs.coordinate_type == 'vertical'
    assert cs.coordinate_axis == ('height',)
    assert cs.coordinate_units == 'm'

    expected_wkt = 'VERTCRS["NOAA Chart Datum",VDATUM["NOAA Chart Datum"],CS[vertical,1],AXIS["gravity-related height (H)",up],LENGTHUNIT["metre",1],'
    base_wkt, vdatversion, version, base_datum, pipeline_data, regions_data = split_wkt_remarks(cs.to_wkt())
    assert expected_wkt == base_wkt
    assert vdatversion
    assert version == __version__
    assert base_datum == 'NAD83(2011)'
    assert pipeline_data[0].find('TXlagmat01_8301') != -1
    assert pipeline_data[1].find('TXlaggal01_8301') != -1
    assert regions_data[0] == 'TXlagmat01_8301'
    assert regions_data[1] == 'TXlaggal01_8301'


def test_transformation_inv_nad83():
    cs = VerticalPipelineCRS(vdatum_version_string='vdatum_4.1.2', vert_datum_name="NOAA Chart Datum")
    cs.add_pipeline(
        "proj=pipeline step proj=vgridshift grids=core\\geoid12b\\g2012bu0.gtx step proj=vgridshift grids=REGION\\tss.gtx step proj=vgridshift grids=REGION\\mllw.gtx",
        "TXlagmat01_8301")
    cs.add_pipeline(
        "proj=pipeline step proj=vgridshift grids=core\\geoid12b\\g2012bu0.gtx step proj=vgridshift grids=REGION\\tss.gtx step proj=vgridshift grids=REGION\\mllw.gtx",
        "TXlaggal01_8301")

    cstwo = VerticalPipelineCRS(vdatum_version_string='vdatum_4.1.2', vert_datum_name="NAD83(2011)_ellipse")
    pipe = get_transformation_pipeline(cs, cstwo, "TXlaggal01_8301", 'vdatum_4.1.2')
    assert pipe == '+proj=pipeline +step +inv +proj=vgridshift grids=TXlaggal01_8301\\mllw.gtx ' \
                   '+step +proj=vgridshift grids=TXlaggal01_8301\\tss.gtx ' \
                   '+step +inv +proj=vgridshift grids=core\\geoid12b\\g2012bu0.gtx'


def test_transformation_tss():
    cs = VerticalPipelineCRS(vdatum_version_string='vdatum_4.1.2', vert_datum_name="tss")
    cs.add_pipeline(
        "proj=pipeline step proj=vgridshift grids=core\\geoid12b\\g2012bu0.gtx step proj=vgridshift grids=REGION\\tss.gtx",
        "TXlagmat01_8301")

    cstwo = VerticalPipelineCRS(vdatum_version_string='vdatum_4.1.2', vert_datum_name="noaa chart datum")
    cstwo.add_pipeline(
        "proj=pipeline step proj=vgridshift grids=core\\geoid12b\\g2012bu0.gtx step proj=vgridshift grids=REGION\\tss.gtx step proj=vgridshift grids=REGION\\mllw.gtx",
        "TXlagmat01_8301")

    pipe = get_transformation_pipeline(cs, cstwo, "TXlagmat01_8301", 'vdatum_4.1.2')
    assert pipe == '+proj=pipeline +step +proj=vgridshift grids=TXlagmat01_8301\\mllw.gtx'


def test_transformation_noregion():
    cs = VerticalPipelineCRS(vdatum_version_string='vdatum_4.1.2', vert_datum_name="tss")
    cs.add_pipeline(
        "proj=pipeline step proj=vgridshift grids=core\\geoid12b\\g2012bu0.gtx step proj=vgridshift grids=REGION\\tss.gtx",
        "TXlagmat01_8301")

    cstwo = VerticalPipelineCRS(vdatum_version_string='vdatum_4.1.2', vert_datum_name="noaa chart datum")
    cstwo.add_pipeline(
        "proj=pipeline step proj=vgridshift grids=core\\geoid12b\\g2012bu0.gtx step proj=vgridshift grids=REGION\\tss.gtx step proj=vgridshift grids=REGION\\mllw.gtx",
        "TXlaggal01_8301")

    try:
        pipe = get_transformation_pipeline(cs, cstwo, "TXlagmat01_8301", 'vdatum_4.1.2')
        assert False
    except NotImplementedError:  # region specified was not in the cstwo object
        assert True


def test_transformation_unsupported_name():
    cs = VerticalPipelineCRS(vdatum_version_string='vdatum_4.1.2', vert_datum_name="tss")
    cs.add_pipeline(
        "proj=pipeline step proj=vgridshift grids=core\\geoid12b\\g2012bu0.gtx step proj=vgridshift grids=REGION\\tss.gtx",
        "TXlagmat01_8301")

    cstwo = VerticalPipelineCRS(vdatum_version_string='vdatum_4.1.2', vert_datum_name="some_bs")
    cstwo.add_pipeline(
        "proj=pipeline step proj=vgridshift grids=core\\geoid12b\\g2012bu0.gtx step proj=vgridshift grids=REGION\\tss.gtx step proj=vgridshift grids=REGION\\mllw.gtx",
        "TXlaggal01_8301")

    try:
        pipe = get_transformation_pipeline(cs, cstwo, "TXlagmat01_8301", 'vdatum_4.1.2')
        assert False
    except NotImplementedError:  # name specified in cstwo was not in the datum definition dictionary
        assert True


def test_vyperpipeline_add_vertcrs_no_pipeline():
    # test adding a vertical crs from a vyperdatum datum definition 
    cs = VyperPipelineCRS(vdatum_version_string='vdatum_4.1.2')
    cs.set_crs("NOAA Chart Datum")
    assert cs.horizontal is None
    assert not cs.is_valid
    assert cs.to_wkt() is None
    assert cs.vertical is None
    assert cs._vert.to_wkt() == 'VERTCRS["NOAA Chart Datum",VDATUM["NOAA Chart Datum"],CS[vertical,1],AXIS["gravity-related height (H)",up,LENGTHUNIT["metre",1]]]'


def test_vyperpipeline_add_vertcrs_with_pipeline():
    # test adding a vertical crs from a vyperdatum datum definition with two regions
    cs = VyperPipelineCRS(vdatum_version_string='vdatum_4.1.2')
    cs.set_crs("NOAA Chart Datum", ['TXlagmat01_8301', 'TXlaggal01_8301'])
    assert cs.horizontal is None
    assert not cs.is_valid
    assert cs.to_wkt() is None

    expected_wkt = 'VERTCRS["NOAA Chart Datum",VDATUM["NOAA Chart Datum"],CS[vertical,1],AXIS["gravity-related height (H)",up,LENGTHUNIT["metre",1]],'
    base_wkt, vdatversion, version, base_datum, pipeline_data, regions_data = split_wkt_remarks(cs.vertical.to_wkt())
    assert expected_wkt == base_wkt
    assert version == __version__
    assert base_datum == 'NAD83(2011)'
    assert pipeline_data[0].find('TXlagmat01_8301') != -1
    assert pipeline_data[1].find('TXlaggal01_8301') != -1
    assert regions_data[0] == 'TXlagmat01_8301'
    assert regions_data[1] == 'TXlaggal01_8301'


def test_vyperpipeline_add_vertcrs_then_pipeline_then_pipeline():
    # test adding a vertical crs from a vyperdatum datum definition and then a region and then another
    cs = VyperPipelineCRS('vdatum_4.1.2')
    cs.set_crs("NOAA Chart Datum")
    cs.update_regions(['TXlagmat01_8301'])
    assert cs.horizontal is None
    assert not cs.is_valid
    assert cs.to_wkt() is None

    expected_wkt = 'VERTCRS["NOAA Chart Datum",VDATUM["NOAA Chart Datum"],CS[vertical,1],AXIS["gravity-related height (H)",up,LENGTHUNIT["metre",1]],'
    base_wkt, vdatversion, version, base_datum, pipeline_data, regions_data = split_wkt_remarks(cs.vertical.to_wkt())
    assert expected_wkt == base_wkt
    assert version == __version__
    assert base_datum == 'NAD83(2011)'
    assert pipeline_data[0].find('TXlagmat01_8301') != -1
    assert regions_data[0] == 'TXlagmat01_8301'


def test_vyperpipeline_add_vertcrs_wkt_then_pipeline_then_pipeline():
    # test adding a vertical crs from wkt definition and then a region
    cs = VyperPipelineCRS('vdatum_4.1.2')
    vert_wkt = 'VERTCRS["NOAA Chart Datum",VDATUM["NOAA Chart Datum"],CS[vertical,1],AXIS["gravity-related height (H)",up,LENGTHUNIT["metre",1]]]'
    cs.set_crs(vert_wkt)
    cs.update_regions(['TXlagmat01_8301'])
    assert cs.horizontal is None
    assert not cs.is_valid
    assert cs.to_wkt() is None

    expected_wkt = 'VERTCRS["NOAA Chart Datum",VDATUM["NOAA Chart Datum"],CS[vertical,1],AXIS["gravity-related height (H)",up,LENGTHUNIT["metre",1]],'
    base_wkt, vdatversion, version, base_datum, pipeline_data, regions_data = split_wkt_remarks(cs.vertical.to_wkt())
    assert expected_wkt == base_wkt
    assert regions_data[0] == 'TXlagmat01_8301'
    assert pipeline_data == ['+proj=pipeline +step +proj=vgridshift grids=core\\geoid12b\\g2012bu0.gtx +step +inv +proj=vgridshift grids=TXlagmat01_8301\\tss.gtx +step +proj=vgridshift grids=TXlagmat01_8301\\mllw.gtx']


def test_vyperpipeline_add_vertcrs_wkt_then_pipeline_then_horizcrs():
    # test adding a vertical crs and then a region and then a horizontal crs
    cs = VyperPipelineCRS('vdatum_4.1.2')
    vert_wkt = 'VERTCRS["NOAA Chart Datum",VDATUM["NOAA Chart Datum"],CS[vertical,1],AXIS["gravity-related height (H)",up,LENGTHUNIT["metre",1]]]'
    cs.set_crs(vert_wkt)
    cs.update_regions(['TXlagmat01_8301'])
    cs.set_crs(26914)
    assert cs.horizontal.to_wkt() == 'PROJCRS["NAD83 / UTM zone 14N",BASEGEOGCRS["NAD83",DATUM["North American Datum 1983",ELLIPSOID["GRS 1980",6378137,298.257222101,LENGTHUNIT["metre",1]]],PRIMEM["Greenwich",0,ANGLEUNIT["degree",0.0174532925199433]],ID["EPSG",4269]],CONVERSION["UTM zone 14N",METHOD["Transverse Mercator",ID["EPSG",9807]],PARAMETER["Latitude of natural origin",0,ANGLEUNIT["degree",0.0174532925199433],ID["EPSG",8801]],PARAMETER["Longitude of natural origin",-99,ANGLEUNIT["degree",0.0174532925199433],ID["EPSG",8802]],PARAMETER["Scale factor at natural origin",0.9996,SCALEUNIT["unity",1],ID["EPSG",8805]],PARAMETER["False easting",500000,LENGTHUNIT["metre",1],ID["EPSG",8806]],PARAMETER["False northing",0,LENGTHUNIT["metre",1],ID["EPSG",8807]]],CS[Cartesian,2],AXIS["(E)",east,ORDER[1],LENGTHUNIT["metre",1]],AXIS["(N)",north,ORDER[2],LENGTHUNIT["metre",1]],USAGE[SCOPE["Engineering survey, topographic mapping."],AREA["North America - between 102°W and 96°W - onshore and offshore. Canada - Manitoba; Nunavut; Saskatchewan. United States (USA) - Iowa; Kansas; Minnesota; Nebraska; North Dakota; Oklahoma; South Dakota; Texas."],BBOX[25.83,-102,84,-96]],ID["EPSG",26914]]'
    assert cs.is_valid

    expected_wkt = 'COMPOUNDCRS["NAD83 / UTM zone 14N + NOAA Chart Datum",PROJCRS["NAD83 / UTM zone 14N",BASEGEOGCRS["NAD83",DATUM["North American Datum 1983",ELLIPSOID["GRS 1980",6378137,298.257222101,LENGTHUNIT["metre",1]]],PRIMEM["Greenwich",0,ANGLEUNIT["degree",0.0174532925199433]],ID["EPSG",4269]],CONVERSION["UTM zone 14N",METHOD["Transverse Mercator",ID["EPSG",9807]],PARAMETER["Latitude of natural origin",0,ANGLEUNIT["degree",0.0174532925199433],ID["EPSG",8801]],PARAMETER["Longitude of natural origin",-99,ANGLEUNIT["degree",0.0174532925199433],ID["EPSG",8802]],PARAMETER["Scale factor at natural origin",0.9996,SCALEUNIT["unity",1],ID["EPSG",8805]],PARAMETER["False easting",500000,LENGTHUNIT["metre",1],ID["EPSG",8806]],PARAMETER["False northing",0,LENGTHUNIT["metre",1],ID["EPSG",8807]]],CS[Cartesian,2],AXIS["(E)",east,ORDER[1],LENGTHUNIT["metre",1]],AXIS["(N)",north,ORDER[2],LENGTHUNIT["metre",1]],USAGE[SCOPE["Engineering survey, topographic mapping."],AREA["North America - between 102°W and 96°W - onshore and offshore. Canada - Manitoba; Nunavut; Saskatchewan. United States (USA) - Iowa; Kansas; Minnesota; Nebraska; North Dakota; Oklahoma; South Dakota; Texas."],BBOX[25.83,-102,84,-96]],ID["EPSG",26914]],VERTCRS["NOAA Chart Datum",VDATUM["NOAA Chart Datum"],CS[vertical,1],AXIS["gravity-related height (H)",up,LENGTHUNIT["metre",1,ID["EPSG",9001]]],'
    base_wkt, vdatversion, version, base_datum, pipeline_data, regions_data = split_wkt_remarks(cs.to_wkt())
    assert expected_wkt == base_wkt
    assert regions_data[0] == 'TXlagmat01_8301'
    assert pipeline_data == ['+proj=pipeline +step +proj=vgridshift grids=core\\geoid12b\\g2012bu0.gtx +step +inv +proj=vgridshift grids=TXlagmat01_8301\\tss.gtx +step +proj=vgridshift grids=TXlagmat01_8301\\mllw.gtx']


def test_vyperpipeline_add_horizcrs_epsg_then_vertcrs():
    # test adding a horizontal and then a vertical crs
    cs = VyperPipelineCRS('vdatum_4.1.2')
    vert_wkt = 'VERTCRS["NOAA Chart Datum",VDATUM["NOAA Chart Datum"],CS[vertical,1],AXIS["gravity-related height (H)",up,LENGTHUNIT["metre",1]]]'
    cs.set_crs(26914)
    cs.set_crs(vert_wkt)
    assert cs.horizontal.to_wkt() == 'PROJCRS["NAD83 / UTM zone 14N",BASEGEOGCRS["NAD83",DATUM["North American Datum 1983",ELLIPSOID["GRS 1980",6378137,298.257222101,LENGTHUNIT["metre",1]]],PRIMEM["Greenwich",0,ANGLEUNIT["degree",0.0174532925199433]],ID["EPSG",4269]],CONVERSION["UTM zone 14N",METHOD["Transverse Mercator",ID["EPSG",9807]],PARAMETER["Latitude of natural origin",0,ANGLEUNIT["degree",0.0174532925199433],ID["EPSG",8801]],PARAMETER["Longitude of natural origin",-99,ANGLEUNIT["degree",0.0174532925199433],ID["EPSG",8802]],PARAMETER["Scale factor at natural origin",0.9996,SCALEUNIT["unity",1],ID["EPSG",8805]],PARAMETER["False easting",500000,LENGTHUNIT["metre",1],ID["EPSG",8806]],PARAMETER["False northing",0,LENGTHUNIT["metre",1],ID["EPSG",8807]]],CS[Cartesian,2],AXIS["(E)",east,ORDER[1],LENGTHUNIT["metre",1]],AXIS["(N)",north,ORDER[2],LENGTHUNIT["metre",1]],USAGE[SCOPE["Engineering survey, topographic mapping."],AREA["North America - between 102°W and 96°W - onshore and offshore. Canada - Manitoba; Nunavut; Saskatchewan. United States (USA) - Iowa; Kansas; Minnesota; Nebraska; North Dakota; Oklahoma; South Dakota; Texas."],BBOX[25.83,-102,84,-96]],ID["EPSG",26914]]'
    assert not cs.is_valid
    assert cs.to_wkt() is None


def test_vyperpipeline_with_horizcrs_and_vertcrs_and_region():
    # test adding a horizontal and vertical crs with region
    cs = VyperPipelineCRS('vdatum_4.1.2')
    vert_wkt = 'VERTCRS["NOAA Chart Datum",VDATUM["NOAA Chart Datum"],CS[vertical,1],AXIS["gravity-related height (H)",up,LENGTHUNIT["metre",1]]]'
    cs.set_crs((26914, vert_wkt), ['TXlagmat01_8301', 'TXlaggal01_8301'])
    assert cs.horizontal.to_wkt() == 'PROJCRS["NAD83 / UTM zone 14N",BASEGEOGCRS["NAD83",DATUM["North American Datum 1983",ELLIPSOID["GRS 1980",6378137,298.257222101,LENGTHUNIT["metre",1]]],PRIMEM["Greenwich",0,ANGLEUNIT["degree",0.0174532925199433]],ID["EPSG",4269]],CONVERSION["UTM zone 14N",METHOD["Transverse Mercator",ID["EPSG",9807]],PARAMETER["Latitude of natural origin",0,ANGLEUNIT["degree",0.0174532925199433],ID["EPSG",8801]],PARAMETER["Longitude of natural origin",-99,ANGLEUNIT["degree",0.0174532925199433],ID["EPSG",8802]],PARAMETER["Scale factor at natural origin",0.9996,SCALEUNIT["unity",1],ID["EPSG",8805]],PARAMETER["False easting",500000,LENGTHUNIT["metre",1],ID["EPSG",8806]],PARAMETER["False northing",0,LENGTHUNIT["metre",1],ID["EPSG",8807]]],CS[Cartesian,2],AXIS["(E)",east,ORDER[1],LENGTHUNIT["metre",1]],AXIS["(N)",north,ORDER[2],LENGTHUNIT["metre",1]],USAGE[SCOPE["Engineering survey, topographic mapping."],AREA["North America - between 102°W and 96°W - onshore and offshore. Canada - Manitoba; Nunavut; Saskatchewan. United States (USA) - Iowa; Kansas; Minnesota; Nebraska; North Dakota; Oklahoma; South Dakota; Texas."],BBOX[25.83,-102,84,-96]],ID["EPSG",26914]]'
    assert cs.is_valid


def test_vyperpipeline_with_horizcrs_and_vertcrs_and_region_in_wkt():
    # test adding a horizontal and vertical crs with region in the vertical wkt
    cs = VyperPipelineCRS('vdatum_4.1.2')
    vert_wkt = 'VERTCRS["NOAA Chart Datum",VDATUM["NOAA Chart Datum"],CS[vertical,1],AXIS["gravity-related height (H)",up,LENGTHUNIT["metre",1,ID["EPSG",9001]]],REMARK["vdatum=vdatum_4.2,vyperdatum=0.1.4,base_datum=NAD83,regions=[TXlagmat01_8301,TXlaggal01_8301],pipelines=[+proj=pipeline +step +proj=vgridshift grids=core\\geoid12b\\g2012bu0.gtx +step +inv +proj=vgridshift grids=TXlagmat01_8301\\tss.gtx +step +proj=vgridshift grids=TXlagmat01_8301\\mllw.gtx;+proj=pipeline +step +proj=vgridshift grids=core\\geoid12b\\g2012bu0.gtx +step +inv +proj=vgridshift grids=TXlaggal01_8301\\tss.gtx +step +proj=vgridshift grids=TXlaggal01_8301\\mllw.gtx]"]]'
    cs.set_crs((26914, vert_wkt))
    assert cs.is_valid

    base_wkt, vdatversion, version, base_datum, pipeline_data, regions_data = split_wkt_remarks(cs.to_wkt())
    assert version == __version__
    assert base_datum == 'NAD83(2011)'
    assert pipeline_data[0].find('TXlagmat01_8301') != -1
    assert pipeline_data[1].find('TXlaggal01_8301') != -1
    assert regions_data[0] == 'TXlagmat01_8301'
    assert regions_data[1] == 'TXlaggal01_8301'


def test_vyperpipeline_with_horizcrs_and_vertcrs_and_region_in_wkt_change_horizcrs():
    # test adding a horizontal and vertical crs with region in the vertical wkt, and then updating the horizontal crs simulating an override condition
    cs = VyperPipelineCRS('vdatum_4.1.2')
    vert_wkt = 'VERTCRS["NOAA Chart Datum",VDATUM["NOAA Chart Datum"],CS[vertical,1],AXIS["gravity-related height (H)",up,LENGTHUNIT["metre",1,ID["EPSG",9001]]],REMARK["vdatum=vdatum_4.2,vyperdatum=0.1.4,base_datum=NAD83,regions=[TXlagmat01_8301,TXlaggal01_8301],pipelines=[+proj=pipeline +step +proj=vgridshift grids=core\\geoid12b\\g2012bu0.gtx +step +inv +proj=vgridshift grids=TXlagmat01_8301\\tss.gtx +step +proj=vgridshift grids=TXlagmat01_8301\\mllw.gtx;+proj=pipeline +step +proj=vgridshift grids=core\\geoid12b\\g2012bu0.gtx +step +inv +proj=vgridshift grids=TXlaggal01_8301\\tss.gtx +step +proj=vgridshift grids=TXlaggal01_8301\\mllw.gtx]"]]'
    cs.set_crs((26914, vert_wkt))
    cs.set_crs(26915)
    assert cs.is_valid
    assert cs.vyperdatum_str == 'noaa chart datum'

    expected_wkt = 'COMPOUNDCRS["NAD83 / UTM zone 15N + NOAA Chart Datum",PROJCRS["NAD83 / UTM zone 15N",BASEGEOGCRS["NAD83",DATUM["North American Datum 1983",ELLIPSOID["GRS 1980",6378137,298.257222101,LENGTHUNIT["metre",1]]],PRIMEM["Greenwich",0,ANGLEUNIT["degree",0.0174532925199433]],ID["EPSG",4269]],CONVERSION["UTM zone 15N",METHOD["Transverse Mercator",ID["EPSG",9807]],PARAMETER["Latitude of natural origin",0,ANGLEUNIT["degree",0.0174532925199433],ID["EPSG",8801]],PARAMETER["Longitude of natural origin",-93,ANGLEUNIT["degree",0.0174532925199433],ID["EPSG",8802]],PARAMETER["Scale factor at natural origin",0.9996,SCALEUNIT["unity",1],ID["EPSG",8805]],PARAMETER["False easting",500000,LENGTHUNIT["metre",1],ID["EPSG",8806]],PARAMETER["False northing",0,LENGTHUNIT["metre",1],ID["EPSG",8807]]],CS[Cartesian,2],AXIS["(E)",east,ORDER[1],LENGTHUNIT["metre",1]],AXIS["(N)",north,ORDER[2],LENGTHUNIT["metre",1]],USAGE[SCOPE["Engineering survey, topographic mapping."],AREA["North America - between 96°W and 90°W - onshore and offshore. Canada - Manitoba; Nunavut; Ontario. United States (USA) - Arkansas; Illinois; Iowa; Kansas; Louisiana; Michigan; Minnesota; Mississippi; Missouri; Nebraska; Oklahoma; Tennessee; Texas; Wisconsin."],BBOX[25.61,-96,84,-90]],ID["EPSG",26915]],VERTCRS["NOAA Chart Datum",VDATUM["NOAA Chart Datum"],CS[vertical,1],AXIS["gravity-related height (H)",up,LENGTHUNIT["metre",1,ID["EPSG",9001]]],'
    base_wkt, vdatversion, version, base_datum, pipeline_data, regions_data = split_wkt_remarks(cs.to_wkt())
    assert version == __version__
    assert base_datum == 'NAD83(2011)'
    assert expected_wkt == base_wkt
    assert pipeline_data[0].find('TXlagmat01_8301') != -1
    assert pipeline_data[1].find('TXlaggal01_8301') != -1
    assert regions_data[0] == 'TXlagmat01_8301'
    assert regions_data[1] == 'TXlaggal01_8301'


def test_vyperpipeline_with_compound_wkt_no_region():
    # test adding a compound crs without region in the vertical wkt
    cs = VyperPipelineCRS('vdatum_4.1.2')
    compound_wkt = 'COMPOUNDCRS["NAD83 / UTM zone 15N + NOAA Chart Datum",PROJCRS["NAD83 / UTM zone 15N",BASEGEOGCRS["NAD83",DATUM["North American Datum 1983",ELLIPSOID["GRS 1980",6378137,298.257222101,LENGTHUNIT["metre",1]]],PRIMEM["Greenwich",0,ANGLEUNIT["degree",0.0174532925199433]],ID["EPSG",4269]],CONVERSION["UTM zone 15N",METHOD["Transverse Mercator",ID["EPSG",9807]],PARAMETER["Latitude of natural origin",0,ANGLEUNIT["degree",0.0174532925199433],ID["EPSG",8801]],PARAMETER["Longitude of natural origin",-93,ANGLEUNIT["degree",0.0174532925199433],ID["EPSG",8802]],PARAMETER["Scale factor at natural origin",0.9996,SCALEUNIT["unity",1],ID["EPSG",8805]],PARAMETER["False easting",500000,LENGTHUNIT["metre",1],ID["EPSG",8806]],PARAMETER["False northing",0,LENGTHUNIT["metre",1],ID["EPSG",8807]]],CS[Cartesian,2],AXIS["(E)",east,ORDER[1],LENGTHUNIT["metre",1]],AXIS["(N)",north,ORDER[2],LENGTHUNIT["metre",1]],USAGE[SCOPE["Engineering survey, topographic mapping."],AREA["North America - between 96°W and 90°W - onshore and offshore. Canada - Manitoba; Nunavut; Ontario. United States (USA) - Arkansas; Illinois; Iowa; Kansas; Louisiana; Michigan; Minnesota; Mississippi; Missouri; Nebraska; Oklahoma; Tennessee; Texas; Wisconsin."],BBOX[25.61,-96,84,-90]],ID["EPSG",26915]],VERTCRS["NOAA Chart Datum",VDATUM["NOAA Chart Datum"],CS[vertical,1],AXIS["gravity-related height (H)",up,LENGTHUNIT["metre",1,ID["EPSG",9001]]]]]'
    cs.set_crs(compound_wkt)
    assert cs.horizontal.to_epsg() == 26915
    assert cs.vertical is None
    assert not cs.is_valid
    assert cs.vyperdatum_str is None


def test_vyperpipeline_with_compound_wkt_with_region():
    # test adding a compound crs with the region in the vertical wkt
    cs = VyperPipelineCRS('vdatum_4.1.2')
    compound_wkt = 'COMPOUNDCRS["NAD83 / UTM zone 15N + NOAA Chart Datum",PROJCRS["NAD83 / UTM zone 15N",BASEGEOGCRS["NAD83",DATUM["North American Datum 1983",ELLIPSOID["GRS 1980",6378137,298.257222101,LENGTHUNIT["metre",1]]],PRIMEM["Greenwich",0,ANGLEUNIT["degree",0.0174532925199433]],ID["EPSG",4269]],CONVERSION["UTM zone 15N",METHOD["Transverse Mercator",ID["EPSG",9807]],PARAMETER["Latitude of natural origin",0,ANGLEUNIT["degree",0.0174532925199433],ID["EPSG",8801]],PARAMETER["Longitude of natural origin",-93,ANGLEUNIT["degree",0.0174532925199433],ID["EPSG",8802]],PARAMETER["Scale factor at natural origin",0.9996,SCALEUNIT["unity",1],ID["EPSG",8805]],PARAMETER["False easting",500000,LENGTHUNIT["metre",1],ID["EPSG",8806]],PARAMETER["False northing",0,LENGTHUNIT["metre",1],ID["EPSG",8807]]],CS[Cartesian,2],AXIS["(E)",east,ORDER[1],LENGTHUNIT["metre",1]],AXIS["(N)",north,ORDER[2],LENGTHUNIT["metre",1]],USAGE[SCOPE["Engineering survey, topographic mapping."],AREA["North America - between 96°W and 90°W - onshore and offshore. Canada - Manitoba; Nunavut; Ontario. United States (USA) - Arkansas; Illinois; Iowa; Kansas; Louisiana; Michigan; Minnesota; Mississippi; Missouri; Nebraska; Oklahoma; Tennessee; Texas; Wisconsin."],BBOX[25.61,-96,84,-90]],ID["EPSG",26915]],VERTCRS["NOAA Chart Datum",VDATUM["NOAA Chart Datum"],CS[vertical,1],AXIS["gravity-related height (H)",up,LENGTHUNIT["metre",1,ID["EPSG",9001]]],REMARK["vdatum=vdatum_4.2,vyperdatum=0.1.4,base_datum=NAD83,regions=[TXlagmat01_8301,TXlaggal01_8301],pipelines=[+proj=pipeline +step +proj=vgridshift grids=core\\geoid12b\\g2012bu0.gtx +step +inv +proj=vgridshift grids=TXlagmat01_8301\\tss.gtx +step +proj=vgridshift grids=TXlagmat01_8301\\mllw.gtx;+proj=pipeline +step +proj=vgridshift grids=core\\geoid12b\\g2012bu0.gtx +step +inv +proj=vgridshift grids=TXlaggal01_8301\\tss.gtx +step +proj=vgridshift grids=TXlaggal01_8301\\mllw.gtx]"]]]'
    cs.set_crs(compound_wkt)
    assert cs.horizontal.to_epsg() == 26915
    expected_wkt = 'VERTCRS["NOAA Chart Datum",VDATUM["NOAA Chart Datum"],CS[vertical,1],AXIS["gravity-related height (H)",up,LENGTHUNIT["metre",1]],'
    base_wkt, vdatversion, version, base_datum, pipeline_data, regions_data = split_wkt_remarks(cs.vertical.to_wkt())
    assert expected_wkt == base_wkt
    assert cs.is_valid
    assert cs.vyperdatum_str == 'noaa chart datum'


def test_vyperpipeline_with_compound_wkt_add_region():
    # test adding a compound crs with no region and then the region
    cs = VyperPipelineCRS('vdatum_4.1.2')
    compound_wkt = 'COMPD_CS["NAD83 / UTM zone 18N + NOAA Chart Datum",PROJCS["NAD83 / UTM zone 18N",GEOGCS["NAD83",DATUM["North_American_Datum_1983",SPHEROID["GRS 1980",6378137,298.257222101,AUTHORITY["EPSG","7019"]],AUTHORITY["EPSG","6269"]],PRIMEM["Greenwich",0,AUTHORITY["EPSG","8901"]],UNIT["degree",0.0174532925199433,AUTHORITY["EPSG","9122"]],AUTHORITY["EPSG","4269"]],PROJECTION["Transverse_Mercator"],PARAMETER["latitude_of_origin",0],PARAMETER["central_meridian",-75],PARAMETER["scale_factor",0.9996],PARAMETER["false_easting",500000],PARAMETER["false_northing",0],UNIT["metre",1,AUTHORITY["EPSG","9001"]],AXIS["Easting",EAST],AXIS["Northing",NORTH],AUTHORITY["EPSG","26918"]],VERT_CS["NOAA Chart Datum",VERT_DATUM["NOAA Chart Datum",2005,AUTHORITY["EPSG","1089"]],UNIT["metre",1,AUTHORITY["EPSG","9001"]],AXIS["Depth",DOWN],AUTHORITY["EPSG","5866"]]]'
    cs.set_crs(compound_wkt)
    assert cs.horizontal.to_epsg() == 26918
    assert not cs.is_valid
    assert cs.vertical is None
    cs.update_regions(['MENHMAgome23_8301'])
    assert cs.is_valid

    expected_wkt = 'VERTCRS["NOAA Chart Datum",VDATUM["NOAA Chart Datum"],CS[vertical,1],AXIS["depth (D)",down,LENGTHUNIT["metre",1]],'
    base_wkt, vdatversion, version, base_datum, pipeline_data, regions_data = split_wkt_remarks(cs.vertical.to_wkt())
    assert expected_wkt == base_wkt
    assert regions_data == ['MENHMAgome23_8301']
    assert pipeline_data == ['+proj=pipeline +step +proj=vgridshift grids=core\\geoid12b\\g2012bu0.gtx +step +inv +proj=vgridshift grids=MENHMAgome23_8301\\tss.gtx +step +proj=vgridshift grids=MENHMAgome23_8301\\mllw.gtx']
    assert cs.vyperdatum_str == 'noaa chart datum'
    assert not cs.is_height


def test_vyperpipeline_set_compound_wkt_on_instantiation():
    # test adding a compound crs wkt on instantiation of the object
    compound_wkt = 'COMPOUNDCRS["NAD83 / UTM zone 18N + NOAA Chart Datum",PROJCRS["NAD83 / UTM zone 18N",BASEGEOGCRS["NAD83",DATUM["North American Datum 1983",ELLIPSOID["GRS 1980",6378137,298.257222101,LENGTHUNIT["metre",1]]],PRIMEM["Greenwich",0,ANGLEUNIT["degree",0.0174532925199433]],ID["EPSG",4269]],CONVERSION["UTM zone 18N",METHOD["Transverse Mercator",ID["EPSG",9807]],PARAMETER["Latitude of natural origin",0,ANGLEUNIT["degree",0.0174532925199433],ID["EPSG",8801]],PARAMETER["Longitude of natural origin",-75,ANGLEUNIT["degree",0.0174532925199433],ID["EPSG",8802]],PARAMETER["Scale factor at natural origin",0.9996,SCALEUNIT["unity",1],ID["EPSG",8805]],PARAMETER["False easting",500000,LENGTHUNIT["metre",1],ID["EPSG",8806]],PARAMETER["False northing",0,LENGTHUNIT["metre",1],ID["EPSG",8807]]],CS[Cartesian,2],AXIS["easting",east,ORDER[1],LENGTHUNIT["metre",1]],AXIS["northing",north,ORDER[2],LENGTHUNIT["metre",1]],ID["EPSG",26918]],VERTCRS["MLLW depth",VDATUM["MLLW depth"],CS[vertical,1],AXIS["depth (D)",down,LENGTHUNIT["metre",1,ID["EPSG",9001]]],REMARK["vdatum=vdatum_4.2,vyperdatum=0.1.4,base_datum=NAD83,regions=[MENHMAgome23_8301],pipelines=[+proj=pipeline +step +proj=vgridshift grids=core\\geoid12b\\g2012bu0.gtx +step +inv +proj=vgridshift grids=MENHMAgome23_8301\\tss.gtx +step +proj=vgridshift grids=MENHMAgome23_8301\\mllw.gtx]"]]]'
    cs = VyperPipelineCRS('vdatum_4.1.2', new_crs=compound_wkt)
    assert cs.horizontal.to_epsg() == 26918
    assert cs.is_valid

    expected_wkt = 'VERTCRS["MLLW depth",VDATUM["MLLW depth"],CS[vertical,1],AXIS["depth (D)",down,LENGTHUNIT["metre",1]],'
    base_wkt, vdatversion, version, base_datum, pipeline_data, regions_data = split_wkt_remarks(cs.vertical.to_wkt())
    assert expected_wkt == base_wkt
    assert regions_data == ['MENHMAgome23_8301']
    assert pipeline_data == ['+proj=pipeline +step +proj=vgridshift grids=core\\geoid12b\\g2012bu0.gtx +step +inv +proj=vgridshift grids=MENHMAgome23_8301\\tss.gtx +step +proj=vgridshift grids=MENHMAgome23_8301\\mllw.gtx']
    assert cs.vyperdatum_str == 'mllw'
    assert not cs.is_height


def test_3d_to_compound():
    cs = VyperPipelineCRS('vdatum_4.1.2', new_crs=6319, regions=['MENHMAgome23_8301'])
    assert cs.is_valid

    expected_wkt = 'COMPOUNDCRS["NAD83(2011) + NAD83(2011)_ellipse",GEOGCRS["NAD83(2011)",DATUM["NAD83 (National Spatial Reference System 2011)",ELLIPSOID["GRS 1980",6378137,298.257222101,LENGTHUNIT["metre",1]]],PRIMEM["Greenwich",0,ANGLEUNIT["degree",0.0174532925199433]],CS[ellipsoidal,2],AXIS["geodetic latitude (Lat)",north,ORDER[1],ANGLEUNIT["degree",0.0174532925199433]],AXIS["geodetic longitude (Lon)",east,ORDER[2],ANGLEUNIT["degree",0.0174532925199433]],USAGE[SCOPE["Horizontal component of 3D system."],AREA["Puerto Rico - onshore and offshore. United States (USA) onshore and offshore - Alabama; Alaska; Arizona; Arkansas; California; Colorado; Connecticut; Delaware; Florida; Georgia; Idaho; Illinois; Indiana; Iowa; Kansas; Kentucky; Louisiana; Maine; Maryland; Massachusetts; Michigan; Minnesota; Mississippi; Missouri; Montana; Nebraska; Nevada; New Hampshire; New Jersey; New Mexico; New York; North Carolina; North Dakota; Ohio; Oklahoma; Oregon; Pennsylvania; Rhode Island; South Carolina; South Dakota; Tennessee; Texas; Utah; Vermont; Virginia; Washington; West Virginia; Wisconsin; Wyoming. US Virgin Islands - onshore and offshore."],BBOX[14.92,167.65,74.71,-63.88]],ID["EPSG",6318]],VERTCRS["NAD83(2011)_ellipse",VDATUM["NAD83(2011)_ellipse"],CS[vertical,1],AXIS["gravity-related height (H)",up,LENGTHUNIT["metre",1,ID["EPSG",9001]]],'
    base_wkt, vdatversion, version, base_datum, pipeline_data, regions_data = split_wkt_remarks(cs.to_wkt())
    assert expected_wkt == base_wkt
    assert regions_data == ['MENHMAgome23_8301']
    assert pipeline_data == ['[]']
    assert cs.vyperdatum_str == 'ellipse'
    assert cs.is_height


def test_crs_is_compound():
    assert not crs_is_compound(CRS.from_epsg(6318))
    assert not crs_is_compound(CRS.from_epsg(4326))
    assert not crs_is_compound(CRS.from_epsg(26918))
    assert not crs_is_compound(CRS.from_epsg(5866))
    compound_wkt = 'COMPOUNDCRS["NAD83 / UTM zone 15N + NOAA Chart Datum",PROJCRS["NAD83 / UTM zone 15N",BASEGEOGCRS["NAD83",DATUM["North American Datum 1983",ELLIPSOID["GRS 1980",6378137,298.257222101,LENGTHUNIT["metre",1]]],PRIMEM["Greenwich",0,ANGLEUNIT["degree",0.0174532925199433]],ID["EPSG",4269]],CONVERSION["UTM zone 15N",METHOD["Transverse Mercator",ID["EPSG",9807]],PARAMETER["Latitude of natural origin",0,ANGLEUNIT["degree",0.0174532925199433],ID["EPSG",8801]],PARAMETER["Longitude of natural origin",-93,ANGLEUNIT["degree",0.0174532925199433],ID["EPSG",8802]],PARAMETER["Scale factor at natural origin",0.9996,SCALEUNIT["unity",1],ID["EPSG",8805]],PARAMETER["False easting",500000,LENGTHUNIT["metre",1],ID["EPSG",8806]],PARAMETER["False northing",0,LENGTHUNIT["metre",1],ID["EPSG",8807]]],CS[Cartesian,2],AXIS["(E)",east,ORDER[1],LENGTHUNIT["metre",1]],AXIS["(N)",north,ORDER[2],LENGTHUNIT["metre",1]],USAGE[SCOPE["Engineering survey, topographic mapping."],AREA["North America - between 96°W and 90°W - onshore and offshore. Canada - Manitoba; Nunavut; Ontario. United States (USA) - Arkansas; Illinois; Iowa; Kansas; Louisiana; Michigan; Minnesota; Mississippi; Missouri; Nebraska; Oklahoma; Tennessee; Texas; Wisconsin."],BBOX[25.61,-96,84,-90]],ID["EPSG",26915]],VERTCRS["NOAA Chart Datum",VDATUM["NOAA Chart Datum"],CS[vertical,1],AXIS["gravity-related height (H)",up,LENGTHUNIT["metre",1,ID["EPSG",9001]]],REMARK["regions=[TXlagmat01_8301,TXlaggal01_8301],pipeline=+proj=pipeline +step +proj=vgridshift grids=core\\geoid12b\\g2012bu0.gtx +step +inv +proj=vgridshift grids=REGION\\tss.gtx +step +proj=vgridshift grids=REGION\\mllw.gtx"]]]'
    assert crs_is_compound(CRS.from_wkt(compound_wkt))


def split_wkt_remarks(wkt):
    base_wkt = ''
    version = ''
    vdatversion = ''
    base_datum = ''
    pipeline_data = []
    regions_data = []
    wkt_split = wkt.split('REMARK')
    if len(wkt_split) == 2:
        base_wkt, remarks = wkt_split
        start, content, end = remarks.split('"')
        for remark in content.split(','):
            if remark.startswith('vdatum='):
                vdatversion = remark[len('vatum='):]
            elif remark.startswith('vyperdatum='):
                version = remark[len('vyperdatum='):]
            elif remark.startswith('base_datum='):
                base_datum = remark[len('base_datum='):]
            elif remark.startswith('pipelines='):
                pipeline_start = content.find('pipelines=')
                strt = pipeline_start + len('pipelines=') + 1
                pipeline_end = content.find('],', strt)
                pipeline_data = content[strt:pipeline_end].split(';')
            elif remark.startswith('regions='):
                regions_start = content.find('regions=')
                strt = regions_start + len('regions=') + 1
                regions_end = content.find('],', strt)
                regions_data = content[strt:regions_end].split(',')

    return base_wkt, vdatversion, version, base_datum, pipeline_data, regions_data


if __name__ == '__main__':
    test_derived_parameter_file()
    test_transformation_inv_nad83()
    test_transformation_noregion()
    test_transformation_tss()
    test_transformation_unsupported_name()
    test_vertical_derived_crs()
    test_vertical_pipeline_crs()
