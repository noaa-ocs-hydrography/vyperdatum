import os
import logging
from osgeo import gdal
import geopandas as gpd
from shapely.geometry import Point
import numpy as np
import pyproj as pp
from vyperdatum.utils.crs_utils import auth_code
from vyperdatum.drivers.base import Driver

logger = logging.getLogger("root_logger")
gdal.UseExceptions()


class GeoParquet(Driver):
    def __init__(self, input_file: str, invalid_error: bool = True) -> None:
        """
        Parameters
        -----------
        input_file: str
            Path to the input geoparquet file.
        invalid_error: bool, default True
            If True, throws an error when the input file has an unexpected format.

        Raises
        -------
        FileNotFoundError:
            If the input file is not found.
        ValueError
            If the passed input file is not recognized as geoparquet file.

        Returns
        -----------
        None
        """
        super().__init__()
        self.input_file = input_file
        if not os.path.isfile(self.input_file):
            raise FileNotFoundError(f"The input file not found at {input_file}.")
        self.is_gparq = self._is_valid()
        if invalid_error and not self.is_gparq:
            msg = (f"The following file is not a valid geoparquet point file: {self.input_file}")
            logger.exception(msg)
            raise TypeError(msg)
        return

    def _is_valid(self) -> bool:
        """
        Check if the input file is a geoparquet and only contains points.

        Returns
        -----------
        bool
            True if a valid geoparquet with point data; otherwise False.
        """
        try:
            gdf = gpd.read_parquet(self.input_file)
            geotypes = gdf.geom_type.unique()
            if len(geotypes) != 1 or geotypes[0].lower() != "Point".lower():
                return False
            valid = True
        except:
            valid = False
        return valid

    def get_points(self) -> bool:
        """
        Extract the coordinate points from geoparquet file.
        The input file should be in the geoparquet format and should only contain points.

        Returns
        -----------
        bool
            True if the coordinates are found successfully; otherwise False.
        """
        try:
            if not self._is_valid():
                return False
            gdf = gpd.read_parquet(self.input_file)
            logger.info("Reading geoparquet file into numpy arrays ...")
            coords = np.array([geom.coords[0] for geom in gdf.geometry])
            self.x, self.y, self.z = coords[:, 0], coords[:, 1], coords[:, 2]
            valid = True
        except:
            valid = False
        return valid

    def wkt(self) -> str:
        """
        Return the WKT string.

        Returns
        -----------
        str
            WKT associated with file's CRS.
        """
        gdf = gpd.read_parquet(self.input_file)
        if gdf.crs is None:
            raise ValueError("The input file does not have a CRS.")
        w = gdf.crs.to_wkt()
        return w

    def transform(self, transformer_instance, output_file: str, pre_post_checks: bool, vdatum_check: bool) -> bool:
        """
        Apply point transformation on the geoparquet point data according to the `transformer_instance`.

        Parameters
        -----------
        transformer_instance: vyperdatum.transformer.Transform
            Instance of the transformer class.
        output_file: str
            Path to the output geoparquet file.

        Returns
        -----------
        bool:
            True if successful, otherwise False.
        """
        if not hasattr(self, "x"):
            self.get_points()
        gdf = gpd.read_parquet(self.input_file)
        if pre_post_checks:
            source_crs = transformer_instance.crs_from
            if not isinstance(transformer_instance.crs_from, pp.CRS):
                source_crs = pp.CRS(transformer_instance.crs_from)
            source_auth = auth_code(source_crs)
            file_auth = auth_code(pp.CRS(gdf.crs.to_wkt()))
            if source_auth != file_auth:
                logger.warning("The authority name/code registered in the "
                               f"input file is {file_auth}, but expected {source_auth}"
                               )
        success, xt, yt, zt = transformer_instance.transform_points(self.x,
                                                                    self.y,
                                                                    self.z,
                                                                    vdatum_check=vdatum_check
                                                                    )
        new_geometry = [Point(xi, yi, zi) for xi, yi, zi in zip(xt, yt, zt)]
        new_gdf = gpd.GeoDataFrame(gdf[["Uncertainty", "Classification"]].copy(),
                                   geometry=new_geometry,
                                   crs=pp.CRS(transformer_instance.crs_to)
                                   )
        new_gdf.to_parquet(output_file, compression="gzip", index=False)

        if pre_post_checks:
            new_gdf = gpd.read_parquet(output_file)
            target_crs = transformer_instance.crs_to
            if not isinstance(transformer_instance.crs_to, pp.CRS):
                target_crs = pp.CRS(transformer_instance.crs_to)
            target_auth = auth_code(target_crs)
            transformed_file_auth = auth_code(pp.CRS(new_gdf.crs.to_wkt()))
            if target_auth != transformed_file_auth:
                logger.warning("The expected authority name/code of the "
                               f"transformed geoparquet is {target_auth}, but received {transformed_file_auth}"
                               )        
        return success

    @property
    def is_valid(self):
        return self.is_gparq
