"""
WKT spec http://docs.opengeospatial.org/is/18-010r7/18-010r7.html

Need something to build wkt for our custom datum transformations

Just do the vertical since there aren't any custom horiz transforms that we do.  We can do a compound CRS with the known
horiz later.  How do we handle these custom vert transformations though?  We have no EPSG registered datum, so it won't be
something we can directly use in pyproj.  We have to build our own pipeline from a source custom vert to a source custom
vert.
"""
from typing import Union
from pyproj.crs import CRS, CompoundCRS, VerticalCRS as pyproj_VerticalCRS

from vyperdatum.pipeline import get_regional_pipeline, datum_definition


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
            if ax.lower() in ['h', 'height', 'gravity-related height (h)', 'gravity-related height']:
                axis_string += 'AXIS["gravity-related height (H)",up]'
            elif ax.lower() in ['d', 'depth', 'depth (d)']:
                axis_string += 'AXIS["depth (D)",up]'
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


class VerticalCRS:
    """
    The base class for all the different flavors of vertical CRS.  Contains the different classes and data types that
    you can use to build the vertical CRS.  See VerticalPipelineCRS and VerticalDerivedCRS to see how it gets used.

    Setting one of the attributes here automatically sets the class that contains that attribute, so you can set the
    datum name for instance, and go straight to wkt, as the VerticalDatum class gets updated in the setter.
    """

    def __init__(self):
        self._base_crs = BaseVerticalCRS('')
        self._deriving_conversion = DerivingConversion('', '')
        self._vertical_datum = VerticalDatum('')
        self._coordinate_system = CoordinateSystem('vertical', ('height',), 'm')

    @property
    def datum_name(self):
        return self._vertical_datum.datum_string

    @datum_name.setter
    def datum_name(self, datum_name: str):
        self._vertical_datum.datum_string = datum_name

    @property
    def base_datum_name(self):
        return self._base_crs.datum_descrption

    @base_datum_name.setter
    def base_datum_name(self, base_datum_name: str):
        self._base_crs.datum_descrption = base_datum_name

    @property
    def conversion_name(self):
        return self._deriving_conversion.conversion_string

    @conversion_name.setter
    def conversion_name(self, conversion_name: str):
        self._deriving_conversion.conversion_string = conversion_name

    @property
    def conversion_method(self):
        return self._deriving_conversion.method_description

    @conversion_method.setter
    def conversion_method(self, conversion_method: str):
        self._deriving_conversion.method_description = conversion_method

    @property
    def coordinate_type(self):
        return self._coordinate_system.axis_type

    @coordinate_type.setter
    def coordinate_type(self, coordinate_type: str):
        self._coordinate_system.axis_type = coordinate_type

    @property
    def coordinate_axis(self):
        return self._coordinate_system.axis

    @coordinate_axis.setter
    def coordinate_axis(self, coordinate_axis: tuple):
        self._coordinate_system.axis = coordinate_axis

    @property
    def coordinate_units(self):
        return self._coordinate_system.units

    @coordinate_units.setter
    def coordinate_units(self, coordinate_units: str):
        self._coordinate_system.units = coordinate_units

    def _wkt_search_string(self, wkt_string: str, startkey: str):
        start_index = wkt_string.find(startkey)
        if start_index != -1:
            start_index = start_index + len(startkey) + 1
            end_index = wkt_string.find('"', start_index)
            if end_index == -1:
                end_index = wkt_string.find("'", start_index)
            if end_index != -1:
                ans = wkt_string[start_index:end_index]
            else:
                raise ValueError(f'from_wkt: Unable to find " in wkt string starting at index {start_index}')
        else:
            if startkey == 'REMARK[':
                ans = None
            else:
                raise ValueError(f'from_wkt: Unable to find {startkey} in wkt string')
        return ans

    def _wkt_search_data(self, wkt_string: str, startkey: str):
        start_index = wkt_string.find(startkey)
        if start_index != -1:
            start_index = start_index + len(startkey)
            end_index = wkt_string.find(',', start_index)
            if end_index != -1:
                ans = wkt_string[start_index:end_index]
            else:
                raise ValueError(f'from_wkt: Unable to find " in wkt string starting at index {start_index}')
        else:
            raise ValueError(f'from_wkt: Unable to find {startkey} in wkt string')
        return ans

    def _wkt_parameter_files(self, wkt_string):
        strt = 0
        data = []
        next_file = wkt_string.find('PARAMETERFILE[', strt)
        while next_file != -1:
            end_param = wkt_string.find(']],', next_file)
            strt = end_param
            param_block = wkt_string[next_file + len('PARAMETERFILE['):end_param].split(',')
            pdata = [param_block[2].replace('ID[', '').strip(' ').strip("'").strip('"'),
                     param_block[0].strip(' ').strip('"').strip("'"),
                     param_block[1].strip(' ').strip('"').strip("'"),
                     param_block[3].strip(' ').strip('"').strip("'"),
                     param_block[4].replace(']', '').strip(' ').strip('"').strip("'")]
            data.append(pdata)
            next_file = wkt_string.find('PARAMETERFILE[', strt)
            print(data, next_file)
        return data

    def _wkt_pipeline_remarks(self, wkt_string):
        remarks = self._wkt_search_string(wkt_string, 'REMARK[')
        if remarks:
            region_start = remarks.find('regions=')
            if region_start != -1:
                strt = region_start + len('regions=') + 1
                region_end = remarks.find('],', strt)
                region_data = remarks[strt:region_end]
                regions = [x.strip() for x in region_data.split(',')]
            else:
                raise ValueError(f'Unable to find regions keyword in remarks string {remarks}')
            pipeline_start = remarks.find('pipeline=')
            if pipeline_start != -1:
                strt = pipeline_start + len('pipeline=')
                pipeline = remarks[strt:]
            else:
                raise ValueError(f'Unable to find pipeline keyword in remarks string {remarks}')
            return pipeline, regions
        else:
            return '',[]

class VerticalDerivedCRS(VerticalCRS):
    """
    WARNING: this class generates wkt that is not supported in PROJ, see VerticalPipelineCRS instead

    Builds the DERIVINGCONVERSION data and allows you to add pipelines to it.  This was my first attempt at building
    a class that would allow us to use a custom vertical datum in PROJ.  The derived vertical CRS is however not
    supported in PROJ, from Even Rouault:

    'I don't think DerivedVerticalCRS is the appropriate modeling. 3.1.14 mentions: "A derived coordinate reference
    system inherits its datum or reference frame from its base coordinate reference system.", so you can't have the
    derived CRS having VDATUM["NOAA Chart Datum"] and the base CRS VDATUM["NAD83(2011) Height"]. And if you look at the
    grammar (in the docs), VDATUM[] is not allowed for the derived vertical CRS, and when PROJ re-exports to WKT2 this
    definition, it will omit it.'

    Class is included in vypercrs for reference only.

    ex:
    VERTCRS["NOAA Chart Datum",
            BASEVERTCRS["NAD83(2011) Height",
                        VDATUM["NAD83(2011) Height"],
                        ID["EPSG",6319]],
            DERIVINGCONVERSION["NAD83(2011) Height to NOAA Mean Lower Low Water",
                               METHOD["VDatum gtx grid transformation",
                                 ID["EPSG",1084]],
                               PARAMETERFILE['g2012bu0', 'core\\geoid12b\\g2012bu0.gtx',
                                 ID[“NOAA VDatum”, “NAD83 to Geoid12B”, “10/23/2012”]],
                               PARAMETERFILE['tss', 'CAORblan01_8301\\tss.gtx',
                                 ID[“NOAA VDatum”, “Geoid12B to Tss", “06/20/2019”]],
                               PARAMETERFILE['mllw', 'CAORblan01_8301\\mllw.gtx',
                                 ID[“NOAA VDatum”, “Tss to Mean Lower Low Water”, “06/20/2019”]]],
            VDATUM["NOAA Chart Datum"],
            CS[vertical,1],
              AXIS["gravity-related height (H)",up,
              LENGTHUNIT["metre",1]]]
    """
    def __init__(self, datum_name: str = '', base_datum_name: str = '', conversion_name: str = '',
                 conversion_method: str = '', coordinate_type: str = 'vertical', coordinate_axis: tuple = ('height',),
                 coordinate_units: str = 'm'):
        super().__init__()

        self.datum_name = datum_name
        self.base_datum_name = base_datum_name
        self.conversion_name = conversion_name
        self.conversion_method = conversion_method
        self.coordinate_type = coordinate_type
        self.coordinate_axis = coordinate_axis
        self.coordinate_units = coordinate_units

    def add_parameter_file(self, grid_source: str, grid_identifier: str, grid_path: str, grid_description: str, grid_date: str):
        self._deriving_conversion.add_parameter_file(grid_source, grid_identifier, grid_path, grid_description, grid_date)

    def to_wkt(self):
        wktstr = f'VERTCRS["{self.datum_name}",{self._base_crs.to_wkt()},{self._deriving_conversion.to_wkt()},'
        wktstr += f'{self._vertical_datum.to_wkt()},{self._coordinate_system.to_wkt()}]'
        return wktstr

    def from_wkt(self, wkt_string: str):
        self.datum_name = self._wkt_search_string(wkt_string, 'VERTCRS[')
        self.base_datum_name = self._wkt_search_string(wkt_string, 'BASEVERTCRS[')
        self.conversion_name = self._wkt_search_string(wkt_string, 'DERIVINGCONVERSION[')
        self.conversion_method = self._wkt_search_string(wkt_string, 'METHOD[')
        self.coordinate_type = self._wkt_search_data(wkt_string, 'CS[')
        self.coordinate_axis = (self._wkt_search_string(wkt_string, 'AXIS['),)
        self.coordinate_units = self._wkt_search_string(wkt_string, 'LENGTHUNIT[')

        paramfiles = self._wkt_parameter_files(wkt_string)
        for pfil in paramfiles:
            self.add_parameter_file(pfil[0], pfil[1], pfil[2], pfil[3], pfil[4])

    def to_pretty_wkt(self):
        wktstr = f'VERTCRS["{self.datum_name}",\n'
        wktstr += f'  {self._base_crs.to_pretty_wkt()},\n'
        wktstr += f'  {self._deriving_conversion.to_pretty_wkt()},\n'
        wktstr += f'  {self._vertical_datum.to_pretty_wkt()},\n'
        wktstr += f'  {self._coordinate_system.to_pretty_wkt()}]\n'
        return wktstr

    def to_crs(self):
        return CRS.from_wkt(self.to_wkt())


class VerticalPipelineCRS(VerticalCRS):
    """
    This class allows us to specify a custom vertical CRS, by recording the basic metadata of that vertical CRS and
    storing the PROJ pipeline that gets us to that custom datum in the remarks field.  This is not really operational
    in PROJ (i.e. we have to run the pipeline ourselves) but it does serve as adequate documentation for now.  Registering
    our VDatum grids in EPSG will be the eventual solution, which would do away with most of this.

    ex:
    VERTCRS["NOAA Chart Datum",
           VDATUM["NOAA Mean Lower Low Water"],
           CS[vertical,1],
             AXIS["gravity-related height (H)",up],
             LENGTHUNIT["metre",1.0],
           REMARK["regions=[TXlagmat01_8301, TXlaggal01_8301],
                   proj=pipeline step proj=vgridshift grids=core\\geoid12b\\g2012bu0.gtx step proj=vgridshift grids=REGION\\tss.gtx"]]
    """

    def __init__(self, datum_name: str = '', coordinate_type: str = 'vertical',
                 coordinate_axis: tuple = ('height',), coordinate_units: str = 'm', horiz_wkt: str = None):

        super().__init__()
        self.horiz_wkt = horiz_wkt
        self.datum_name = datum_name
        self.coordinate_type = coordinate_type
        self.coordinate_axis = coordinate_axis
        self.coordinate_units = coordinate_units

        self.regions = []
        self.pipeline_string = ''

    def add_pipeline(self, pipeline: str, region: str):
        self.regions.append(region)
        # remove region name from the pipeline, replace with 'REGION' keyword
        pipeline = pipeline.replace(region, 'REGION')
        if self.pipeline_string and self.pipeline_string != pipeline:
            raise ValueError(f'New pipeline provided does not match the existing pipeline in this CRS: {self.pipeline_string}')
        self.pipeline_string = pipeline

    def build_remarks(self, pretty=False):
        fmt_regions = '['
        for cnt, reg in enumerate(self.regions):
            if cnt >= 1:
                fmt_regions += ','
            fmt_regions += reg
        fmt_regions += ']'

        if pretty:
            pretty_ident = len('REMARK') * ' '
            return f'REMARK["regions={fmt_regions},\n{pretty_ident}pipeline={self.pipeline_string}"]'
        else:
            return f'REMARK["regions={fmt_regions},pipeline={self.pipeline_string}"]'

    def to_wkt(self):
        wktstr = f'VERTCRS["{self.datum_name}",{self._vertical_datum.to_wkt()},{self._coordinate_system.to_wkt()},'
        if len(self.regions) > 0 and len(self.pipeline_string) > 0:
            wktstr += f'{self.build_remarks()}]'
        else:
            wktstr += ']'
        return wktstr

    def from_wkt(self, wkt_string: str):
        self.datum_name = self._wkt_search_string(wkt_string, 'VERTCRS[')
        self.coordinate_type = self._wkt_search_data(wkt_string, 'CS[')
        self.coordinate_axis = (self._wkt_search_string(wkt_string, 'AXIS['),)
        self.coordinate_units = self._wkt_search_string(wkt_string, 'LENGTHUNIT[')
        self.pipeline_string, self.regions = self._wkt_pipeline_remarks(wkt_string)

    def to_pretty_wkt(self):
        wktstr = f'VERTCRS["{self.datum_name}",\n'
        wktstr += f'  {self._vertical_datum.to_pretty_wkt()},\n'
        wktstr += f'  {self._coordinate_system.to_pretty_wkt()}]\n'
        if len(self.regions) > 0 and len(self.pipeline_string) > 0:
            wktstr += f'  {self.build_remarks()}]'
        else:
            wktstr += ']'
        return wktstr

    def to_compound_wkt(self):
        """
        Must have a compound CRS to use GDAL to save data to geoTiff
        """
        horiz_wkt = self.horiz_wkt
        if self.horiz_wkt is None:
            raise ValueError('No horizontal coordinate system set, this is generally done on loading new raster dataset')
        # wkt should always start with keyword like PROJCS["NAD83 / UTM zone 19N"
        horiz_wkt_name = horiz_wkt.split('"')[1]
        vert_wkt = self.to_wkt()
        wktstr = f'COMPOUNDCRS["{horiz_wkt_name} + {self.datum_name}",'
        wktstr += f'{horiz_wkt},'
        wktstr += f'{vert_wkt}]'
        return wktstr

    def to_crs(self):
        return CRS.from_wkt(self.to_wkt())

    def to_compound_crs(self):
        return CRS.from_wkt(self.to_compound_wkt())

class VyperPipelineCRS:
    """
    A container for developing and validating compound crs objects built around pyproj crs objects
    and the vypercrs.VerticalPipelineCRS object.
    """
    
    def __init__(self, new_crs: Union[str, int, tuple] = None, regions:[str] = None):
        self._is_valid = False
        self._ccsr = None
        self._vert = None
        self._hori = None
        self._regions = None
        self._vyperdatum_str = None
        if new_crs != None:
            self.set_crs(new_crs, regions)
        
    def set_crs(self, new_crs: Union[str, int, tuple], regions:[str] = None):
        """
        Set the object vertical and / or horizontal crs using either an epsg code or wkt.
        Regions are also optionally set with a list of VDatum region strings.

        Parameters
        ----------
        new_crs : Union[str, int, tuple]
            A wkt string or a vyperdatum vertical datum definition string or an epsg code
            may be provided either on its own or as a tuple pair.  While the order (horizontal or vertical)
            does not matter, if they contain information for the same frame (horizontal or vertical) the
            second will overwrite the first.
            
            Once the provided object datums are set, the object compound attribute is set if the horizontal,
            verical, and region information is available.
            
        regions : [str], optional
            A list of VDatum region strings.  These values will overwrite the values contained in the vertical
            WKT if they exist. The default is None.

        Raises
        ------
        ValueError
            If a tuple of length greater than two is provided or if the provided value(s) are not a string
            or an integer.

        Returns
        -------
        None.

        """
        # check the input type
        if type(new_crs) == tuple:
            if len(new_crs) > 2:
                len_crs = len(new_crs)
                raise ValueError(f'The provided crs {new_crs} is {len_crs} in length but should have a length of two.')
        else:
            new_crs = (new_crs,)
        # create pyproj crs based on the input type
        for entry in new_crs:
            if type(entry) == str:
                crs_str = entry
                if entry.lower() in datum_definition:
                    self._vyperdatum_str = entry
                    tmp_crs = VerticalPipelineCRS(datum_name = entry)
                    crs_str = tmp_crs.to_wkt()
                crs = CRS.from_wkt(crs_str)
                self._set_single(crs)
            elif type(entry) == int:
                crs = CRS.from_epsg(entry)
                self._set_single(crs)
            else:
                raise ValueError(f'The crs description type {entry} is not recognized.')
        if regions:
            self.update_regions(regions)
            
        self._build_compound()        
            
    def update_regions(self, regions:[str]):
        """
        Update the regions object attribute.

        Parameters
        ----------
        regions : [str]
            DESCRIPTION.

        Returns
        -------
        None.

        """
        self._regions = regions
        if self._vert:
            self._vert, self._vyperdatum_str = build_valid_vert_crs(self._vert, regions)
        self._build_compound()
            
    def _set_single(self, crs: CRS):
        """
        Assign the provided pyproj crs object to the object attribute representing either the
        vertical crs or the horizontal crs.  If the object contains a new vertical crs and
        contains the remarks for the regions, the regions are also extracted and assigned to
        the associated object attribute.

        Parameters
        ----------
        crs : pyproj.crs.CRS
            The new crs.

        Returns
        -------
        None.

        """
        new_vert = False
        if crs.is_compound:
            self.ccrs = crs
            self._hori = crs.sub_crs_list[0]
            self._vert = crs.sub_crs_list[1]
            new_vert = True
        elif crs.is_vertical:
            self._vert = crs
            new_vert =True
        else:
            self._hori = crs
        if new_vert and self._valid_vert():
            tmp_vert = VerticalPipelineCRS()
            tmp_vert.from_wkt(self._vert.to_wkt())
            self.update_regions(tmp_vert.regions)
            self._vyperdatum_str = guess_vertical_datum_from_string(self._vert.name)
         
    def _build_compound(self):
        """
        Create a compound crs object attribute and mark the object as valid if there is a horizontal
        crs, a vertical crs, and if the vertical crs includes the pipeline and regions in the remarks.

        Returns
        -------
        None.

        """
        if self._hori and self._vert and self._valid_vert():
            compound_name = f'{self._hori.name} + {self._vert.name}'
            self.ccrs = CompoundCRS(compound_name, [self._hori, self._vert])
            self._is_valid = True
            
    def _valid_vert(self) -> bool:
        """
        See if there is a vertical crs in the object and if it has regions and
        and a pipeline in the remarks.

        Returns
        -------
        bool
            True if there is a vertical crs object and the remarks include
            the pipeline and regions.

        """
        valid = False
        if self._vert and self._vert.remarks:
            if 'regions' in self._vert.remarks and 'pipeline' in self._vert.remarks:
                valid = True
        return valid
    
    @property
    def is_valid(self):
        return self._is_valid
    
    @property
    def vertical(self):
        if self._valid_vert():
            return self._vert
        else:
            return None
        
    @property    
    def horizontal(self):
        return self._hori
    
    @property
    def regions(self):
        return self._regions
    
    @property
    def vyperdatum_str(self):
        return self._vyperdatum_str
    
    def to_wkt(self):
        if self._is_valid:
            return self.ccrs.to_wkt()
        else:
            return None
            
def build_valid_vert_crs(crs: pyproj_VerticalCRS, regions: [str]) -> (pyproj_VerticalCRS, str):
    """
    Add the regions and pipeline to the remarks section of the wkt for the
    provided pyproj VerticalCRS object.

    Parameters
    ----------
    crs : pyproj.crs.VerticalCRS
        The vertical crs object to add the pipeline and region into.
    regions : [str]
        The regions to add into the crs remarks.

    Returns
    -------
    result (pyproj.crs.VerticalCRS, str)
        First value is the vertical crs object with the remarks updated to add the region and
        pipeline.  The second value is the vyperdatum.pipeline datum identifier.

    """
    is_ak = is_alaska(regions)
    datum = guess_vertical_datum_from_string(crs.name)
    new_crs = VerticalPipelineCRS()
    new_crs.from_wkt(crs.to_wkt())
    if datum:
        for region in regions:
            new_pipeline = get_regional_pipeline('nad83', datum, region, is_alaska=is_ak)
            if new_pipeline:
                new_crs.add_pipeline(new_pipeline, region)
        valid_vert_crs = CRS.from_wkt(new_crs.to_wkt())
    else:
        valid_vert_crs = None
    return valid_vert_crs, datum

def is_alaska(regions:[str]) -> bool:
    """
    A somewhat weak implementation of a method to determine if these regions are in alaska.  Currently, alaskan
    tidal datums are based on xgeoid18, so we need to identify those regions to ensure we use the correct geoid
    during transformation.

    Could probably just use the geographic bounds, but this method works and is less expensive.

    Parameters
    ----------
    regions
        list of vdatum region strings

    Returns
    -------
    bool
        True if all regions are in alaska
    """
    if regions:
        ak_region = [t.find('AK') != -1 for t in regions]
        any_ak = any(ak_region)
        all_ak = all(ak_region)
        if any_ak and all_ak:
            is_ak = True
        elif any_ak:
            raise NotImplementedError('Regions in and not in alaska specified, not currently supported')
        else:
            is_ak = False
    else:
        is_ak = False
    return is_ak

def guess_vertical_datum_from_string(vertical_datum_name: str) -> str:
    """
    Guess the vyperdatum string name by inspecting the string provided and
    looking for matches to the datum names.

    Parameters
    ----------
    vertical_datum_name : str
        A string from the datum WKT.

    Raises
    ------
    ValueError
        If more than one match to the datum definition is found to match the
        string provided.

    Returns
    -------
    str
        The matching vyperdatum string name if there is one, otherwise returns
        None.
        

    """
    guess_list = []
    for datum in datum_definition:
        if datum in vertical_datum_name.lower():
            guess_list.append(datum)
    if len(guess_list) == 1:
        return guess_list[0]
    elif len(guess_list) == 0:
        return None
    else:
        raise ValueError(f'More than one datum guess found in {vertical_datum_name}')

def get_transformation_pipeline(in_crs: VerticalPipelineCRS, out_crs: VerticalPipelineCRS, region: str, is_alaska: bool = False):
    """
    Use the datum name in the input/output crs and the region specified to build the pipeline between the two
    provided CRS.  This means that the datum names of the two crs must be in the datum_definition dictionary.

    Also the region provided must be in the list of regions in both crs objects, unless that crs object is nad83.

    Parameters
    ----------
    in_crs
        VerticalPipelineCRS object representing the start point in the transformation
    out_crs
        VerticalPipelineCRS object representing the end point in the transformation
    region
        name of the vdatum folder for the region of interest, ex: NYNJhbr34_8301
    is_alaska
        # if True, regions are in alaska, which means we need to do a string replace to go to xgeoid17b

    Returns
    -------
    str
        PROJ pipeline string specifying the vertical transformation between source incrs and outcrs
    """

    if in_crs.datum_name.lower() not in datum_definition.keys():
        raise NotImplementedError(f'Unable to build pipeline, datum name not in the datum definition dict, {in_crs.datum_name} not in {list(datum_definition.keys())}')
    # nad83 is a special case, there would be no transformation there as it is the pivot datum, all regions (assuming nad83 bounds) are valid
    if region not in in_crs.regions and in_crs.datum_name.lower() != 'nad83':
        raise NotImplementedError(f'Unable to build pipeline, region not in input CRS: {region}')

    if out_crs.datum_name.lower() not in datum_definition.keys():
        raise NotImplementedError(f'Unable to build pipeline, datum name not in the datum definition dict, {out_crs.datum_name} not in {list(datum_definition.keys())}')
    if region not in out_crs.regions and out_crs.datum_name.lower() != 'nad83':
        raise NotImplementedError(f'Unable to build pipeline, region not in output CRS: {region}')

    return get_regional_pipeline(in_crs.datum_name, out_crs.datum_name, region, is_alaska=is_alaska)


if __name__ == '__main__':
    vs = VerticalPipelineCRS("NOAA Chart Datum")
    vs.add_pipeline(
        "proj=pipeline step proj=vgridshift grids=core\\geoid12b\\g2012bu0.gtx step proj=vgridshift grids=REGION\\tss.gtx",
        "TXlagmat01_8301")
    vs.add_pipeline(
        "proj=pipeline step proj=vgridshift grids=core\\geoid12b\\g2012bu0.gtx step proj=vgridshift grids=REGION\\tss.gtx",
        "TXlaggal01_8301")

    vstwo = VerticalPipelineCRS("nad83")
    vstwo.add_pipeline(
        "proj=pipeline step proj=vgridshift grids=core\\geoid12b\\g2012bu0.gtx step proj=vgridshift grids=REGION\\tss.gtx proj=vgridshift grids=regionname\\mllw.gtx",
        "TXlagmat01_8301")
    vstwo.add_pipeline(
        "proj=pipeline step proj=vgridshift grids=core\\geoid12b\\g2012bu0.gtx step proj=vgridshift grids=REGION\\tss.gtx proj=vgridshift grids=regionname\\mllw.gtx",
        "TXlaggal01_8301")

    print(vs.to_pretty_wkt())
    print(get_transformation_pipeline(vs, vstwo, "TXlagmat01_8301"))
