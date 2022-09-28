import os
import numpy as np
from osgeo import gdal
from typing import Union

from vyperdatum.core import VyperCore


class VyperPoints(VyperCore):
    """
    An extension of VyperCore with methods for dealing with point data.  Currently not much here, just some examples
    of exporting and storing the transformed data.
    """

    def __init__(self,  vdatum_directory: str = None, logfile: str = None, silent: bool = False):
        # ensure that vdatum_directory is passed in the first time this is run, to store that path
        super().__init__(vdatum_directory, logfile, silent)
        self.x = None
        self.y = None
        self.z = None
        self.unc = None
        self.region_index = None

    def transform_points(self, input_datum: tuple, output_datum: Union[tuple, str], x: np.array, y: np.array,
                         z: np.array = None, include_vdatum_uncertainty: bool = True, include_region_index: bool = False,
                         sample_distance: float = None):
        """
        Run transform_dataset to get the vertical transformed result / 3d transformed result.

        See core.VyperCore.transform_dataset

        Parameters
        ----------
        input_datum
            a tubple with either a string identifier (ex: 'nad83', 'mllw', or a wkt) or an epsg code 
            describing the horizontal and vertical datums for the input data.
            
        output_datum
            a string identifier (ex: 'nad83', 'mllw', or a wkt) or an epsg code for the vertical datum
            and optionally (within a tuple)
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
        sample_distance
            if a float is provided, we bin the points using a 2d grid of resolution sample_distance, and only run the
            grid center node location through vyperdatum
        """

        self.set_input_datum(input_datum)
        self.set_output_datum(output_datum)

        if not sample_distance:
            self.x, self.y, self.z, self.unc, self.region_index = self.transform_dataset(x, y, z,
                                                                                         include_vdatum_uncertainty=include_vdatum_uncertainty,
                                                                                         include_region_index=include_region_index)
        else:
            extents = (min(x), min(y), max(x), max(y))
            self._set_extents(extents)
            xx_sampled, yy_sampled, x_range, y_range = sample_array(self.min_x, self.max_x, self.min_y, self.max_y, sample_distance)
            x_sep, y_sep, z_sep, unc_new, regidx = self.transform_dataset(xx_sampled.ravel(), yy_sampled.ravel(),
                                                                          include_vdatum_uncertainty=include_vdatum_uncertainty,
                                                                          include_region_index=include_region_index)

            # handle nans
            nan_mask = np.logical_and(~np.isnan(x), ~np.isnan(y))
            # bin the raster cell locations to get which sep value applies
            x_bins = np.digitize(x[nan_mask], x_range)
            y_bins = np.digitize(y[nan_mask], y_range)

            # no 2d transformation is done with sampling interval, we can't just expand the xy coordinates
            self.x = None
            self.y = None
            z_sep = z_sep.reshape(xx_sampled.shape)
            if z is not None:
                if self.in_crs.is_height != self.out_crs.is_height:
                    z = z.copy()
                    z *= -1
                newz = z_sep[y_bins - 1, x_bins - 1] + z[nan_mask]
            else:
                newz = z_sep[y_bins - 1, x_bins - 1]
            self.z = np.zeros_like(z)
            self.z[nan_mask] = newz
            self.z[~nan_mask] = np.float32(np.nan)
            if include_vdatum_uncertainty:
                unc_new = unc_new.reshape(xx_sampled.shape)
                unc_new = unc_new[y_bins - 1, x_bins - 1]
                self.unc = np.zeros(z.shape, dtype=unc_new.dtype)
                self.unc[nan_mask] = unc_new
                self.unc[~nan_mask] = np.float32(np.nan)
            if include_region_index:
                regidx = regidx.reshape(xx_sampled.shape)
                regidx = regidx[y_bins - 1, x_bins - 1]
                self.region_index = np.zeros(z.shape, dtype=regidx.dtype)
                self.region_index[nan_mask] = regidx
                self.region_index[~nan_mask] = -1

    def export_to_csv(self, output_file: str, delimiter: str = ' '):
        """
        Export all point variables to csv.  Includes uncertainty and region index if that data is contained in this class.

        Parameters
        ----------
        output_file
            the file path to the output file you want to write
        delimiter
            optional, delimiter character if you don't want space delimited data
        """

        dset_vars = [dvar for dvar in [self.x, self.y, self.z, self.unc, self.region_index] if dvar is not None]
        dset = np.c_[dset_vars]
        np.savetxt(output_file, dset, delimiter=delimiter, comments='')


def sample_array(min_x: float, max_x: float, min_y: float, max_y: float, sampling_distance: float, center: bool = True):
    """
    Build coordinates for a sampled grid using the extents of the main grid.  The new grid will have the same extents,
    but be sampled at sampling_distance.

    Parameters
    ----------
    min_x
        minimum x value of the grid
    max_x
        maximum x value of the grid
    min_y
        minimum y value of the grid
    max_y
        maximum y value of the grid
    sampling_distance
        distance in grid units to sample
    center
        optional, if True returns the sampled grid coordinates at the center of the sampled grid, rather than the edges

    Returns
    -------
    np.ndarray
        2d array of x values for the new sampled grid
    np.ndarray
        2d array of y values for the new sampled grid
    np.array
        1d array of the x values for one column of the grid, i.e. the x range of the grid
    np.array
        1d array of the y values for one column of the grid, i.e. the y range of the grid
    """

    # buffer out so that points do not lie on boundaries of bins
    min_x -= sampling_distance
    max_x += sampling_distance
    min_y -= sampling_distance
    max_y += sampling_distance

    nx = np.ceil((max_x - min_x) / sampling_distance).astype(int)
    ny = np.ceil((max_y - min_y) / sampling_distance).astype(int)
    x_range = np.linspace(min_x, max_x, nx)
    y_range = np.linspace(min_y, max_y, ny)

    if center:
        # sampled coords are now the cell borders, we want cell centers
        x_sampled = x_range[:-1] + (sampling_distance / 2)
        y_sampled = y_range[:-1] + (sampling_distance / 2)
    else:
        x_sampled = x_range
        y_sampled = y_range

    # grid with yx order to match gdal
    yy, xx = np.meshgrid(y_sampled, x_sampled, indexing='ij')

    return xx, yy, x_range, y_range
