import sys

import numpy as np
import pyproj.exceptions
from pyproj import Transformer, CRS
from osgeo import gdal, ogr
from typing import Union
import logging
from datetime import datetime

from vyperdatum.vypercrs import VyperPipelineCRS, get_transformation_pipeline, geoid_frame_lookup, geoid_possibilities, \
    frame_to_3dcrs
from vyperdatum.vyperdata import DatumData


class VyperCore:
    """
    The core object for conducting transformations.  Contains all the information built automatically from the vdatum
    distribution, including paths to gtx files and uncertainty per grid.  VyperCore uses this information to provide
    a transformation method to go from source datum to EPSG with a vertical or 3d transformation, depending on
    source datum.
    """

    def __init__(self, vdatum_directory: str = None, logfile: str = None, silent: bool = False):
        self.silent = silent
        self.datum_data = DatumData(vdatum_directory=vdatum_directory, parent=self)

        self.min_x = None
        self.min_y = None
        self.max_x = None
        self.max_y = None

        self.geographic_min_x = None
        self.geographic_min_y = None
        self.geographic_max_x = None
        self.geographic_max_y = None

        self.in_crs = VyperPipelineCRS(self.datum_data)
        self.out_crs = VyperPipelineCRS(self.datum_data)

        self.logger = return_logger(logfile)
        self._regions = []
        self._geoid_frame = []
        self.pipelines = []

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
        self._geoid_frame = []
        for region in self.datum_data.polygon_files:
            vector = ogr.Open(self.datum_data.polygon_files[region])
            layer_count = vector.GetLayerCount()
            for m in range(layer_count):
                layer = vector.GetLayerByIndex(m)
                feature_count = layer.GetFeatureCount()
                for n in range(feature_count):
                    feature = layer.GetNextFeature()
                    try:
                        feature_name = feature.GetField(0)
                    except AttributeError:
                        print('WARNING: Unable to read feature name from feature in layer in {}'.format(self.datum_data.polygon_files[region]))
                        continue
                    if feature_name[:15] == 'valid-transform':
                        valid_vdatum_poly = feature.GetGeometryRef()
                        if data_geometry.Intersect(valid_vdatum_poly):
                            intersecting_regions.append(region)
                            gframe = self.datum_data.get_geoid_frame(region)
                            self._geoid_frame.append(gframe)
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
        in_horiz_name = self.in_crs.horizontal.name
        # ideally we would use the geoid frame to do this, but we need to identify the regions to identify the geoid frame,
        #   so we just use NAD83 coordinates instead.  The difference when dealing with the sep model grids is negligible
        if in_horiz_name != 'NAD83(2011)':
            x = [self.min_x, self.max_x]
            y = [self.min_y, self.max_y]
            z = [0, 0]
            x_geo, y_geo, z_geo = self._transform_to_geoid_frame(x, y, z, override_frame='NAD83(2011)')
            self.geographic_min_x, self.geographic_max_x = x_geo
            self.geographic_min_y, self.geographic_max_y = y_geo
        else:
            self.geographic_min_x = self.min_x
            self.geographic_max_x = self.max_x
            self.geographic_min_y = self.min_y
            self.geographic_max_y = self.max_y

    def _transform_to_geoid_frame(self, x: np.array, y: np.array, z: np.array = None, override_frame: Union[str, int] = None):
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
        override_frame
            if you don't want to use the geoid frame, you can specify a new frame here, as either a string identifier
            or an epsg code

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
        if override_frame:
            if isinstance(override_frame, str):
                out_crs = frame_to_3dcrs[override_frame]
            else:
                out_crs = CRS.from_epsg(override_frame)
        else:  # the geoid frame attribute is the 2d coord system for each region, if override not specified, just use the first region frame
            out_crs = frame_to_3dcrs[self._geoid_frame[0]]
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
        outdatum = self.out_crs.vyperdatum_str
        indatum = self.in_crs.vyperdatum_str
        if indatum == 'ellipse' and outdatum != 'ellipse':  # include ellipse-geoid uncertainty
            gd_index = np.where([self.out_crs.pipeline_string.find(gd) for gd in geoid_possibilities] != -1)[0]
            if gd_index.size != 1:
                self.log_error(f'Found {len(gd_index.size)} geoid possibilities in pipeline string', ValueError)
            geoid = geoid_possibilities[gd_index[0]]
            final_uncertainty += self.datum_data.uncertainties[geoid]
        if indatum in ['ellipse', 'geoid', 'navd88'] and outdatum not in ['ellipse', 'geoid', 'navd88']:  # include tss uncertainty
            final_uncertainty += self.datum_data.uncertainties[region]['tss']
        if outdatum not in ['ellipse', 'geoid', 'tss', 'navd88']:
            srch_string = outdatum
            if srch_string == 'noaa chart datum':
                srch_string = 'mllw'
            elif srch_string == 'noaa chart height':
                srch_string = 'mhw'
            final_uncertainty += self.datum_data.uncertainties[region][srch_string]

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
                z = z.copy()  # do not alter the array input
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
            valid_regions = []
            for cnt, region in enumerate(self._regions):
                gframe = self.datum_data.get_geoid_frame(region)
                geoid_name = self.datum_data.get_geoid_name(region)
                in_horiz_name = self.in_crs.horizontal.name
                out_horiz_name = self.out_crs.horizontal.name
                if in_horiz_name != gframe:  # need to transform these points to use the geoid coordinate system
                    new_x, new_y, new_z = self._transform_to_geoid_frame(x, y, z, override_frame=gframe)
                else:
                    new_x, new_y, new_z = x, y, z
                pipeline, valid_pipeline = get_transformation_pipeline(self.in_crs, self.out_crs, region, geoid_name)
                if not valid_pipeline:
                    self.log_info(f'Pipeline "{pipeline}" for transformation from "{self.in_crs.pipeline_string}" to "{self.out_crs.pipeline_string}" in region "{region}" was flagged as invalid.  Missing support files?')
                    continue
                elif pipeline:  # do the vertical transformation if there is a valid one for this operation
                    new_x, new_y, new_z = self._run_pipeline(new_x, new_y, pipeline, z=new_z)
                    self.pipelines.append(pipeline)
                    valid_regions.append(region)
                if out_horiz_name == in_horiz_name:  # we can use the original xy as the input/output horiz datums are the same
                    new_x, new_y = x, y
                elif out_horiz_name == gframe:  # we can use the transformed geoid frame xy as the output and gframe datums are the same
                    new_x, new_y = new_x, new_y
                else:  # we need to get new xy to account for the change in horizontal datum
                    if self.out_crs.vyperdatum_str != 'ellipse':
                        new_x, new_y, _ = self._transform_to_geoid_frame(x, y, z, override_frame=self.out_crs.horizontal.to_epsg())
                    else:  # special case, if output is to the ellipse, we need to do a 3d transformation to account for vertical differences in ellipses
                        new_x, new_y, diffz = self._transform_to_geoid_frame(x, y, z, override_frame=self.out_crs.horizontal.to_epsg())
                        new_z = new_z - (z - diffz)
                # areas outside the coverage of the vert shift are inf
                valid_index = ~np.isinf(new_z)
                ans_x[valid_index] = new_x[valid_index]
                ans_y[valid_index] = new_y[valid_index]
                ans_z[valid_index] = flip * new_z[valid_index]
                if include_vdatum_uncertainty:
                    ans_unc[valid_index] = self._get_output_uncertainty(region)
                if include_region_index:
                    ans_region[valid_index] = cnt
            # update the regions to those that passed
            if len(valid_regions) > 0:
                self._regions = valid_regions
                self.in_crs.update_regions(valid_regions)
                self.out_crs.update_regions(valid_regions)
                self.log_info(f'transformed {len(ans_z)} points from {self.in_crs.vyperdatum_str} to {self.out_crs.vyperdatum_str}')
            else:
                self.log_error('No valid region found with the specified datum transformation. Unable to perform transformation', ValueError)
            return ans_x, ans_y, np.round(ans_z, 3), ans_unc, ans_region
        else:
            self.log_error('No regions specified, unable to transform points', ValueError)


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


def vertical_datum_to_wkt(datum_identifier: str, projcrs: int, min_lon: float, min_lat: float, max_lon: float, max_lat: float):
    """
    Translate the provided vertical datum identifier to vypercrs wkt string.  Used to build vertical datum wkt string
    for use in BAG metadata.

    Parameters
    ----------
    datum_identifier
        one of 'mllw', 'mhw', 'waterline', 'ellipse', etc.  See pipeline.datum_definition
    projcrs
        projected crs epsg
    min_lon
        minimum longitude of the survey
    min_lat
        minimum latitude of the survey
    max_lon
        maximum longitude of the survey
    max_lat
        maximum latitude of the survey

    Returns
    -------
    str
        vypercrs wkt string
    """

    if datum_identifier != 'ellipse':
        vc = VyperCore()
        try:
            if datum_identifier == 'mllw':  # we need to let vyperdatum know this is positive down, do that by giving it the mllw epsg
                datum_identifier = 5866
            vc.set_input_datum((projcrs, datum_identifier))
            vc.set_region_by_bounds(min_lon, min_lat, max_lon, max_lat)
            return vc.in_crs._vert.to_wkt()
        except pyproj.exceptions.CRSError:
            raise ValueError(f'vertical_datum_to_wkt: ERROR: unable to resolve HORIZONTAL={projcrs}, VERTICAL={datum_identifier}')
    else:
        # an ellipsoid vertical datum definition looks something like this
        # 'VERTCRS["ellipse",VDATUM["NAD83 / UTM zone 17N + ellipse"],CS[vertical,1],AXIS["ellipsoid height (h)",up,LENGTHUNIT["metre",1]]]'
        # so you don't need to define VDatum version, etc.  Useful for non vdatum havers (some Kluster users), who still want this string
        # so we skip the vypercore initialization (which requires a vdatum path) and just do the below
        try:
            horiz = CRS.from_epsg(projcrs)
        except pyproj.exceptions.CRSError:
            raise ValueError(f'vertical_datum_to_wkt: ERROR: unable to resolve HORIZONTAL={projcrs} as integer epsg code')
        wktstring = 'VERTCRS["ellipse",VDATUM[REPLACEME],CS[vertical,1],AXIS["ellipsoid height (h)",up,LENGTHUNIT["metre",1]]]'
        wktstring = wktstring.replace('REPLACEME', f'"{horiz.name} + ellipse"')

        # vc = VyperCore()
        # cs = VyperPipelineCRS(vc.datum_data)
        # cs.set_crs('ellipse')
        # cs.set_crs(projcrs)
        # wktstring = cs._vert.to_wkt()
        # if 'VDATUM["ellipse"]' not in wktstring:
        #     raise ValueError('datum_to_wkt: expected VDATUM["ellipse"] in datum_identifier=ellipse WKT string, did not find it')
        # wktstring = wktstring.replace('VDATUM["ellipse"]', f'VDATUM["{cs._hori.name} + {cs._vert.name}"]')
        return wktstring
