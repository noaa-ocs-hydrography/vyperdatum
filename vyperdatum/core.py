import os, sys, glob, configparser
import numpy as np
from pyproj import Transformer, datadir, CRS
from osgeo import gdal, ogr
from typing import Any, Union
import logging
from datetime import datetime

from vyperdatum.vypercrs import VerticalPipelineCRS, get_transformation_pipeline
from vyperdatum.pipeline import get_regional_pipeline


class VyperCore:
    """
    The core object for conducting transformations.  Contains all the information built automatically from the vdatum
    distribution, including paths to gtx files and uncertainty per grid.  VyperCore uses this information to provide
    a transformation method to go from source datum to EPSG with a vertical or 3d transformation, depending on
    source datum.

    vc = VyperCore()
    vc.set_region_by_bounds(-75.79179, 35.80674, -75.3853, 36.01585)

    # choose one of these
    # a 3d transformation from state plane to NAD83/MLLW
    vc.set_input_datum(3631)
    # a vertical transformation from NAD83/ELHeight to NAD83/MLLW
    vc.set_input_datum('nad83')

    vc.set_output_datum('mllw')
    x = np.array([898745.505, 898736.854, 898728.203])
    y = np.array([256015.372, 256003.991, 255992.610])
    z = np.array([10.5, 11.0, 11.5])
    newx, newy, newz, newunc = vc.transform_dataset(x, y, z)

    """

    def __init__(self, vdatum_directory: str = None, logfile: str = None, silent: bool = False):
        # if vdatum_directory is provided initialize VdatumData with that path
        self.vdatum = VdatumData(vdatum_directory=vdatum_directory, parent=self)
        self.silent = silent

        self.min_x = None
        self.min_y = None
        self.max_x = None
        self.max_y = None

        self.geographic_min_x = None
        self.geographic_min_y = None
        self.geographic_max_x = None
        self.geographic_max_y = None

        self.in_crs = None
        self.out_crs = None
        self.base_horiz_crs = None

        self.logger = return_logger(logfile)
        self.regions = []

    def log_error(self, msg, exception=None):
        self.logger.error(msg)
        if exception:
            raise exception(msg)

    def log_warning(self, msg):
        if not self.silent:
            self.logger.warning(msg)

    def log_info(self, msg):
        if not self.silent:
            self.logger.info(msg)

    def log_debug(self, msg):
        if not self.silent:
            self.logger.debug(msg)

    def close(self):
        # we want this to wait till all handlers are closed, it seems like you have to make multiple passes sometimes
        # maybe a waiting for threads to terminate thing
        while self.logger.handlers:
            for handler in self.logger.handlers:
                handler.close()
                self.logger.removeHandler(handler)
        self.logger = None

    def base_to_geographic_extents(self, input_datum: int):
        """
        An additional task is run on setting the input datum.  We first need to determine the nad83 geographic coordinates
        to determine which vdatum regions apply (set_region_by_bounds).  Afterwards we call the vypercore set_input_datum
        process.

        Parameters
        ----------
        input_datum
            EPSG code for the input datum of the raster
        """

        if not self.min_x or not self.min_y or not self.max_x or not self.max_y:
            self.log_error('You must set min/max extents first, before setting input datum, as we transform the extents here', ValueError)

        # epsg which lets us transform, otherwise assume raster extents are geographic
        # transform the raster extents so we can use them to find the vdatum regions
        transformer = Transformer.from_crs(CRS.from_epsg(input_datum), CRS.from_epsg(6319), always_xy=True)
        self.geographic_min_x, self.geographic_min_y, _ = transformer.transform(self.min_x, self.min_y, 0)
        self.geographic_max_x, self.geographic_max_y, _ = transformer.transform(self.max_x, self.max_y, 0)
        self.set_region_by_bounds(self.geographic_min_x, self.geographic_min_y, self.geographic_max_x,
                                  self.geographic_max_y)

    def set_region_by_bounds(self, x_min: float, y_min: float, x_max: float, y_max: float):
        """
        Set the regions that intersect with the provided bounds and store a list of region names that overlap.

        Parameters
        ----------
        x_min
            the minimum longitude of the area of interest
        y_min
            the minimum latitude of the area of interest
        x_max
            the maximum longitude of the area of interest
        y_max
            the maximum latitude of the area of interest
        """

        assert x_min < x_max
        assert y_min < y_max

        # build corners from the provided bounds
        ul = (x_min, y_max)
        ur = (x_max, y_max)
        lr = (x_max, y_min)
        ll = (x_min, y_min)

        # build polygon from corners
        ring = ogr.Geometry(ogr.wkbLinearRing)
        ring.AddPoint(ul[0], ul[1])
        ring.AddPoint(ur[0], ur[1])
        ring.AddPoint(lr[0], lr[1])
        ring.AddPoint(ll[0], ll[1])
        ring.AddPoint(ul[0], ul[1])
        data_geometry = ogr.Geometry(ogr.wkbPolygon)
        data_geometry.AddGeometry(ring)

        # see if the regions intersect with the provided geometries
        intersecting_regions = []
        for region in self.vdatum.polygon_files:
            vector = ogr.Open(self.vdatum.polygon_files[region])
            layer_count = vector.GetLayerCount()
            for m in range(layer_count):
                layer = vector.GetLayerByIndex(m)
                feature_count = layer.GetFeatureCount()
                for n in range(feature_count):
                    feature = layer.GetFeature(n)
                    feature_name = feature.GetField(0)
                    if feature_name[:15] == 'valid-transform':
                        valid_vdatum_poly = feature.GetGeometryRef()
                        if data_geometry.Intersect(valid_vdatum_poly):
                            intersecting_regions.append(region)
                    feature = None
                layer = None
            vector = None
        self.regions = intersecting_regions

    def is_alaska(self):
        """
        A somewhat weak implementation of a method to determine if these regions are in alaska.  Currently, alaskan
        tidal datums are based on xgeoid18, so we need to identify those regions to ensure we use the correct geoid
        during transformation.

        Could probably just use the geographic bounds, but this method works and is less expensive.

        Returns
        -------
        bool
            True if regions are in alaska
        """

        if self.regions:
            is_alaska = all([t.find('AK') != -1 for t in self.regions])
            is_not_alaska = all([t.find('AK') == -1 for t in self.regions])
            if not is_alaska and not is_not_alaska:
                self.log_error('Regions in and not in alaska specified, not currently supported', NotImplementedError)
            if is_alaska:
                return True
            else:
                return False
        else:
            self.log_error('No regions specified, unable to determine is_alaska', ValueError)

    def _build_datum_from_string(self, datum: str):
        """
        We build a CRS for the input and output datum.  You can pass in a prebuilt VerticalPipelineCRS, or use this
        method to build one automatically.

        Parameters
        ----------
        datum
            string identifier for datum, see pipeline.datum_definition keys for possible options

        Returns
        -------
        VerticalPipelineCRS
            constructed CRS for the datum provided
        """

        if self.regions:
            new_crs = VerticalPipelineCRS(datum)
            for r in self.regions:
                new_pipeline = get_regional_pipeline('nad83', datum, r, is_alaska=self.is_alaska())
                if new_pipeline:
                    new_crs.add_pipeline(new_pipeline, r)
            return new_crs
        else:
            self.log_error('No Vdatum regions found, data is probably out of bounds', ValueError)

    def _transform_to_nad83(self, source_epsg: int, x: np.array, y: np.array, z: np.array = None):
        """
        NAD83 is our pivot datum in vyperdatum.  In order to do a vertical transform, we need to first get to NAD83
        if we aren't there already.  We assume that if you are not at NAD83, you are providing an integer EPSG code,
        which triggers this method.

        Here we use the Transformer object to do a 3d (if EPSG is 3d coordinate system) or 2d transformation to
        6319, which is 3d NAD83 (2011).  If the transformation is 3d, you'll get a z value which is the sep between
        source and 6319.  Otherwise z will be unchanged.

        Parameters
        ----------
        source_epsg
            The coordinate system of the input data, as EPSG
        x
            longitude/easting of the input data
        y
            latitude/northing of the input data
        z
            depth value of the input data

        Returns
        -------
        x
            longitude/easting of the input data, transformed to NAD83(2011)
        y
            latitude/northing of the input data, transformed to NAD83(2011)
        z
            depth value of the input data, transformed to NAD83(2011)
        """

        in_crs = CRS.from_epsg(source_epsg)
        out_crs = CRS.from_epsg(6319)
        # Transformer.transform input order is based on the CRS, see CRS.geodetic_crs.axis_info
        # - lon, lat - this appears to be valid when using CRS from proj4 string
        # - lat, lon - this appears to be valid when using CRS from epsg
        # use the always_xy option to force the transform to expect lon/lat order
        transformer = Transformer.from_crs(in_crs, out_crs, always_xy=True)

        if z is None:
            z = np.zeros_like(x)
        x, y, z = transformer.transform(x, y, z)
        return x, y, z

    def set_input_datum(self, input_datum: Union[str, int], vertical: str = None, extents: tuple = None):
        """
        Construct the input datum, using the provided identifier.  If EPSG (int) is provided, will store the source
        in self.base_horiz_crs to do a 3d/2d transformation later and assume that the input datum will be at NAD83,
        unless you use vertical='mllw' for example.

        Parameters
        ----------
        input_datum
            Either EPSG code, or datum identifier string, see pipeline.datum_definition keys for possible options for string
        vertical
            Optional, if the user enters a 2d epsg for input datum, we assume the input vertical datum is NAD83 elheight.
            Use this to force a vertical datum other than ellipsoid height, see pipeline.datum_definition keys for possible
            options for string
        extents
            Optional, if an epsg code is provided, we assume the user wants to do a 2d transformation.  That means either
            the min/max values must have been set previously, or they must be provided here.
        """

        if extents:
            self.min_x, self.min_y, self.max_x, self.max_y = extents
        if isinstance(input_datum, int):
            if not (self.min_x or self.min_y or self.max_x or self.max_y):
                self.log_error('No min/max values found, must provide extents here if you use an EPSG code that requires a 2d transformation', ValueError)
            self.base_to_geographic_extents(input_datum)
            self.base_horiz_crs = input_datum
            if vertical:
                input_datum = vertical
            else:
                input_datum = 'NAD83'
        else:
            self.geographic_min_x, self.geographic_min_y = self.min_x, self.min_y
            self.geographic_max_x, self.geographic_max_y = self.max_x, self.max_y
            self.base_horiz_crs = None
        try:
            incrs = VerticalPipelineCRS()
            incrs.from_wkt(input_datum)
        except ValueError:
            incrs = self._build_datum_from_string(input_datum)
        self.in_crs = incrs

    def set_output_datum(self, output_datum: str):
        """
        Construct the output datum, using the provided identifier.

        Parameters
        ----------
        output_datum
            datum identifier string, see pipeline.datum_definition keys for possible options for string
        """
        try:
            outcrs = VerticalPipelineCRS()
            outcrs.from_wkt(output_datum)
        except ValueError:
            outcrs = self._build_datum_from_string(output_datum)
        self.out_crs = outcrs

    def _run_pipeline(self, x, y, pipeline, z=None):
        """
        Helper method for running the transformer pipeline operation on the provided data.

        Parameters
        ----------
        x
            longitude of the input data
        y
            latitude of the input data
        pipeline
            string containing the pipeline information
        z
            optional, depth value of the input data, if not provided will use all zeros

        Returns
        -------
        tuple
            tuple of transformed x, y, z
        """

        if z is None:
            z = np.zeros(len(x))
        assert len(x) == len(y) and len(y) == len(z)

        # get the transform at the sparse points
        transformer = Transformer.from_pipeline(pipeline)
        result = transformer.transform(xx=x, yy=y, zz=z)
        return result

    def _get_output_uncertainty(self, region: str):
        """
        Get the output uncertainty for each point by reading the vdatum_sigma.inf file and combining the uncertainties
        that apply for this region.

        Currently we use the output datum pipeline as the source of uncertainty.  Might
        be better to use the transformation pipeline instead.  The way it currently works, if your output datum is NAD83,
        there would be no pipeline (as nad83 is the pivot datum) and so you would have 0 uncertainty, even if you did transform
        from MLLW to NAD83.

        Parameters
        ----------
        region
            region name as string

        Returns
        -------
        float
            uncertainty associated with each transformed point
        """

        if not self.out_crs.pipeline_string:  # if nad83 is the output datum, no transformation is done
            return 0
        final_uncertainty = 0
        layer_names = ['lmsl', 'mhhw', 'mhw', 'mtl', 'dtl', 'mlw', 'mllw']
        for lyr in layer_names:
            if self.out_crs.pipeline_string.find(lyr) != -1:
                final_uncertainty += self.vdatum.uncertainties[region][lyr]

        if self.out_crs.pipeline_string.find('geoid12b') != -1:
            final_uncertainty += self.vdatum.uncertainties['geoid12b']
        elif self.out_crs.pipeline_string.find('xgeoid18b') != -1:
            final_uncertainty += self.vdatum.uncertainties['xgeoid18b']
        else:
            self.log_error('Unable to find either geoid12b or xgeoid18b in the output datum pipeline, which geoid is used?', ValueError)
        return final_uncertainty

    def transform_dataset(self, x: np.array, y: np.array, z: np.array = None, include_vdatum_uncertainty: bool = True,
                          include_region_index: bool = False):
        """
        Transform all points provided here for each vdatum grid file that overlaps the overall extents of the input data.

        If an EPSG code was provided to set_input_datum, does an optional 2d/3d transformation to NAD83(2011).

        Parameters
        ----------
        x
            longitude of the input data
        y
            latitude of the input data
        z
            optional, depth value of the input data, if not provided will use all zeros include_vdatum_uncertainty
        include_vdatum_uncertainty
            if True, will return the combined separation uncertainty for each point
        include_region_index
            if True, will return the integer index of the region used for each point

        Returns
        -------
        tuple
            contains: transformed x value (if EPSG code is provided, else original x value),
                      transformed y value (if EPSG code is provided, else original y value),
                      transformed z value,
                      combined uncertainty for each vdatum layer if include_vdatum_uncertainty, otherwise None,
                      region index for each vdatum layer if include_region_index, otherwise None
        """
        if self.regions:
            if self.base_horiz_crs:
                x, y, z = self._transform_to_nad83(self.base_horiz_crs, x, y, z)
            ans_x = np.full_like(x, np.nan)
            ans_y = np.full_like(y, np.nan)
            if z is None:
                z = np.zeros(len(x))
            ans_z = np.full_like(z, np.nan)
            if include_vdatum_uncertainty:
                ans_unc = np.full_like(z, np.nan)
            else:
                ans_unc = None
            if include_region_index:
                ans_region = np.full(z.shape, -1, dtype=np.int8)
            else:
                ans_region = None

            for cnt, region in enumerate(self.regions):
                # get the pipeline
                pipeline = get_transformation_pipeline(self.in_crs, self.out_crs, region, self.is_alaska())
                if pipeline:
                    tmp_x, tmp_y, tmp_z = self._run_pipeline(x, y, pipeline, z=z)
                else:
                    tmp_x, tmp_y, tmp_z = x, y, z

                # areas outside the coverage of the vert shift are inf
                valid_index = ~np.isinf(tmp_z)
                ans_x[valid_index] = tmp_x[valid_index]
                ans_y[valid_index] = tmp_y[valid_index]
                ans_z[valid_index] = tmp_z[valid_index]
                if include_vdatum_uncertainty:
                    ans_unc[valid_index] = self._get_output_uncertainty(region)
                if include_region_index:
                    ans_region[valid_index] = cnt
            self.log_info(f'transformed {len(ans_z)} points from {self.in_crs.datum_name} to {self.out_crs.datum_name}')
            return ans_x, ans_y, np.round(ans_z, 3), ans_unc, ans_region
        else:
            self.log_error('No regions specified, unable to transform points', ValueError)


class VdatumData:
    """
    Gets and maintains VDatum information for use with Vyperdatum.
    
    The VDatum path location is stored in a config file which is in the user's directory.  Use configparser to sync
    self._config and the ini file.

    Optionally, user may provide a vdatum directory here on initialization to set the vdatum path the first time
    """

    def __init__(self, vdatum_directory: str = None, parent=None):
        self.parent = parent

        self.grid_files = {}  # dict of file names to file paths for the gtx files
        self.polygon_files = {}  # dict of file names to file paths for the kml files
        self.uncertainties = {}  # dict of file names to uncertainties for each grid
        self.vdatum_path = ''  # path to the parent vdatum folder

        self._config = {}  # dict of all the settings
        self.config_path_file = ''  # path to the config file that maintains the settings between runs

        self._get_stored_vdatum_config()
        if vdatum_directory:  # overwrite the loaded path if you want to change it on initialization
            self.set_vdatum_directory(vdatum_directory)
        else:
            self.set_vdatum_directory(self.vdatum_path)

    def set_config(self, ky: str, value: Any):
        """
        Setter for the _config attribute.  Use this instead of setting _config directly, will set both the _config
        key/value and the configparser ini file.

        Parameters
        ----------
        ky
            key to set in the dict
        value
            value to set in the dict
        """

        try:
            config = configparser.ConfigParser()
            config.read(self.config_path_file)
            for k, v in self._config.items():
                config['Default'][k] = v

            self._config[ky] = value  # set the class attribute
            config['Default'][ky] = value  # set the ini matching attribute
            with open(self.config_path_file, 'w') as configfile:
                config.write(configfile)
        except:
            # get a number of exceptions here when reading and writing to the config file in multiprocessing
            if self.parent:
                self.parent.log_warning('Unable to set {} in config file {}'.format(ky, self.config_path_file))
        if ky == 'vdatum_path':
            self.vdatum_path = value

    def _get_stored_vdatum_config(self):
        """
        Runs on initialization, will read from the ini file and set the vdatum path, config attribute
        """
        vyperdatum_folder = os.path.join(os.path.expanduser('~'), 'vyperdatum')
        self.config_path_file = os.path.join(vyperdatum_folder, 'vdatum.config')
        # get the config
        if os.path.exists(self.config_path_file):
            self._config = self._read_from_config_file()
        else:
            default_vdatum_path = os.path.join(os.path.splitdrive(sys.executable)[0], '/VDatum')
            self._config = self._create_new_config_file({'vdatum_path': default_vdatum_path})
        self.vdatum_path = self._config['vdatum_path']
            
    def _read_from_config_file(self):
        """
        Read from the generated configparser file path, set the object vdatum 
        settings.
    
        Returns
        -------
        dict
            dictionary of settings
        """
    
        settings = {}
        config_file = configparser.ConfigParser()
        config_file.read(self.config_path_file)
        sections = config_file.sections()
        for section in sections:
            config_file_section = config_file[section]
            for key in config_file_section:
                settings[key] = config_file_section[key]
        return settings

    def _create_new_config_file(self, default_settings: dict) -> dict:
        """
        Create a new configparser file, return the settings and the configparser object
    
        Parameters
        ----------
        default_settings
            default settings we want to write to the configparser file
    
        Returns
        -------
        configparser.ConfigParser
            configparser object used to read the file
        dict
            settings within the file
        """
        config_folder, config_file = os.path.split(self.config_path_file)
        if not os.path.exists(config_folder):
            os.mkdir(config_folder)
        config = configparser.ConfigParser()
        config['Default'] = default_settings
        with open(self.config_path_file, 'w') as configfile:
            config.write(configfile)
        return default_settings

    def set_vdatum_directory(self, vdatum_path: str):
        """
        Called when self.settings['vdatum_directory'] is updated.  We find all the grids and polygons in the vdatum
        directory and save the dicts to the attributes in this class.
        """
        self.set_config('vdatum_path', vdatum_path)
        if not os.path.exists(self.vdatum_path):
            raise ValueError(f'VDatum is not found at the provided path: {self.vdatum_path}')

        # special case for vdatum directory, we want to give pyproj the new path if it isn't there already
        orig_proj_paths = datadir.get_data_dir()
        if vdatum_path not in orig_proj_paths:
            datadir.append_data_dir(vdatum_path)
    
        # also want to populate grids and polygons with what we find
        self.grid_files = get_gtx_grid_list(vdatum_path)
        self.polygon_files = get_vdatum_region_polygons(vdatum_path)
        self.uncertainties = get_vdatum_uncertainties(vdatum_path)

        self.vdatum_path = self._config['vdatum_path']


def get_gtx_grid_list(vdatum_directory: str):
    """
    Search the vdatum directory to find all gtx files

    Parameters
    ----------
    vdatum_directory
        absolute folder path to the vdatum directory

    Returns
    -------
    dict
        dictionary of {grid name: grid path, ...}
    """

    search_path = os.path.join(vdatum_directory, '*/*.gtx')
    gtx_list = glob.glob(search_path)
    if len(gtx_list) == 0:
        errmsg = f'No GTX files found in the provided VDatum directory: {vdatum_directory}'
        print(errmsg)
    grids = {}
    for gtx in gtx_list:
        gtx_path, gtx_file = os.path.split(gtx)
        gtx_path, gtx_folder = os.path.split(gtx_path)
        gtx_name = '/'.join([gtx_folder, gtx_file])
        gtx_subpath = os.path.join(gtx_folder, gtx_file)
        grids[gtx_name] = gtx_subpath
    return grids


def get_vdatum_region_polygons(vdatum_directory: str):
    """"
    Search the vdatum directory to find all kml files

    Parameters
    ----------
    vdatum_directory
        absolute folder path to the vdatum directory

    Returns
    -------
    dict
        dictionary of {kml name: kml path, ...}
    """

    search_path = os.path.join(vdatum_directory, '*/*.kml')
    kml_list = glob.glob(search_path)
    if len(kml_list) == 0:
        errmsg = f'No kml files found in the provided VDatum directory: {vdatum_directory}'
        print(errmsg)
    geom = {}
    for kml in kml_list:
        kml_path, kml_file = os.path.split(kml)
        root_dir, kml_name = os.path.split(kml_path)
        geom[kml_name] = kml
    return geom


def get_vdatum_uncertainties(vdatum_directory: str):
    """"
    Parse the sigma file to build a dictionary of gridname: uncertainty for each layer.

    Parameters
    ----------
    vdatum_directory
        absolute folder path to the vdatum directory

    Returns
    -------
    dict
        dictionary of {kml name: kml path, ...}
    """
    acc_file = os.path.join(vdatum_directory, 'vdatum_sigma.inf')

    # use the polygon search to get a dict of all grids quickly
    grid_dict = get_vdatum_region_polygons(vdatum_directory)
    for k in grid_dict.keys():
        grid_dict[k] = {'lmsl': 0, 'mhhw': 0, 'mhw': 0, 'mtl': 0, 'dtl': 0, 'mlw': 0, 'mllw': 0}
    # add in the geoids we care about
    grid_entries = list(grid_dict.keys())

    with open(acc_file, 'r') as afil:
        for line in afil.readlines():
            data = line.split('=')
            if len(data) == 2:  # a valid line, ex: nynjhbr.lmsl=1.4
                data_entry, val = data
                sub_data = data_entry.split('.')
                if len(sub_data) == 2:
                    prefix, suffix = sub_data  # flpensac.mhw=1.8
                # elif len(sub_data) == 3:
                #     prefix, _, suffix = sub_data  # akyakutat.lmsl.mhhw=6.6
                    if prefix == 'conus':
                        if suffix == 'navd88':
                            grid_dict['geoid12b'] = float(val) * 0.01  # answer in meters
                        elif suffix == 'xgeoid18b':
                            grid_dict['xgeoid18b'] = float(val) * 0.01
                    else:
                        match = np.where(np.array([entry.lower().find(prefix) for entry in grid_entries]) == 0)
                        if match[0].size:
                            if len(match[0]) > 1:
                                raise ValueError(f'Found multiple matches in vdatum_sigma file for entry {data_entry}')
                            elif match:
                                grid_key = grid_entries[match[0][0]]
                                val = val.lstrip().rstrip()
                                if val == 'n/a':
                                    val = 0
                                grid_dict[grid_key][suffix] = float(val) * 0.01
                            else:
                                print(f'No match for vdatum_sigma entry {data_entry}!')
    return grid_dict


class StdErrFilter(logging.Filter):
    """
    filter out messages that are not CRITICAL or ERROR or WARNING
    """
    def filter(self, rec):
        return rec.levelno in (logging.CRITICAL, logging.ERROR, logging.WARNING)


class StdOutFilter(logging.Filter):
    """
    filter out messages that are not DEBUG or INFO
    """
    def filter(self, rec):
        return rec.levelno in (logging.DEBUG, logging.INFO)


def return_logger(logfile: str = None):
    """
    I disable the root logger by clearing out it's handlers because it always gets a default stderr log handler that
    ends up duplicating messages.  Since I want the stderr messages formatted nicely, I want to setup that handler \
    myself.

    Parameters
    ----------
    logfile: str, path to the log file where you want the output driven to

    Returns
    -------
    logger: logging.Logger instance for the provided name/logfile

    """
    fmat = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    if logfile:
        logger = logging.getLogger(logfile)
    else:
        nowtime = datetime.now().strftime('%Y%m%d_%H%M%S')
        logger = logging.getLogger(f'vyperdatum_{nowtime}')
    logger.setLevel(logging.INFO)

    consolelogger = logging.StreamHandler(sys.stdout)
    consolelogger.setLevel(logging.INFO)
    #consolelogger.setFormatter(logging.Formatter(fmat))
    consolelogger.addFilter(StdOutFilter())

    errorlogger = logging.StreamHandler(sys.stderr)
    errorlogger.setLevel(logging.WARNING)
    #errorlogger.setFormatter(logging.Formatter(fmat))
    errorlogger.addFilter(StdErrFilter())

    logger.addHandler(consolelogger)
    logger.addHandler(errorlogger)

    if logfile is not None:
        filelogger = logging.FileHandler(logfile)
        filelogger.setLevel(logging.INFO)
        filelogger.setFormatter(logging.Formatter(fmat))
        logger.addHandler(filelogger)

    # eliminate the root logger handlers, it will have a default stderr pointing handler that ends up duplicating all the logs to console
    logging.getLogger().handlers = []

    return logger
