import os, sys, glob, configparser, hashlib
import numpy as np
from pyproj import Transformer, datadir, CRS
from osgeo import gdal, ogr
from typing import Any, Union
import logging
from datetime import datetime

from vyperdatum.vypercrs import VyperPipelineCRS, get_transformation_pipeline, is_alaska, geoid_frame, geoid_possibilities, \
    frame_to_3dcrs
from vyperdatum.vdatum_validation import vdatum_hashlookup, vdatum_geoidlookup


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
        self.silent = silent
        self.vdatum = VdatumData(vdatum_directory=vdatum_directory, parent=self)

        self.min_x = None
        self.min_y = None
        self.max_x = None
        self.max_y = None

        self.geographic_min_x = None
        self.geographic_min_y = None
        self.geographic_max_x = None
        self.geographic_max_y = None

        self.in_crs = VyperPipelineCRS()
        self.out_crs = VyperPipelineCRS()

        self.logger = return_logger(logfile)
        self._regions = []
        self._geoid_frame = None
        self.pipelines = []
        
    @property
    def is_alaska(self):
        ak = False
        if len(self._regions) > 0:
            ak = is_alaska(self._regions)
        return ak
    
    @property
    def regions(self):
        return self._regions
    
    @regions.setter
    def regions(self, new_regions: list):
        if type(new_regions) == list:
            self._regions = new_regions
            self._in_crs.update_regions(new_regions)
            self._out_crs.update_regions(new_regions)

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

    def set_region_by_bounds(self, x_min: float, y_min: float, x_max: float, y_max: float):
        """
        Set the regions that intersect with the provided bounds and store a list of region names that overlap.
        This input corrdinate reference system is expected to be NAD83(2011) geographic.

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
                            gframe = geoid_frame[vdatum_geoidlookup[self.vdatum.vdatum_version][region]]
                            if self._geoid_frame and self._geoid_frame != gframe:
                                raise NotImplementedError(f'Found two different geoid reference frames in the intersecting regions: {self._geoid_frame}, {gframe}')
                            self._geoid_frame = gframe
                    feature = None
                layer = None
            vector = None
        self._regions = intersecting_regions
        self.in_crs.update_regions(intersecting_regions)
        self.out_crs.update_regions(intersecting_regions)
        
    def _set_region_by_extents(self):
        self.set_region_by_bounds(self.geographic_min_x,
                                  self.geographic_min_y,
                                  self.geographic_max_x,
                                  self.geographic_max_y)
        
    def _set_extents(self, extents: tuple):
        """
        set the object horizontal extents using the input tuple.  The geographic extents
        are set as well.

        Parameters
        ----------
        extents : tuple
            The object horizontal extents in the input crs as (min_x, min_y, max_x, max_y).

        Returns
        -------
        None.

        """
        self.min_x, self.min_y, self.max_x, self.max_y = extents
        gframe = self._geoid_frame
        in_horiz_name = self.in_crs.horizontal.name
        if in_horiz_name != gframe:
            x = [self.min_x, self.max_x]
            y = [self.min_y, self.max_y]
            z = [0, 0]
            x_geo, y_geo, z_geo = self._transform_to_geoid_frame(x, y, z)
            self.geographic_min_x, self.geographic_max_x = x_geo
            self.geographic_min_y, self.geographic_max_y = y_geo
        else:
            self.geographic_min_x = self.min_x
            self.geographic_max_x = self.max_x
            self.geographic_min_y = self.min_y
            self.geographic_max_y = self.max_y

    def _transform_to_geoid_frame(self, x: np.array, y: np.array, z: np.array = None):
        """
        In order to do a vertical transform, we need to first get to the geoid reference frame if we aren't there
        already.  See set_region_by_bounds for where that geoid frame attribute gets set.  Basically we look at the
        regions of interest to figure out the correct geoid frame.

        Here we use the Transformer object to do a 3d (if EPSG is 3d coordinate system) or 2d transformation to
        the geoid frame.  If the transformation is a valid 3d, you'll get a z value which is the sep between
        source and geoid frame.  Otherwise z will be unchanged.

        Parameters
        ----------
        x
            longitude/easting of the input data
        y
            latitude/northing of the input data
        z
            height value of the input data

        Returns
        -------
        x
            longitude/easting of the input data, transformed to NAD83(2011)
        y
            latitude/northing of the input data, transformed to NAD83(2011)
        z
            height value of the input data, transformed to NAD83(2011)
        """

        in_crs = self.in_crs.horizontal.to_epsg()
        out_crs = frame_to_3dcrs[self._geoid_frame]
        # Transformer.transform input order is based on the CRS, see CRS.geodetic_crs.axis_info
        # - lon, lat - this appears to be valid when using CRS from proj4 string
        # - lat, lon - this appears to be valid when using CRS from epsg
        # use the always_xy option to force the transform to expect lon/lat order
        transformer = Transformer.from_crs(in_crs, out_crs, always_xy=True)

        if z is None:
            z = np.zeros_like(x)
        x, y, z = transformer.transform(x, y, z)

        return x, y, z

    def set_input_datum(self, input_datum: Union[str, int, tuple], extents: tuple = None):
        """
        Construct the input datum as a vypercrs.VyperPipeline object, using the provided identifier(s).

        Parameters
        ----------
        input_datum
            Either EPSG code, wkt, datum identifier string, or tuple of two of these.  
            See vypercrs.VyperPipelineCRS and pipeline.datum_definition for possible options for string

        extents
            Optional. Used to define the transform pipeline regions.
        """

        self.in_crs.set_crs(input_datum)
        if extents:
            self._set_extents(extents)
            self._set_region_by_extents()
        if self.in_crs.horizontal and not self.out_crs.horizontal:
            self.set_output_datum(self.in_crs.horizontal.to_wkt())

    def set_output_datum(self, output_datum: Union[str, int, tuple]):
        """
        Construct the output datum, using the provided identifier(s).

        Parameters
        ----------
        output_datum
            Either EPSG code, wkt, datum identifier string, or tuple of two of these.  
            See vypercrs.VyperPipelineCRS and pipeline.datum_definition for possible options for string
        """
        self.out_crs.set_crs(output_datum)

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
            optional, height value of the input data, if not provided will use all zeros

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

        geoid_search = [gd for gd in geoid_possibilities if self.out_crs.pipeline_string.find(gd) != -1]
        if len(geoid_search) != 1:
            self.log_error(f'Found {len(geoid_search)} geoid possibilities in pipeline string', ValueError)
        else:
            final_uncertainty += self.vdatum.uncertainties[geoid_search[0]]

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
            optional, height or depth value of the input data, if not provided will use all zeros include_vdatum_uncertainty
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
        if not self.min_x:
            extents = (min(x), min(y), max(x), max(y))
            self._set_extents(extents)
        if len(self._regions) == 0:
            self._set_region_by_extents()
        if len(self._regions) > 0:
            if not self.in_crs.is_valid:
                self.log_error('Input datum insufficently specified', ValueError)
            if not self.out_crs.is_valid:
                self.log_error('Output datum insufficently specified', ValueError)

            if z is not None and not self.in_crs.is_height:
                z *= -1
            if self.out_crs.is_height:
                flip = 1
            else:
                flip = -1

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

            self.pipelines = []
            for cnt, region in enumerate(self._regions):
                # get the pipeline
                gframe = self._geoid_frame
                in_horiz_name = self.in_crs.horizontal.name
                if in_horiz_name != gframe:
                    x, y, z = self._transform_to_geoid_frame(x, y, z)
                pipeline = get_transformation_pipeline(self.in_crs, self.out_crs, region, self.is_alaska)
                if pipeline:
                    tmp_x, tmp_y, tmp_z = self._run_pipeline(x, y, pipeline, z=z)
                    self.pipelines.append(pipeline)
                else:
                    tmp_x, tmp_y, tmp_z = x, y, z

                # areas outside the coverage of the vert shift are inf
                valid_index = ~np.isinf(tmp_z)
                ans_x[valid_index] = tmp_x[valid_index]
                ans_y[valid_index] = tmp_y[valid_index]
                ans_z[valid_index] = flip * tmp_z[valid_index]
                if include_vdatum_uncertainty:
                    ans_unc[valid_index] = self._get_output_uncertainty(region)
                if include_region_index:
                    ans_region[valid_index] = cnt
            self.log_info(f'transformed {len(ans_z)} points from {self.in_crs.vyperdatum_str} to {self.out_crs.vyperdatum_str}')
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

        self.regions = []
        self.grid_files = {}  # dict of file names to file paths for the gtx files
        self.polygon_files = {}  # dict of file names to file paths for the kml files
        self.uncertainties = {}  # dict of file names to uncertainties for each grid
        self.vdatum_path = ''  # path to the parent vdatum folder
        self.vdatum_version = ''

        self._config = {'vdatum_path': ''}  # dict of all the settings
        self.config_path_file = ''  # path to the config file that maintains the settings between runs

        self._get_stored_vdatum_config()
        if vdatum_directory:  # overwrite the loaded path if you want to change it on initialization
            self.set_vdatum_directory(vdatum_directory)
        else:
            self.set_vdatum_directory(self.vdatum_path)
        self.get_vdatum_version()

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
            try:
                if self.parent:
                    self.parent.log_warning('Unable to set {} in config file {}'.format(ky, self.config_path_file))
            except AttributeError:  # logger not initialized yet
                print('WARNING: Unable to set {} in config file {}'.format(ky, self.config_path_file))
        if ky == 'vdatum_path':
            self.vdatum_path = value

    def _get_stored_vdatum_config(self):
        """
        Runs on initialization, will read from the ini file and set the vdatum path, config attribute
        """
        try:
            vyperdatum_folder = os.path.join(os.path.expanduser('~'), 'vyperdatum')
            self.config_path_file = os.path.join(vyperdatum_folder, 'vdatum.config')
            # get the config
            if os.path.exists(self.config_path_file):
                self._config = self._read_from_config_file()
            else:
                default_vdatum_path = os.path.join(os.path.splitdrive(sys.executable)[0], '/VDatum')
                self._config = self._create_new_config_file({'vdatum_path': default_vdatum_path})
            self.vdatum_path = self._config['vdatum_path']
        except:
            # get a number of exceptions here when reading and writing to the config file in multiprocessing
            try:
                if self.parent:
                    self.parent.log_warning('Unable to read from existing config file {}'.format(self.config_path_file))
            except AttributeError:  # logger not initialized yet
                print('WARNING: Unable to read from existing config file {}'.format(self.config_path_file))
            
    def _read_from_config_file(self):
        """
        Read from the generated configparser file path, set the object vdatum settings.
    
        Returns
        -------
        dict
            dictionary of settings
        """
    
        settings = {}
        try:
            config_file = configparser.ConfigParser()
            config_file.read(self.config_path_file)
            sections = config_file.sections()
            for section in sections:
                config_file_section = config_file[section]
                for key in config_file_section:
                    settings[key] = config_file_section[key]
        except:
            # get a number of exceptions here when reading and writing to the config file in multiprocessing
            try:
                if self.parent:
                    self.parent.log_warning('Unable to read from existing config file {}'.format(self.config_path_file))
            except AttributeError:  # logger not initialized yet
                print('WARNING: Unable to read from existing config file {}'.format(self.config_path_file))
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
        dict
            settings within the file
        """
        try:
            config_folder, config_file = os.path.split(self.config_path_file)
            if not os.path.exists(config_folder):
                os.mkdir(config_folder)
            config = configparser.ConfigParser()
            config['Default'] = default_settings
            with open(self.config_path_file, 'w') as configfile:
                config.write(configfile)
        except:
            # get a number of exceptions here when reading and writing to the config file in multiprocessing
            try:
                if self.parent:
                    self.parent.log_warning('Unable to create new config file {}'.format(self.config_path_file))
            except AttributeError:  # logger not initialized yet
                print('WARNING: Unable to create new config file {}'.format(self.config_path_file))
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
        self.grid_files, self.regions = get_gtx_grid_list(vdatum_path)
        self.polygon_files = get_vdatum_region_polygons(vdatum_path)
        self.uncertainties = get_vdatum_uncertainties(vdatum_path)

        self.vdatum_path = self._config['vdatum_path']

    def get_vdatum_version(self):
        """
        Get the current vdatum version that vyperdatum generates on the fly.  If this has been run before, the version
        will be encoded in a new vdatum_vyperversion.txt file that we can read instead so that we don't have to do the
        lengthy check.
        """
        if not os.path.exists(self.vdatum_path):
            raise ValueError(f'VDatum is not found at the provided path: {self.vdatum_path}')
        vyperversion_file = os.path.join(self.vdatum_path, 'vdatum_vyperversion.txt')
        if os.path.exists(vyperversion_file):
            with open(vyperversion_file, 'r') as vfile:
                vversion = vfile.read()
        else:
            try:
                if self.parent:
                    self.parent.log_info(f'Performing hash comparison to identify VDatum version, should only run once for a new VDatum directory...')
            except AttributeError:  # logger not initialized yet
                print(f'Performing hash comparison to identify VDatum version, should only run once for a new VDatum directory...')
            vversion = return_vdatum_version(self.grid_files, self.vdatum_path, save_path=vyperversion_file)
            try:
                if self.parent:
                    self.parent.log_info(f'Generated new version file: {vyperversion_file}')
            except AttributeError:  # logger not initialized yet
                print(f'Generated new version file: {vyperversion_file}')
        self.vdatum_version = vversion


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
    list
        list of vdatum regions
    """

    search_path = os.path.join(vdatum_directory, '*/*.gtx')
    gtx_list = glob.glob(search_path)
    if len(gtx_list) == 0:
        errmsg = f'No GTX files found in the provided VDatum directory: {vdatum_directory}'
        print(errmsg)
    grids = {}
    regions = []
    for gtx in gtx_list:
        gtx_path, gtx_file = os.path.split(gtx)
        gtx_path, gtx_folder = os.path.split(gtx_path)
        gtx_name = '/'.join([gtx_folder, gtx_file])
        gtx_subpath = os.path.join(gtx_folder, gtx_file)
        grids[gtx_name] = gtx_subpath
        regions.append(gtx_folder)
    regions = list(set(regions))
    return grids, regions


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
                        else:
                            grid_dict[suffix] = float(val) * 0.01
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


def hash_a_file(filepath: str):
    """
    Generate a new md5 hash for the provided file

    Parameters
    ----------
    filepath
        full absolute file path to the file to hash

    Returns
    -------
    str
        new md5 hex digest for the file
    """

    md5 = hashlib.md5()
    with open(filepath, 'rb') as f:
        data = f.read()
        md5.update(data)
    return md5.hexdigest()


def hash_vdatum_grids(grid_files: dict, vdatum_path: str):
    """
    Generate a new md5 hash for each grid file in the provided dictionary

    Parameters
    ----------
    grid_files
        dictionary of {file name: file path} for the grids in this vdatum directory
    vdatum_path
        path to the vdatum folder

    Returns
    -------
    dict
        dictionary of {file path: file hash}
    """

    hashdict = {}
    for grd in grid_files.keys():
        hashdict[grd] = hash_a_file(os.path.join(vdatum_path, grd))
    return hashdict


def return_vdatum_version(grid_files: dict, vdatum_path: str, save_path: str = None):
    """
    Return the vdatum version either by brute force using our vdatum hash lookup check, or by reading the vdatum
    version file that vyperdatum generates, if this check has been run once before.

    Parameters
    ----------
    grid_files
        dictionary of {file name: file path} for the grids in this vdatum directory
    vdatum_path
        path to the vdatum folder
    save_path
        if provided, saves the vdatum version to a new text file in the vdatum directory

    Returns
    -------

    """
    hashdict = hash_vdatum_grids(grid_files, vdatum_path)
    myversion = ''
    for vdversion, vdhashes in vdatum_hashlookup.items():
        if hashdict == vdhashes:
            myversion = vdversion
    if myversion and save_path:
        with open(save_path, 'w') as ofile:
            ofile.write(myversion)
    if not myversion:
        raise EnvironmentError(f'Unable to find version for {vdatum_path} in the currently accepted versions: {list(vdatum_hashlookup.keys())}')
    return myversion
