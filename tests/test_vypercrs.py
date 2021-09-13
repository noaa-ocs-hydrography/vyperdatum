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
    assert pipe == '+proj=pipeline +step +inv +proj=vgridshift grids=TXlaggal01_8301\\mllw.gtx ' \
                   '+step +proj=vgridshift grids=TXlaggal01_8301\\tss.gtx ' \
                   '+step +inv +proj=vgridshift grids=core\\geoid12b\\g2012bu0.gtx'


def test_transformation_tss():
    cs = VerticalPipelineCRS("tss")
    cs.add_pipeline("proj=pipeline step proj=vgridshift grids=core\\geoid12b\\g2012bu0.gtx step proj=vgridshift grids=REGION\\tss.gtx",
                    "TXlagmat01_8301")

    cstwo = VerticalPipelineCRS("mllw")
    cstwo.add_pipeline("proj=pipeline step proj=vgridshift grids=core\\geoid12b\\g2012bu0.gtx step proj=vgridshift grids=REGION\\tss.gtx step proj=vgridshift grids=REGION\\mllw.gtx",
                       "TXlagmat01_8301")

    pipe = get_transformation_pipeline(cs, cstwo, "TXlagmat01_8301")
    assert pipe == '+proj=pipeline +step +proj=vgridshift grids=TXlagmat01_8301\\mllw.gtx'


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
        
def test_vyperpipeline_add_vertcrs_no_pipeline():
    # test adding a vertical crs from a vyperdatum datum definition 
    cs = VyperPipelineCRS()
    cs.set_crs("NOAA Chart Datum")
    assert cs.horizontal == None
    assert cs.is_valid == False
    assert cs.to_wkt() == None
    assert cs.vertical == None
    assert cs._vert.to_wkt() == 'VERTCRS["NOAA Chart Datum",VDATUM["NOAA Chart Datum"],CS[vertical,1],AXIS["gravity-related height (H)",up,LENGTHUNIT["metre",1]]]'    
    
def test_vyperpipeline_add_vertcrs_with_pipeline():
    # test adding a vertical crs from a vyperdatum datum definition with two regions
    cs = VyperPipelineCRS()
    cs.set_crs("NOAA Chart Datum", ['TXlagmat01_8301', 'TXlaggal01_8301'])
    assert cs.horizontal == None
    assert cs.is_valid == False
    assert cs.to_wkt() == None
    assert cs.vertical.to_wkt() == 'VERTCRS["NOAA Chart Datum",VDATUM["NOAA Chart Datum"],CS[vertical,1],AXIS["gravity-related height (H)",up,LENGTHUNIT["metre",1]],REMARK["regions=[TXlagmat01_8301,TXlaggal01_8301],pipeline=+proj=pipeline +step +proj=vgridshift grids=core\\geoid12b\\g2012bu0.gtx +step +inv +proj=vgridshift grids=REGION\\tss.gtx +step +proj=vgridshift grids=REGION\\mllw.gtx"]]'
    
def test_vyperpipeline_add_vertcrs_then_pipeline_then_pipeline():
    # test adding a vertical crs from a vyperdatum datum definition and then a region and then another
    cs = VyperPipelineCRS()
    cs.set_crs("NOAA Chart Datum")
    cs.update_regions(['TXlagmat01_8301'])
    assert cs.horizontal == None
    assert cs.is_valid == False
    assert cs.to_wkt() == None
    assert cs.vertical.to_wkt() == 'VERTCRS["NOAA Chart Datum",VDATUM["NOAA Chart Datum"],CS[vertical,1],AXIS["gravity-related height (H)",up,LENGTHUNIT["metre",1]],REMARK["regions=[TXlagmat01_8301],pipeline=+proj=pipeline +step +proj=vgridshift grids=core\\geoid12b\\g2012bu0.gtx +step +inv +proj=vgridshift grids=REGION\\tss.gtx +step +proj=vgridshift grids=REGION\\mllw.gtx"]]'
    cs.update_regions(['TXlaggal01_8301'])
    assert cs.vertical.to_wkt() == 'VERTCRS["NOAA Chart Datum",VDATUM["NOAA Chart Datum"],CS[vertical,1],AXIS["gravity-related height (H)",up,LENGTHUNIT["metre",1]],REMARK["regions=[TXlagmat01_8301,TXlaggal01_8301],pipeline=+proj=pipeline +step +proj=vgridshift grids=core\\geoid12b\\g2012bu0.gtx +step +inv +proj=vgridshift grids=REGION\\tss.gtx +step +proj=vgridshift grids=REGION\\mllw.gtx"]]'
    
def test_vyperpipeline_add_vertcrs_wkt_then_pipeline_then_pipeline():
    # test adding a vertical crs from wkt definition and then a region
    cs = VyperPipelineCRS()
    vert_wkt = 'VERTCRS["NOAA Chart Datum",VDATUM["NOAA Chart Datum"],CS[vertical,1],AXIS["gravity-related height (H)",up,LENGTHUNIT["metre",1]]]'
    cs.set_crs(vert_wkt)
    cs.update_regions(['TXlagmat01_8301'])
    assert cs.horizontal == None
    assert cs.is_valid == False
    assert cs.to_wkt() == None
    assert cs.vertical.to_wkt() == 'VERTCRS["NOAA Chart Datum",VDATUM["NOAA Chart Datum"],CS[vertical,1],AXIS["gravity-related height (H)",up,LENGTHUNIT["metre",1]],REMARK["regions=[TXlagmat01_8301],pipeline=+proj=pipeline +step +proj=vgridshift grids=core\\geoid12b\\g2012bu0.gtx +step +inv +proj=vgridshift grids=REGION\\tss.gtx +step +proj=vgridshift grids=REGION\\mllw.gtx"]]'
    
def test_vyperpipeline_add_vertcrs_wkt_then_pipeline_then_horizcrs():
    # test adding a vertical crs and then a region and then a horizontal crs
    cs = VyperPipelineCRS()
    vert_wkt = 'VERTCRS["NOAA Chart Datum",VDATUM["NOAA Chart Datum"],CS[vertical,1],AXIS["gravity-related height (H)",up,LENGTHUNIT["metre",1]]]'
    cs.set_crs(vert_wkt)
    cs.update_regions(['TXlagmat01_8301'])
    cs.set_crs(26914)
    assert cs.horizontal.to_wkt() == 'PROJCRS["NAD83 / UTM zone 14N",BASEGEOGCRS["NAD83",DATUM["North American Datum 1983",ELLIPSOID["GRS 1980",6378137,298.257222101,LENGTHUNIT["metre",1]]],PRIMEM["Greenwich",0,ANGLEUNIT["degree",0.0174532925199433]],ID["EPSG",4269]],CONVERSION["UTM zone 14N",METHOD["Transverse Mercator",ID["EPSG",9807]],PARAMETER["Latitude of natural origin",0,ANGLEUNIT["degree",0.0174532925199433],ID["EPSG",8801]],PARAMETER["Longitude of natural origin",-99,ANGLEUNIT["degree",0.0174532925199433],ID["EPSG",8802]],PARAMETER["Scale factor at natural origin",0.9996,SCALEUNIT["unity",1],ID["EPSG",8805]],PARAMETER["False easting",500000,LENGTHUNIT["metre",1],ID["EPSG",8806]],PARAMETER["False northing",0,LENGTHUNIT["metre",1],ID["EPSG",8807]]],CS[Cartesian,2],AXIS["(E)",east,ORDER[1],LENGTHUNIT["metre",1]],AXIS["(N)",north,ORDER[2],LENGTHUNIT["metre",1]],USAGE[SCOPE["Engineering survey, topographic mapping."],AREA["North America - between 102°W and 96°W - onshore and offshore. Canada - Manitoba; Nunavut; Saskatchewan. United States (USA) - Iowa; Kansas; Minnesota; Nebraska; North Dakota; Oklahoma; South Dakota; Texas."],BBOX[25.83,-102,84,-96]],ID["EPSG",26914]]'
    assert cs.is_valid == True
    assert cs.to_wkt() == 'COMPOUNDCRS["NAD83 / UTM zone 14N + NOAA Chart Datum",PROJCRS["NAD83 / UTM zone 14N",BASEGEOGCRS["NAD83",DATUM["North American Datum 1983",ELLIPSOID["GRS 1980",6378137,298.257222101,LENGTHUNIT["metre",1]]],PRIMEM["Greenwich",0,ANGLEUNIT["degree",0.0174532925199433]],ID["EPSG",4269]],CONVERSION["UTM zone 14N",METHOD["Transverse Mercator",ID["EPSG",9807]],PARAMETER["Latitude of natural origin",0,ANGLEUNIT["degree",0.0174532925199433],ID["EPSG",8801]],PARAMETER["Longitude of natural origin",-99,ANGLEUNIT["degree",0.0174532925199433],ID["EPSG",8802]],PARAMETER["Scale factor at natural origin",0.9996,SCALEUNIT["unity",1],ID["EPSG",8805]],PARAMETER["False easting",500000,LENGTHUNIT["metre",1],ID["EPSG",8806]],PARAMETER["False northing",0,LENGTHUNIT["metre",1],ID["EPSG",8807]]],CS[Cartesian,2],AXIS["(E)",east,ORDER[1],LENGTHUNIT["metre",1]],AXIS["(N)",north,ORDER[2],LENGTHUNIT["metre",1]],USAGE[SCOPE["Engineering survey, topographic mapping."],AREA["North America - between 102°W and 96°W - onshore and offshore. Canada - Manitoba; Nunavut; Saskatchewan. United States (USA) - Iowa; Kansas; Minnesota; Nebraska; North Dakota; Oklahoma; South Dakota; Texas."],BBOX[25.83,-102,84,-96]],ID["EPSG",26914]],VERTCRS["NOAA Chart Datum",VDATUM["NOAA Chart Datum"],CS[vertical,1],AXIS["gravity-related height (H)",up,LENGTHUNIT["metre",1,ID["EPSG",9001]]],REMARK["regions=[TXlagmat01_8301],pipeline=+proj=pipeline +step +proj=vgridshift grids=core\\geoid12b\\g2012bu0.gtx +step +inv +proj=vgridshift grids=REGION\\tss.gtx +step +proj=vgridshift grids=REGION\\mllw.gtx"]]]'

def test_vyperpipeline_add_horizcrs_epsg_then_vertcrs():
    # test adding a horizontal and then a vertical crs
    cs = VyperPipelineCRS()
    vert_wkt = 'VERTCRS["NOAA Chart Datum",VDATUM["NOAA Chart Datum"],CS[vertical,1],AXIS["gravity-related height (H)",up,LENGTHUNIT["metre",1]]]'
    cs.set_crs(26914)
    cs.set_crs(vert_wkt)
    assert cs.horizontal.to_wkt() == 'PROJCRS["NAD83 / UTM zone 14N",BASEGEOGCRS["NAD83",DATUM["North American Datum 1983",ELLIPSOID["GRS 1980",6378137,298.257222101,LENGTHUNIT["metre",1]]],PRIMEM["Greenwich",0,ANGLEUNIT["degree",0.0174532925199433]],ID["EPSG",4269]],CONVERSION["UTM zone 14N",METHOD["Transverse Mercator",ID["EPSG",9807]],PARAMETER["Latitude of natural origin",0,ANGLEUNIT["degree",0.0174532925199433],ID["EPSG",8801]],PARAMETER["Longitude of natural origin",-99,ANGLEUNIT["degree",0.0174532925199433],ID["EPSG",8802]],PARAMETER["Scale factor at natural origin",0.9996,SCALEUNIT["unity",1],ID["EPSG",8805]],PARAMETER["False easting",500000,LENGTHUNIT["metre",1],ID["EPSG",8806]],PARAMETER["False northing",0,LENGTHUNIT["metre",1],ID["EPSG",8807]]],CS[Cartesian,2],AXIS["(E)",east,ORDER[1],LENGTHUNIT["metre",1]],AXIS["(N)",north,ORDER[2],LENGTHUNIT["metre",1]],USAGE[SCOPE["Engineering survey, topographic mapping."],AREA["North America - between 102°W and 96°W - onshore and offshore. Canada - Manitoba; Nunavut; Saskatchewan. United States (USA) - Iowa; Kansas; Minnesota; Nebraska; North Dakota; Oklahoma; South Dakota; Texas."],BBOX[25.83,-102,84,-96]],ID["EPSG",26914]]'
    assert cs.is_valid == False
    assert cs.to_wkt() == None
    
def test_vyperpipeline_with_horizcrs_and_vertcrs_and_region():
    # test adding a horizontal and vertical crs with region
    cs = VyperPipelineCRS()
    vert_wkt = 'VERTCRS["NOAA Chart Datum",VDATUM["NOAA Chart Datum"],CS[vertical,1],AXIS["gravity-related height (H)",up,LENGTHUNIT["metre",1]]]'
    cs.set_crs((26914, vert_wkt), ['TXlagmat01_8301', 'TXlaggal01_8301'])
    assert cs.horizontal.to_wkt() == 'PROJCRS["NAD83 / UTM zone 14N",BASEGEOGCRS["NAD83",DATUM["North American Datum 1983",ELLIPSOID["GRS 1980",6378137,298.257222101,LENGTHUNIT["metre",1]]],PRIMEM["Greenwich",0,ANGLEUNIT["degree",0.0174532925199433]],ID["EPSG",4269]],CONVERSION["UTM zone 14N",METHOD["Transverse Mercator",ID["EPSG",9807]],PARAMETER["Latitude of natural origin",0,ANGLEUNIT["degree",0.0174532925199433],ID["EPSG",8801]],PARAMETER["Longitude of natural origin",-99,ANGLEUNIT["degree",0.0174532925199433],ID["EPSG",8802]],PARAMETER["Scale factor at natural origin",0.9996,SCALEUNIT["unity",1],ID["EPSG",8805]],PARAMETER["False easting",500000,LENGTHUNIT["metre",1],ID["EPSG",8806]],PARAMETER["False northing",0,LENGTHUNIT["metre",1],ID["EPSG",8807]]],CS[Cartesian,2],AXIS["(E)",east,ORDER[1],LENGTHUNIT["metre",1]],AXIS["(N)",north,ORDER[2],LENGTHUNIT["metre",1]],USAGE[SCOPE["Engineering survey, topographic mapping."],AREA["North America - between 102°W and 96°W - onshore and offshore. Canada - Manitoba; Nunavut; Saskatchewan. United States (USA) - Iowa; Kansas; Minnesota; Nebraska; North Dakota; Oklahoma; South Dakota; Texas."],BBOX[25.83,-102,84,-96]],ID["EPSG",26914]]'
    assert cs.is_valid == True
    
def test_vyperpipeline_with_horizcrs_and_vertcrs_and_region_in_wkt():
    # test adding a horizontal and vertical crs with region in the vertical wkt
    cs = VyperPipelineCRS()
    vert_wkt = 'VERTCRS["NOAA Chart Datum",VDATUM["NOAA Chart Datum"],CS[vertical,1],AXIS["gravity-related height (H)",up,LENGTHUNIT["metre",1]],REMARK["regions=[TXlagmat01_8301,TXlaggal01_8301],pipeline=+proj=pipeline +step +proj=vgridshift grids=core\\geoid12b\\g2012bu0.gtx +step +inv +proj=vgridshift grids=REGION\\tss.gtx +step +proj=vgridshift grids=REGION\\mllw.gtx"]]'
    cs.set_crs((26914, vert_wkt))
    assert cs.is_valid == True
    assert cs.regions == ['TXlagmat01_8301', 'TXlaggal01_8301']
    
def test_vyperpipeline_with_horizcrs_and_vertcrs_and_region_in_wkt_change_horizcrs():
    # test adding a horizontal and vertical crs with region in the vertical wkt, and then updating the horizontal crs simulating an override condition
    cs = VyperPipelineCRS()
    vert_wkt = 'VERTCRS["NOAA Chart Datum",VDATUM["NOAA Chart Datum"],CS[vertical,1],AXIS["gravity-related height (H)",up,LENGTHUNIT["metre",1]],REMARK["regions=[TXlagmat01_8301,TXlaggal01_8301],pipeline=+proj=pipeline +step +proj=vgridshift grids=core\\geoid12b\\g2012bu0.gtx +step +inv +proj=vgridshift grids=REGION\\tss.gtx +step +proj=vgridshift grids=REGION\\mllw.gtx"]]'
    cs.set_crs((26914, vert_wkt))
    cs.set_crs(26915)
    assert cs.is_valid == True
    assert cs.to_wkt() == 'COMPOUNDCRS["NAD83 / UTM zone 15N + NOAA Chart Datum",PROJCRS["NAD83 / UTM zone 15N",BASEGEOGCRS["NAD83",DATUM["North American Datum 1983",ELLIPSOID["GRS 1980",6378137,298.257222101,LENGTHUNIT["metre",1]]],PRIMEM["Greenwich",0,ANGLEUNIT["degree",0.0174532925199433]],ID["EPSG",4269]],CONVERSION["UTM zone 15N",METHOD["Transverse Mercator",ID["EPSG",9807]],PARAMETER["Latitude of natural origin",0,ANGLEUNIT["degree",0.0174532925199433],ID["EPSG",8801]],PARAMETER["Longitude of natural origin",-93,ANGLEUNIT["degree",0.0174532925199433],ID["EPSG",8802]],PARAMETER["Scale factor at natural origin",0.9996,SCALEUNIT["unity",1],ID["EPSG",8805]],PARAMETER["False easting",500000,LENGTHUNIT["metre",1],ID["EPSG",8806]],PARAMETER["False northing",0,LENGTHUNIT["metre",1],ID["EPSG",8807]]],CS[Cartesian,2],AXIS["(E)",east,ORDER[1],LENGTHUNIT["metre",1]],AXIS["(N)",north,ORDER[2],LENGTHUNIT["metre",1]],USAGE[SCOPE["Engineering survey, topographic mapping."],AREA["North America - between 96°W and 90°W - onshore and offshore. Canada - Manitoba; Nunavut; Ontario. United States (USA) - Arkansas; Illinois; Iowa; Kansas; Louisiana; Michigan; Minnesota; Mississippi; Missouri; Nebraska; Oklahoma; Tennessee; Texas; Wisconsin."],BBOX[25.61,-96,84,-90]],ID["EPSG",26915]],VERTCRS["NOAA Chart Datum",VDATUM["NOAA Chart Datum"],CS[vertical,1],AXIS["gravity-related height (H)",up,LENGTHUNIT["metre",1,ID["EPSG",9001]]],REMARK["regions=[TXlagmat01_8301,TXlaggal01_8301,TXlagmat01_8301,TXlaggal01_8301],pipeline=+proj=pipeline +step +proj=vgridshift grids=core\\geoid12b\\g2012bu0.gtx +step +inv +proj=vgridshift grids=REGION\\tss.gtx +step +proj=vgridshift grids=REGION\\mllw.gtx"]]]'
    assert cs.vyperdatum_str == 'noaa chart datum'
    
def test_vyperpipeline_with_compound_wkt_no_region():
    # test adding a compound crs without region in the vertical wkt
    cs = VyperPipelineCRS()
    compound_wkt = 'COMPOUNDCRS["NAD83 / UTM zone 15N + NOAA Chart Datum",PROJCRS["NAD83 / UTM zone 15N",BASEGEOGCRS["NAD83",DATUM["North American Datum 1983",ELLIPSOID["GRS 1980",6378137,298.257222101,LENGTHUNIT["metre",1]]],PRIMEM["Greenwich",0,ANGLEUNIT["degree",0.0174532925199433]],ID["EPSG",4269]],CONVERSION["UTM zone 15N",METHOD["Transverse Mercator",ID["EPSG",9807]],PARAMETER["Latitude of natural origin",0,ANGLEUNIT["degree",0.0174532925199433],ID["EPSG",8801]],PARAMETER["Longitude of natural origin",-93,ANGLEUNIT["degree",0.0174532925199433],ID["EPSG",8802]],PARAMETER["Scale factor at natural origin",0.9996,SCALEUNIT["unity",1],ID["EPSG",8805]],PARAMETER["False easting",500000,LENGTHUNIT["metre",1],ID["EPSG",8806]],PARAMETER["False northing",0,LENGTHUNIT["metre",1],ID["EPSG",8807]]],CS[Cartesian,2],AXIS["(E)",east,ORDER[1],LENGTHUNIT["metre",1]],AXIS["(N)",north,ORDER[2],LENGTHUNIT["metre",1]],USAGE[SCOPE["Engineering survey, topographic mapping."],AREA["North America - between 96°W and 90°W - onshore and offshore. Canada - Manitoba; Nunavut; Ontario. United States (USA) - Arkansas; Illinois; Iowa; Kansas; Louisiana; Michigan; Minnesota; Mississippi; Missouri; Nebraska; Oklahoma; Tennessee; Texas; Wisconsin."],BBOX[25.61,-96,84,-90]],ID["EPSG",26915]],VERTCRS["NOAA Chart Datum",VDATUM["NOAA Chart Datum"],CS[vertical,1],AXIS["gravity-related height (H)",up,LENGTHUNIT["metre",1,ID["EPSG",9001]]]]]'
    cs.set_crs(compound_wkt)
    assert cs.horizontal.to_epsg() == 26915
    assert cs.vertical == None
    assert cs.is_valid == False
    assert cs.vyperdatum_str == None
    
def test_vyperpipeline_with_compound_wkt_with_region():
    # test adding a compound crs with the region in the vertical wkt
    cs = VyperPipelineCRS()
    compound_wkt = 'COMPOUNDCRS["NAD83 / UTM zone 15N + NOAA Chart Datum",PROJCRS["NAD83 / UTM zone 15N",BASEGEOGCRS["NAD83",DATUM["North American Datum 1983",ELLIPSOID["GRS 1980",6378137,298.257222101,LENGTHUNIT["metre",1]]],PRIMEM["Greenwich",0,ANGLEUNIT["degree",0.0174532925199433]],ID["EPSG",4269]],CONVERSION["UTM zone 15N",METHOD["Transverse Mercator",ID["EPSG",9807]],PARAMETER["Latitude of natural origin",0,ANGLEUNIT["degree",0.0174532925199433],ID["EPSG",8801]],PARAMETER["Longitude of natural origin",-93,ANGLEUNIT["degree",0.0174532925199433],ID["EPSG",8802]],PARAMETER["Scale factor at natural origin",0.9996,SCALEUNIT["unity",1],ID["EPSG",8805]],PARAMETER["False easting",500000,LENGTHUNIT["metre",1],ID["EPSG",8806]],PARAMETER["False northing",0,LENGTHUNIT["metre",1],ID["EPSG",8807]]],CS[Cartesian,2],AXIS["(E)",east,ORDER[1],LENGTHUNIT["metre",1]],AXIS["(N)",north,ORDER[2],LENGTHUNIT["metre",1]],USAGE[SCOPE["Engineering survey, topographic mapping."],AREA["North America - between 96°W and 90°W - onshore and offshore. Canada - Manitoba; Nunavut; Ontario. United States (USA) - Arkansas; Illinois; Iowa; Kansas; Louisiana; Michigan; Minnesota; Mississippi; Missouri; Nebraska; Oklahoma; Tennessee; Texas; Wisconsin."],BBOX[25.61,-96,84,-90]],ID["EPSG",26915]],VERTCRS["NOAA Chart Datum",VDATUM["NOAA Chart Datum"],CS[vertical,1],AXIS["gravity-related height (H)",up,LENGTHUNIT["metre",1,ID["EPSG",9001]]],REMARK["regions=[TXlagmat01_8301,TXlaggal01_8301],pipeline=+proj=pipeline +step +proj=vgridshift grids=core\\geoid12b\\g2012bu0.gtx +step +inv +proj=vgridshift grids=REGION\\tss.gtx +step +proj=vgridshift grids=REGION\\mllw.gtx"]]]'
    cs.set_crs(compound_wkt)
    assert cs.horizontal.to_epsg() == 26915
    assert cs.vertical.to_wkt() == 'VERTCRS["NOAA Chart Datum",VDATUM["NOAA Chart Datum"],CS[vertical,1],AXIS["gravity-related height (H)",up,LENGTHUNIT["metre",1]],REMARK["regions=[TXlagmat01_8301,TXlaggal01_8301,TXlagmat01_8301,TXlaggal01_8301],pipeline=+proj=pipeline +step +proj=vgridshift grids=core\\geoid12b\\g2012bu0.gtx +step +inv +proj=vgridshift grids=REGION\\tss.gtx +step +proj=vgridshift grids=REGION\\mllw.gtx"]]'
    assert cs.is_valid == True
    assert cs.vyperdatum_str == 'noaa chart datum'
    
def test_vyperpipeline_with_compound_wkt_add_region():
    # test adding a compound crs with no region and then the region
    cs = VyperPipelineCRS()    
    compound_wkt = 'COMPD_CS["NAD83 / UTM zone 18N + MLLW depth",PROJCS["NAD83 / UTM zone 18N",GEOGCS["NAD83",DATUM["North_American_Datum_1983",SPHEROID["GRS 1980",6378137,298.257222101,AUTHORITY["EPSG","7019"]],AUTHORITY["EPSG","6269"]],PRIMEM["Greenwich",0,AUTHORITY["EPSG","8901"]],UNIT["degree",0.0174532925199433,AUTHORITY["EPSG","9122"]],AUTHORITY["EPSG","4269"]],PROJECTION["Transverse_Mercator"],PARAMETER["latitude_of_origin",0],PARAMETER["central_meridian",-75],PARAMETER["scale_factor",0.9996],PARAMETER["false_easting",500000],PARAMETER["false_northing",0],UNIT["metre",1,AUTHORITY["EPSG","9001"]],AXIS["Easting",EAST],AXIS["Northing",NORTH],AUTHORITY["EPSG","26918"]],VERT_CS["MLLW depth",VERT_DATUM["Mean Lower Low Water",2005,AUTHORITY["EPSG","1089"]],UNIT["metre",1,AUTHORITY["EPSG","9001"]],AXIS["Depth",DOWN],AUTHORITY["EPSG","5866"]]]'
    cs.set_crs(compound_wkt)
    assert cs.horizontal.to_epsg() == 26918
    assert cs.is_valid == False
    assert cs.vertical == None
    cs.update_regions(['MENHMAgome23_8301'])
    assert cs.is_valid == True
    assert cs.vertical.to_wkt() == 'VERTCRS["MLLW depth",VDATUM["MLLW depth"],CS[vertical,1],AXIS["depth (D)",up,LENGTHUNIT["metre",1]],REMARK["regions=[MENHMAgome23_8301],pipeline=+proj=pipeline +step +proj=vgridshift grids=core\\geoid12b\\g2012bu0.gtx +step +inv +proj=vgridshift grids=REGION\\tss.gtx +step +proj=vgridshift grids=REGION\\mllw.gtx"]]'
    assert cs.vyperdatum_str == 'mllw'

def test_vyperpipeline_set_compound_wkt_on_instantiation():
    # test adding a compound crs wkt on instantiation of the object
    compound_wkt = 'COMPOUNDCRS["NAD83 / UTM zone 18N + MLLW depth",PROJCRS["NAD83 / UTM zone 18N",BASEGEOGCRS["NAD83",DATUM["North American Datum 1983",ELLIPSOID["GRS 1980",6378137,298.257222101,LENGTHUNIT["metre",1]]],PRIMEM["Greenwich",0,ANGLEUNIT["degree",0.0174532925199433]],ID["EPSG",4269]],CONVERSION["UTM zone 18N",METHOD["Transverse Mercator",ID["EPSG",9807]],PARAMETER["Latitude of natural origin",0,ANGLEUNIT["degree",0.0174532925199433],ID["EPSG",8801]],PARAMETER["Longitude of natural origin",-75,ANGLEUNIT["degree",0.0174532925199433],ID["EPSG",8802]],PARAMETER["Scale factor at natural origin",0.9996,SCALEUNIT["unity",1],ID["EPSG",8805]],PARAMETER["False easting",500000,LENGTHUNIT["metre",1],ID["EPSG",8806]],PARAMETER["False northing",0,LENGTHUNIT["metre",1],ID["EPSG",8807]]],CS[Cartesian,2],AXIS["easting",east,ORDER[1],LENGTHUNIT["metre",1]],AXIS["northing",north,ORDER[2],LENGTHUNIT["metre",1]],ID["EPSG",26918]],VERTCRS["MLLW depth",VDATUM["MLLW depth"],CS[vertical,1],AXIS["depth (D)",up,LENGTHUNIT["metre",1,ID["EPSG",9001]]],REMARK["regions=[MENHMAgome23_8301],pipeline=+proj=pipeline +step +proj=vgridshift grids=core\\geoid12b\\g2012bu0.gtx +step +inv +proj=vgridshift grids=REGION\\tss.gtx +step +proj=vgridshift grids=REGION\\mllw.gtx"]]]'
    cs = VyperPipelineCRS(compound_wkt)    
    assert cs.horizontal.to_epsg() == 26918
    assert cs.is_valid == True
    assert cs.vertical.to_wkt() == 'VERTCRS["MLLW depth",VDATUM["MLLW depth"],CS[vertical,1],AXIS["depth (D)",up,LENGTHUNIT["metre",1]],REMARK["regions=[MENHMAgome23_8301,MENHMAgome23_8301],pipeline=+proj=pipeline +step +proj=vgridshift grids=core\\geoid12b\\g2012bu0.gtx +step +inv +proj=vgridshift grids=REGION\\tss.gtx +step +proj=vgridshift grids=REGION\\mllw.gtx"]]'
    assert cs.vyperdatum_str == 'mllw'
    
if __name__ == '__main__':
    test_derived_parameter_file()
    test_transformation_inv_nad83()
    test_transformation_noregion()
    test_transformation_tss()
    test_transformation_unsupported_name()
    test_vertical_derived_crs()
    test_vertical_pipeline_crs()
