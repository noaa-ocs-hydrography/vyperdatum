"""
WKT spec http://docs.opengeospatial.org/is/18-010r7/18-010r7.html

Need something to build wkt for our custom datum transformations

Just do the vertical since there aren't any custom horiz transforms that we do.  We can do a compound CRS with the known
horiz later.  How do we handle these custom vert transformations though?  We have no EPSG registered datum, so it won't be
something we can directly use in pyproj.  We have to build our own pipeline from a source custom vert to a source custom
vert.
"""

import os
from typing import Union
from pyproj.crs import CRS, CompoundCRS, VerticalCRS as pyproj_VerticalCRS
import pyproj.datadir
from vyperdatum.pipeline import get_regional_pipeline, datum_definition
from vyperdatum.__version__ import __version__


NAD83_2D = 6318
NAD83_3D = 6319
ITRF2008_2D = 8999
ITRF2008_3D = 7911
ITRF2014_2D = 9000
ITRF2014_3D = 7912

frame_lookup = {CRS.from_epsg(NAD83_2D).name: 'NAD83',
                CRS.from_epsg(NAD83_3D).name: 'NAD83',
                CRS.from_epsg(ITRF2008_2D).name: 'ITRF2008',
                CRS.from_epsg(ITRF2008_3D).name: 'ITRF2008',
                CRS.from_epsg(ITRF2014_2D).name: 'ITRF2014',
                CRS.from_epsg(ITRF2014_3D).name: 'ITRF2014'}

geoid_frame_lookup = {r'core\geoid12b\g2012bu0.gtx': CRS.from_epsg(NAD83_2D).name,
                      r'core\geoid12b\g2012bp0.gtx': CRS.from_epsg(NAD83_2D).name,
                      r'core\xgeoid16b\ak.gtx': CRS.from_epsg(ITRF2008_2D).name,
                      r'core\xgeoid16b\conus.gtx': CRS.from_epsg(ITRF2008_2D).name,
                      r'core\xgeoid16b\hi.gtx': CRS.from_epsg(ITRF2008_2D).name,
                      r'core\xgeoid16b\prvi.gtx': CRS.from_epsg(ITRF2008_2D).name,
                      r'core\xgeoid17b\AK_17B.gtx': CRS.from_epsg(ITRF2008_2D).name,
                      r'core\xgeoid17b\CONUS_17B.gtx': CRS.from_epsg(ITRF2008_2D).name,
                      r'core\xgeoid17b\PRVI_17B.gtx': CRS.from_epsg(ITRF2008_2D).name,
                      r'core\xgeoid18b\AK_18B.gtx': CRS.from_epsg(ITRF2008_2D).name,
                      r'core\xgeoid18b\CONUS_18B.gtx': CRS.from_epsg(ITRF2008_2D).name,
                      r'core\xgeoid18b\PRVI_18B.gtx': CRS.from_epsg(ITRF2008_2D).name,
                      r'core\xgeoid18b\GU_18B.gtx': CRS.from_epsg(ITRF2008_2D).name,
                      r'core\xgeoid19b\CONUSPAC.pc.gtx': CRS.from_epsg(ITRF2008_2D).name,
                      r'core\xgeoid20b\conuspac.gtx': CRS.from_epsg(ITRF2014_2D).name,
                      r'core\xgeoid20b\as.gtx': CRS.from_epsg(ITRF2014_2D).name,
                      r'core\xgeoid20b\gu.gtx': CRS.from_epsg(ITRF2014_2D).name}

geoid_possibilities = ['geoid12b', 'xgeoid16b', 'xgeoid17b', 'xgeoid18b', 'xgeoid19b', 'xgeoid20b']

frame_to_3dcrs = {CRS.from_epsg(NAD83_2D).name: CRS.from_epsg(NAD83_3D),
                  CRS.from_epsg(ITRF2008_2D).name: CRS.from_epsg(ITRF2008_3D),
                  CRS.from_epsg(ITRF2014_2D).name: CRS.from_epsg(ITRF2014_3D)}

valid_grid_extensions = ['.tiff', '.tif', '.gtx']


class CoordinateSystem:
    """
    Contains the information needed to generate the CS string

    ex: CS[vertical,1], AXIS["gravity-related height (H)",up], LENGTHUNIT["metre",1.0]
    """
    def __init__(self, axis_type: str = '', axis: tuple = tuple(), units: str = '', is_3d: bool = False):
        self.axis_type = axis_type
        self.axis = axis
        self.units = units
        self.is_3d = is_3d

    @property
    def lengthunit_string(self):
        if self.units.lower() in ['m', 'meter', 'metre', 'meters', 'metres']:
            return 'LENGTHUNIT["metre",1]'
        else:
            raise NotImplementedError(f'Only meters is suppported, got {self.units}')

    @property
    def axis_string(self):
        axis_string = ''
        for cnt, ax in enumerate(self.axis):
            if cnt >= 1:
                axis_string += ','
            if ax.lower() in ['h', 'height', 'ellipsoid height', 'ellipsoid height (h)']:
                axis_string += 'AXIS["ellipsoid height (h)",up]'
            elif ax.lower() in ['gravity-related height (h)', 'gravity-related height', 'up']:
                axis_string += 'AXIS["gravity-related height (H)",up]'
            elif ax.lower() in ['d', 'depth', 'depth (d)']:
                axis_string += 'AXIS["depth (D)",down]'
            else:
                raise ValueError(f'"{ax}" is not a registered axis type, such as "height" or "depth".')
        return axis_string

    @property
    def cs_string(self):
        cs_string = ''
        if self.axis_type.lower() == 'vertical':
            cs_string = 'CS[vertical,1]'
        elif self.axis_type.lower() == 'cartesian':
            raise NotImplementedError('2d cartesian not supported')
        elif self.axis_type.lower() == 'ellipsoidal':
            raise NotImplementedError('2d/3d ellipsoidal not supported')
        return cs_string

    def to_wkt(self):
        self.validate()
        return f'{self.cs_string},{self.axis_string},{self.lengthunit_string}'

    def to_pretty_wkt(self):
        self.validate()
        pretty_ident = len('CS') * ' '
        return f'{self.cs_string},\n  {pretty_ident}{self.axis_string},\n  {pretty_ident}{self.lengthunit_string}'

    def validate(self):
        if not self.axis_type:
            raise ValueError('CoordinateSystem: axis_type must be populated first, ex: "vertical"')
        if not self.axis:
            raise ValueError('CoordinateSystem: axis must be populated first, ex: "height"')
        if not self.units:
            raise ValueError('CoordinateSystem: units must be populated first, ex: "meters"')


class VerticalDatum:
    """
    Contains the information needed to generate the VDATUM string

    ex: VDATUM["NOAA Mean Lower Low Water"]
    """
    def __init__(self, datum_string: str = ''):
        self.datum_string = datum_string

    def to_wkt(self):
        return f'VDATUM["{self.datum_string}"]'

    def to_pretty_wkt(self):
        return f'VDATUM["{self.datum_string}"]'

    def validate(self):
        if not self.datum_string:
            raise ValueError('VerticalDatum: grid_source must be populated first, ex: "NOAA Chart Datum"')


class ParameterFile:
    """
    Contains the information needed to build the PARAMETERFILE string

    ex: PARAMETERFILE['mllw', 'CAORblan01_8301\\mllw.gtx', ID[“NOAA VDatum”, “Tss to Mean Lower Low Water”, “06/20/2019”]]
    """
    def __init__(self, grid_source: str, grid_identifier: str, grid_path: str, grid_description: str, grid_date: str):
        self.grid_source = grid_source
        self.grid_identifier = grid_identifier
        self.grid_path = grid_path
        self.grid_description = grid_description
        self.grid_date = grid_date

    def load_from_list(self, gridsource, gridident, gridpath, griddescrp, griddate):
        self.grid_source = gridsource
        self.grid_identifier = gridident
        self.grid_path = gridpath
        self.grid_description = griddescrp
        self.grid_date = griddate

    @property
    def id_string(self):
        return f'ID["{self.grid_source}", "{self.grid_description}", "{self.grid_date}"]'

    @property
    def parameter_string(self):
        return f'PARAMETERFILE["{self.grid_identifier}", "{self.grid_path}"'

    def to_wkt(self):
        self.validate()
        return f'{self.parameter_string}, {self.id_string}]'

    def to_pretty_wkt(self):
        self.validate()
        pretty_ident = len('DERIVINGCONVERSION') * ' '
        return f'{self.parameter_string}\n{pretty_ident}  {self.id_string}]'

    def validate(self):
        if not self.grid_source:
            raise ValueError('ParameterFile: grid_source must be populated first, ex: “NOAA VDatum”')
        elif not self.grid_identifier:
            raise ValueError('ParameterFile: grid_identifier must be populated first, ex: "g2012bu0"')
        elif not self.grid_path:
            raise ValueError('ParameterFile: grid_path must be populated first, ex: “core\\geoid12b\\g2012bu0.gtx”')
        elif not self.grid_description:
            raise ValueError('ParameterFile: grid_description must be populated first, ex: “NAD83 to Geoid12B”')
        elif not self.grid_date:
            raise ValueError('ParameterFile: grid_date must be populated first, ex: 10/23/2012”')


class DerivingConversion:
    """
    Contains the information needed to build the DERIVINGCONVERSION string,

    ex: DERIVINGCONVERSION["NAD83(2011) Height to NOAA Mean Lower Low Water", METHOD["VDatum_VXXX gtx grid transformation", ID["EPSG",1084]]
    """
    def __init__(self, conversion_string: str = '', method_description: str = ''):
        self.conversion_string = conversion_string
        self.method_description = method_description

        self.file_data = []

    @property
    def method_string(self):
        if self.method_description.lower().find('gtx') != -1:
            return f'METHOD["{self.method_description}", ID["EPSG",1084]]'
        elif self.method_description.lower().find('asc') != -1:
            return f'METHOD["{self.method_description}", ID["EPSG",1085]]'
        else:
            raise NotImplementedError('Only gtx and asc currently supported for building ID EPSG strings')

    def add_parameter_file(self, grid_source: str, grid_identifier: str, grid_path: str, grid_description: str, grid_date: str):
        self.file_data.append([grid_source, grid_identifier, grid_path, grid_description, grid_date])

    def to_wkt(self):
        self.validate()
        wktstring = f'DERIVINGCONVERSION["{self.conversion_string}",{self.method_string}'
        for fil in self.file_data:
            wktstring += ','
            pm = ParameterFile(fil[0], fil[1], fil[2], fil[3], fil[4])
            wktstring += pm.to_wkt()
        wktstring += ']'
        return wktstring

    def to_pretty_wkt(self):
        self.validate()
        pretty_ident = len('DERIVINGCONVERSION') * ' '
        wktstring = f'DERIVINGCONVERSION["{self.conversion_string}",\n{pretty_ident}{self.method_string}'
        for fil in self.file_data:
            wktstring += f',\n{pretty_ident}'
            pm = ParameterFile(fil[0], fil[1], fil[2], fil[3], fil[4])
            wktstring += pm.to_wkt()
        wktstring += ']'
        return wktstring

    def validate(self):
        if not self.conversion_string:
            raise ValueError('DerivingConversion: conversion_string must be populated first, ex: "NAD83(2011) Height to NOAA Mean Lower Low Water"')
        elif not self.method_description:
            raise ValueError('DerivingConversion: method_description must be populated first, ex: "VDatum gtx grid transformation"')


class BaseVerticalCRS:
    """
    Contains the information needed to build the BASEVERTCRS string:

    ex: BASEVERTCRS["NAD83(2011) Height", VDATUM["NAD83(2011) Height"], ID["EPSG",6319]]
    """
    def __init__(self, datum_description: str = ''):
        self.datum_descrption = datum_description

    @property
    def vertical_datum_string(self):
        return VerticalDatum(self.datum_descrption).to_wkt()

    @property
    def id_string(self):
        if self.datum_descrption.lower().find('nad83') != -1:
            return 'ID["EPSG",6319]'
        elif self.datum_descrption.lower().find('wgs') != -1:
            return 'ID["EPSG",4979]'
        else:
            raise NotImplementedError(f'Only nad83 and wgs84 supported, unable to find either in {self.datum_descrption}')

    def to_wkt(self):
        self.validate()
        return f'BASEVERTCRS["{self.datum_descrption}",{self.vertical_datum_string},{self.id_string}]'

    def to_pretty_wkt(self):
        self.validate()
        pretty_ident = len('BASEVERTCRS') * ' '
        return f'BASEVERTCRS["{self.datum_descrption}",\n{pretty_ident}{self.vertical_datum_string},\n{pretty_ident}{self.id_string}]'

    def validate(self):
        if not self.datum_descrption:
            raise ValueError('BaseVerticalCRS: datum_description must be populated first, ex: "NAD83(2011) Height"')

