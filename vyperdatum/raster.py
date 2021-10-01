from time import perf_counter
import os
import numpy as np
from typing import Union
from osgeo import gdal
from pyproj import Transformer, CRS
from pyproj.exceptions import CRSError

from vyperdatum.core import VyperCore
from vyperdatum.vypercrs import get_transformation_pipeline


class VyperRaster(VyperCore):
    """
    Using VyperCore, read from a raster and perform a vertical transformation of the data to a vdatum supported
    vertical datum CRS, optionally writing to geotiff.
    """

    def __init__(self, input_file: str = None, vdatum_directory: str = None,
                 logfile: str = None, silent: bool = False):
        super().__init__(vdatum_directory, logfile, silent)
        self.input_file = input_file
        self.input_wkt = None
        self.geotransform = None

        self.resolution_x = None
        self.resolution_y = None
        self.width = None
        self.height = None

        self.layers = []
        self.layernames = []
        self.nodatavalue = []

        self.raster_vdatum_sep = None
        self.raster_vdatum_uncertainty = None
        self.raster_vdatum_region_index = None

        self.output_geotransform = None

        if input_file:
            self.initialize()

    @property
    def is_covered(self):
        """
        Data is completely covered by the found VDatum regions

        Returns
        -------
        bool
            Returns true if data is completely covered by VDatum
        """

        if self.raster_vdatum_sep is None:
            self.log_error('No separation grid found, make sure you run get_datum_sep first', ValueError)
        return np.count_nonzero(np.isnan(self.raster_vdatum_sep)) == 0

    def initialize(self, input_file: str = None):
        """
        Get all the data we need from the input raster.  This is run automatically on instancing this class, if an input
        file is provided then.  Otherwise, use this method and provide a gdal supported file to initialize.

        Parameters
        ----------
        input_file
            file path to a gdal supported raster file
        """

        if input_file:  # can re-initialize by passing in a new file here
            self.input_file = input_file

        ofile = gdal.Open(self.input_file)
        if not ofile:
            self.log_error(f'Unable to open {self.input_file} with gdal', ValueError)

        self.log_info(f'Operating on {self.input_file}')
        self.layers = [ofile.GetRasterBand(i + 1).ReadAsArray() for i in range(ofile.RasterCount)]
        self.nodatavalue = [ofile.GetRasterBand(i + 1).GetNoDataValue() for i in range(ofile.RasterCount)]
        self.layernames = [ofile.GetRasterBand(i + 1).GetDescription() for i in range(ofile.RasterCount)]

        # readasarray doesn't seem to handle gdal nodatavalue NaN
        for lyr, ndv in zip(self.layers, self.nodatavalue):
            lyr[lyr == ndv] = np.nan

        # geotransform in this format [x origin, x pixel size, x rotation, y origin, y rotation, -y pixel size]
        self.geotransform = ofile.GetGeoTransform()
        min_x, self.resolution_x, _, max_y, _, self.resolution_y = self.geotransform
        self.width, self.height = ofile.RasterXSize, ofile.RasterYSize
        max_x = min_x + self.width * self.resolution_x
        min_y = max_y + self.height * self.resolution_y
        self.resolution_y = abs(self.resolution_y)  # store this as positive for future use

        input_crs = ofile.GetSpatialRef()
        self.input_wkt = input_crs.ExportToWkt()
        self.set_input_datum(self.input_wkt, extents = (min_x, min_y, max_x, max_y))
        ofile = None

    def _get_elevation_layer_index(self):
        """
        Find the elevation layer index

        Returns
        -------
        int
            integer index in self.layernames for the elevation layer, -1 if it does not exist
        """
        check_layer_names = [lname.lower() for lname in self.layernames]
        if 'depth' in check_layer_names:
            depth_idx = check_layer_names.index('depth')
        elif 'elevation' in check_layer_names:
            depth_idx = check_layer_names.index('elevation')
        else:
            depth_idx = -1
            self.log_warning(f'Unable to find depth or elevation layer by name, layers={check_layer_names}')
        return depth_idx

    def _get_uncertainty_layer_index(self):
        """
        Find the uncertainty layer index

        Returns
        -------
        int
            integer index in self.layernames for the uncertainty layer, -1 if it does not exist
        """
        check_layer_names = [lname.lower() for lname in self.layernames]
        if 'uncertainty' in check_layer_names:
            unc_idx = check_layer_names.index('uncertainty')
        elif 'vertical uncertainty' in check_layer_names:
            unc_idx = check_layer_names.index('vertical uncertainty')
        else:
            unc_idx = -1
            self.log_warning(f'Unable to find uncertainty or vertical uncertainty layer by name, layers={check_layer_names}')
        return unc_idx

    def _get_contributor_layer_index(self):
        """
        Find the contributor layer index

        Returns
        -------
        int
            integer index in self.layernames for the contributor layer, -1 if it does not exist
        """
        check_layer_names = [lname.lower() for lname in self.layernames]
        if 'contributor' in check_layer_names:
            cont_idx = check_layer_names.index('contributor')
        else:
            cont_idx = -1
            self.log_warning(f'Unable to find contributor layer by name, layers={check_layer_names}')
        return cont_idx

    def get_datum_sep(self):
        """
        Build a datum separation using the VDatum regions and compound input and output
        datum definitions described in this object as attributes.  The coordinate
        reference systems (vypercrs.VyperPipelineCRS objects) must be valid for this
        process to commence.
        
        The datum separation, datum uncertainty, and region index corrisponding to the
        object region list are stored as object attributes.
        
        Raises
        ------
        ValueError
            If there are no regions in the object or the in_crs or out_crs objects are
            not valid.

        Returns
        -------
        None.

        """

        if self.regions is None:
            self.log_error('Initialization must have failed, re-initialize with a new gdal supported file', ValueError)
        if not self.in_crs.is_valid:
            self.log_error('Input datum must be valid before performing datum transformation operations.', ValueError)
        if not self.out_crs.is_valid:
            self.log_error('Output datum must be valid before performing datum transformation operations.', ValueError)
        if self.in_crs.horizontal.to_wkt() != self.out_crs.horizontal.to_wkt():
            self.log_error('Horizontal datum transformation operations for rasters are not yet supported.', NotImplementedError)

        self.pipelines = []
        self.regional_seps = []
        self.regional_uncertainties = []
        valid_counts = []
        valid_idx = []
        for region in self.regions:
            if region not in self.vdatum.regions:
                self.log_error('Region {region} not found in VDatum.', ValueError)
            # get the pipeline
            regional_sep = None
            pipeline = get_transformation_pipeline(self.in_crs, self.out_crs, region, self.vdatum.vdatum_version)
            self.pipelines.append(pipeline)
            # get each layer for for the pipeline and add to the stack
            for cmd in pipeline.split(' +step '):
                if cmd.find('vgridshift') >= 0:
                    inv = False
                    cmd_parts = cmd.split()
                    for part in cmd_parts:
                        if part == '+inv':
                            inv = True
                        elif part.startswith('grids='):
                            junk, grid_file = part.split('=')
                            grid_path = os.path.join(self.vdatum.vdatum_path, grid_file)
                    # transform, crop and resample the source grid
                    epsg = self.out_crs.horizontal.to_epsg()
                    ds = gdal.Warp('', grid_path, format = 'MEM', dstSRS = f'EPSG:{epsg}', 
                                   xRes = self.resolution_x, yRes = self.resolution_y, 
                                   outputBounds = [self.min_x, self.min_y, self.max_x, self.max_y])
                    band = ds.GetRasterBand(1)
                    array = band.ReadAsArray()
                    nodata = band.GetNoDataValue()
                    array[np.where(array == nodata)] = np.nan
                    if not inv:
                        array *= -1
                    ds = None
                    if regional_sep is None:
                        regional_sep = array.copy()
                    else:
                        regional_sep += array
            self.regional_seps.append(regional_sep)
            valid = np.where(~np.isnan(regional_sep))
            valid_idx.append(valid)
            valid_counts.append(len(valid[0]))
            datum_unc = self._get_output_uncertainty(region)
            regional_uncertainty = np.full(regional_sep.shape, np.nan)
            regional_uncertainty[valid] = datum_unc
            self.regional_uncertainties.append(regional_uncertainty)
        # combine the regional seps
        self.raster_vdatum_sep = np.full((self.height, self.width), np.nan)
        self.raster_vdatum_uncertainty = np.full((self.height, self.width), np.nan)
        self.raster_vdatum_region_index = np.full((self.height, self.width), np.nan)
        stack_order = np.argsort(valid_counts)
        for idx in stack_order:
            self.raster_vdatum_sep[valid_idx[idx]] = self.regional_seps[idx][valid_idx[idx]]
            self.raster_vdatum_uncertainty[valid_idx[idx]] = self.regional_uncertainties[idx][valid_idx[idx]]
            self.raster_vdatum_region_index[valid_idx[idx]] = idx

    def apply_sep(self, allow_points_outside_coverage: bool = False):
        """
        After getting the datum separation model from vdatum, use this method to apply the separation and added
        separation uncertainty.

        If allow_points_outside_coverage is True, this will pass through z values that are outside of vdatum coverage,
        but add additional uncertainty

        Parameters
        ----------
        allow_points_outside_coverage
            if True, allows through points outside of vdatum coverage

        Returns
        -------
        tuple
            tuple of layers, including elevation, uncertainty and possibly contributor
        tuple
            tuple of layer names for each layer in returned layers
        tuple
            tuple of layer nodata value for each layer in returned layers
        """

        if self.raster_vdatum_sep is None:
            self.log_error('Unable to find sep model, make sure you run get_datum_sep first', ValueError)
        elevation_layer_idx = self._get_elevation_layer_index()
        uncertainty_layer_idx = self._get_uncertainty_layer_index()
        contributor_layer_idx = self._get_contributor_layer_index()

        if elevation_layer_idx == -1:
            self.log_error('Unable to find elevation layer', ValueError)
        if uncertainty_layer_idx == -1:
            self.log_info('Unable to find uncertainty layer, uncertainty will be entirely based off of vdatum sep model')

        elevation_layer = self.layers[elevation_layer_idx]
        layernames = [self.layernames[elevation_layer_idx]]
        layernodata = [self.nodatavalue[elevation_layer_idx]]
        uncertainty_layer = None
        contributor_layer = None
        if uncertainty_layer_idx:
            uncertainty_layer = self.layers[uncertainty_layer_idx]
            layernames.append(self.layernames[uncertainty_layer_idx])
            layernodata.append(self.nodatavalue[uncertainty_layer_idx])
        else:
            layernames.append('Uncertainty')
            layernodata.append(np.nan)
        if contributor_layer_idx:
            contributor_layer = self.layers[contributor_layer_idx]
            layernames.append(self.layernames[contributor_layer_idx])
            layernodata.append(self.nodatavalue[contributor_layer_idx])

        elev_nodata = np.isnan(elevation_layer)
        elev_nodata_idx = np.where(elev_nodata)
        missing = np.isnan(self.raster_vdatum_sep)
        missing_idx = np.where(missing & ~elev_nodata)
        missing_count = len(missing_idx[0])
        self.log_info(f'Applying vdatum separation model to {self.raster_vdatum_sep.size} total points')

        if self.in_crs.is_height == self.out_crs.is_height:
            flip = 1
        else:
            flip = -1

        if self.in_crs.is_height == True:
            final_elevation_layer = flip * (elevation_layer + self.raster_vdatum_sep)
        else:
            final_elevation_layer = flip * (elevation_layer - self.raster_vdatum_sep)
        final_elevation_layer[elev_nodata_idx] = self.nodatavalue[elevation_layer_idx]

        if uncertainty_layer_idx:
            final_uncertainty_layer = uncertainty_layer + self.raster_vdatum_uncertainty
        else:
            final_uncertainty_layer = self.raster_vdatum_uncertainty
        final_uncertainty_layer[elev_nodata_idx] = self.nodatavalue[uncertainty_layer_idx]

        if contributor_layer is not None:
            contributor_layer[elev_nodata_idx] = self.nodatavalue[contributor_layer_idx]

        if allow_points_outside_coverage:
            self.log_info(f'Allowing {missing_count} points that are outside of vdatum coverage, using CATZOC D vertical uncertainty')
            final_elevation_layer[missing_idx] = flip * elevation_layer[missing_idx]
            if self.in_crs.is_height:
                z_values = elevation_layer[missing_idx]
            else:
                z_values = -elevation_layer[missing_idx]
            u_values = 3 - 0.06 * z_values
            u_values[np.where(z_values > 0)] = 3.0
            final_uncertainty_layer[missing_idx] = u_values
        else:
            self.log_info(f'applying nodatavalue to {missing_count} points that are outside of vdatum coverage')
            final_elevation_layer[missing_idx] = self.nodatavalue[elevation_layer_idx]
            final_uncertainty_layer[missing_idx] = self.nodatavalue[uncertainty_layer_idx]
            if contributor_layer is not None:
                contributor_layer[missing_idx] = self.nodatavalue[contributor_layer_idx]         

        layers = (final_elevation_layer, final_uncertainty_layer, contributor_layer)
        return layers, layernames, layernodata

    def transform_raster(self, output_datum: Union[str, int, tuple], input_datum: Union[int, str, tuple] = None,
                         allow_points_outside_coverage: bool = False, output_filename: str = None):
        """
        Main method of this class, contains all the other methods and allows you to transform the source raster to a
        different vertical datum using VDatum.

        Parameters
        ----------
        output_datum
            inputs to vypercrs VyperPipelineCRS
        input_datum
            inputs to vypercrs VyperPipelineCRS
        allow_points_outside_coverage
            if True, allows through points outside of vdatum coverage
        output_filename
            if provided, writes the new raster to geotiff

        Returns
        -------
        tuple
            tuple of layers, including elevation, uncertainty and possibly contributor
        tuple
            tuple of layer names for each layer in returned layers
        tuple
            tuple of layer nodata value for each layer in returned layers
        """

        if input_datum:
            self.set_input_datum(input_datum)

        if output_datum:
            self.set_output_datum(output_datum)

        if self.regions is None:
            self.log_error(f'Unable to find regions for raster using ({self.geographic_min_x},{self.geographic_min_y}), '
                           f'({self.geographic_max_x},{self.geographic_max_y})', ValueError)

        start_cnt = perf_counter()
        self.log_info(f'Begin work on {os.path.basename(self.input_file)}')
        self.get_datum_sep()
        layers, layernames, layernodata = self.apply_sep(allow_points_outside_coverage=allow_points_outside_coverage)
        if output_filename:
            if layernodata[2]:  # contributor
                tiffdata = np.concatenate([layers[0][None, :, :], layers[1][None, :, :], layers[2][None, :, :]])
            else:
                tiffdata = np.concatenate([layers[0][None, :, :], layers[1][None, :, :]])
            tiffdata = np.round(tiffdata, 3)
            self._write_gdal_geotiff(output_filename, tiffdata, layernames, layernodata)
        end_cnt = perf_counter()
        self.log_info(f'Raster transformation complete: Elapsed time {end_cnt - start_cnt} seconds')
        return layers, layernames, layernodata

    def _custom_output_crs(self, destination_epsg: int):
        try:
            out_crs = CRS.from_epsg(int(destination_epsg))
        except CRSError:
            self.log_error(f'Expected integer epsg code that is readable by the pyproj CRS object, got {destination_epsg}',
                           ValueError)
        if out_crs.is_vertical:
            self.log_error(f'Only 2d coordinate system epsg supported when using the new_2d_crs option, got {destination_epsg}',
                           ValueError)
        in_crs = CRS.from_epsg(6319)
        # Transformer.transform input order is based on the CRS, see CRS.geodetic_crs.axis_info
        # - lon, lat - this appears to be valid when using CRS from proj4 string
        # - lat, lon - this appears to be valid when using CRS from epsg
        # use the always_xy option to force the transform to expect lon/lat order
        transformer = Transformer.from_crs(in_crs, out_crs, always_xy=True)
        new_min_x, new_min_y = transformer.transform(self.geographic_min_x, self.geographic_min_y)
        new_max_x, new_max_y = transformer.transform(self.geographic_max_x, self.geographic_max_y)

        # if out_crs.is_projected:
        #     if new_min_x < 0:
        #         new_min_x = int(np.ceil(new_min_x))
        #     else:
        #         new_min_x = int(np.floor(new_min_x))
        #     if new_min_y < 0:
        #         new_min_y = int(np.ceil(new_min_y))
        #     else:
        #         new_min_y = int(np.floor(new_min_y))
        #     if new_max_x < 0:
        #         new_max_x = int(np.floor(new_max_x))
        #     else:
        #         new_max_x = int(np.ceil(new_max_x))
        #     if new_max_y < 0:
        #         new_max_y = int(np.floor(new_max_y))
        #     else:
        #         new_max_y = int(np.ceil(new_max_y))

        x_rez = (new_max_x - new_min_x) / self.width
        y_rez = (new_max_y - new_min_y) / self.height
        self.output_geotransform = (new_min_x, x_rez, 0.0, new_max_y, 0.0, -y_rez)
        self.out_crs.horiz_wkt = out_crs.to_wkt()

    def _write_gdal_geotiff(self, outfile: str, data: tuple, band_names: tuple, nodatavalue: tuple,
                            use_custom_geotransform: bool = False):
        """
        Build a geotiff from the transformed raster data

        Parameters
        ----------
        outfile
            output file that we write the raster data to
        data
            arrays for each layer that we want to write to file
        band_names
            names for each layer that we want to write to file
        nodatavalue
            nodatavalues for each layer that we want to write to file
        use_custom_geotransform
            if True, rely on the custom output geotransform we made from the provided 2d epsg in transform raster
        """

        numlyrs, rows, cols = data.shape
        driver = gdal.GetDriverByName('GTiff')
        out_raster = driver.Create(outfile, cols, rows, numlyrs, gdal.GDT_Float32)
        if use_custom_geotransform:
            out_raster.SetGeoTransform(self.output_geotransform)
        else:
            out_raster.SetGeoTransform(self.geotransform)
        for lyr_num in range(numlyrs):
            outband = out_raster.GetRasterBand(lyr_num + 1)
            outband.SetNoDataValue(nodatavalue[lyr_num])
            outband.SetDescription(band_names[lyr_num])
            outband.WriteArray(data[lyr_num])
            outband = None
        out_raster.SetProjection(self.out_crs.to_wkt())
        out_raster = None
