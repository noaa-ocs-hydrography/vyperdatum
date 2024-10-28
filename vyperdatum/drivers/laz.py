import os
import logging
from osgeo import gdal
import laspy
import numpy as np
import pyproj as pp


logger = logging.getLogger("root_logger")
gdal.UseExceptions()


class LAZ():
    def __init__(self, input_file: str) -> None:
        """
        Parameters
        -----------
        input_file: str
            Path to the input laz file.

        Raises
        -------
        FileNotFoundError:
            If the input file is not found.
        TypeError
            If the passed LAZ file is not valid.

        Returns
        -----------
        None
        """
        self.input_file = input_file
        if not os.path.isfile(self.input_file):
            raise FileNotFoundError(f"The input file not found at {input_file}.")
        if not self.get_points():
            msg = (f"The following file is not a valid LAZ file: {self.input_file}")
            logger.exception(msg)
            raise TypeError(msg)

    def get_points(self) -> bool:
        """
        Extract the coordinate points from .LAZ file.

        Returns
        -----------
        bool
            True if the coordinates are found successfully; otherwise False.
        """
        try:
            with laspy.open(self.input_file) as lf:
                points = lf.read()
                self.x = np.array(points.x)
                self.y = np.array(points.y)
                self.z = np.array(points.z)
                valid = True
        except:
            valid = False
        return valid

    def get_wkt(self) -> str:
        """
        Return the LAZ WKT string.

        Returns
        -----------
        str
            WKT associated with file's CRS.
        """
        with laspy.open(self.input_file) as lf:
            wkt = lf.header.parse_crs().to_wkt()
        return wkt

    def transform_laz(self, transformer_instance) -> None:
        """
        Apply point transformation on the laz data according to the `transformer_instance`.

        Parameters
        -----------
        transformer_instance: vyperdatum.transformer.Transform
            Instance of the transformer class.

        Returns
        -----------
        None
        """
        lf = laspy.read(self.input_file)
        xx, yy, zz = transformer_instance.transform_points(self.x, self.y, self.z)
        lf.x, lf.y, lf.z = xx, yy, zz
        lf.header.add_crs(transformer_instance.crs_to)
        lf.write(self.input_file)
        return
