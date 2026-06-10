import numpy as np
import pathlib
from collections import Counter
from typing import Tuple
import pyproj as pp
from vyperdatum.drivers.base import Driver

class NPZ(Driver):
    """
    Handle loading and parsing of a .npz (numpy arrays) file.

    Attributes
    ----------
    input_file: str
        Full path to the npz file.
    content: np.lib.npyio.NpzFile
        The object containing the numpy arrays stored in the npz file.

    Example
    --------
    >>> npz = NPZ('PATH_TO_NPZ_FILE')
    >>> x, y, z, u = npz.xyzu()
    >>> wkt = npz.wkt()
    >>> mmx, mmy, mmz, mmu = npz.minmax()
    """

    def __init__(self, input_file: str, invalid_error: bool = True) -> None:
        """
        Load a numpy .npz file (collection of numpy arrays).

        Parameters
        ----------
        input_file: str
            Full file path.
        invalid_error: bool, default True
            If True, throws an error when the input file has an unexpected format.

        Raises
        --------
        ValueError:
            If the input file is not recognized as npz file.

        Returns
        -----------
        None
        """
        super().__init__()
        self.input_file = input_file
        self.content = self.load()
        schema = ["wkt", "data", "minmax"]
        try:
            self.is_npz = Counter(self.content.files) == Counter(schema)
        except:
            self.is_npz = False
        if invalid_error and not self.is_npz:
            raise ValueError(("Expected the following keys in the .npz file: "
                              f"{schema}, but receieved {self.content.files}."))

    def load(self) -> np.lib.npyio.NpzFile:
        """
        Load a numpy .npz file (collection of numpy arrays).
        Return None when any exception take place or when the file is invalid. 

        Raises
        --------
        ValueError:
            If the file path is missing.
        FileNotFoundError:
            If the input file is not found.
        TypeError:
            If key names in the .npz file didn't match the expected names.

        Returns
        --------
        Optional[numpy.lib.npyio.NpzFile]
        """
        try:
            if not self.input_file:
                raise ValueError("Invalid or unspecified .npz file path.")
            input_file = pathlib.Path(self.input_file)
            if not input_file.is_file():
                raise FileNotFoundError(f"The npz file not found at: {input_file}")         
            bundle = np.load(input_file)
        except:
            return None
        return bundle


    def xyzu(self) -> Tuple[np.ndarray]:
        """
        Slice the `data` array to extract x, y, z, u arrays.

        Returns
        -------
        x: numpy.ndarray
            x coordinate numpy array.
        y: numpy.ndarray
            y coordinate numpy array.
        z: numpy.ndarray
            z coordinate numpy array.
        u: numpy.ndarray
            uncertainty numpy array.
        """
        if not self.content:
            raise ValueError("npz file not loaded.")
        x = self.content["data"][:, 0]
        y = self.content["data"][:, 1]
        z = self.content["data"][:, 2]
        u = self.content["data"][:, 3]
        return x, y, z, u

    def wkt(self) -> str:
        """
        Return wkt stored in the npz file.
        """
        if not self.content:
            raise ValueError("npz file not loaded.")
        return str(self.content["wkt"])

    def minmax(self) -> Tuple[np.ndarray]:
        """
        Extract the minmax values of the coordinated and uncertainty arrays.

        Returns
        -------
        x: numpy.ndarray
            x coordinate numpy array.
        y: numpy.ndarray
            y coordinate numpy array.
        z: numpy.ndarray
            z coordinate numpy array.
        u: numpy.ndarray
            uncertainty numpy array.
        """
        if not self.content:
            raise ValueError("npz file not loaded.")
        mmx = self.content["minmax"][:, 0]
        mmy = self.content["minmax"][:, 1]
        mmz = self.content["minmax"][:, 2]
        mmu = self.content["minmax"][:, 3]
        return mmx, mmy, mmz, mmu

    def transform(self, transformer_instance, vdatum_check: bool) -> bool:
        """
        Apply point transformation on npz data according to the `transformer_instance`.

        Parameters
        -----------
        transformer_instance: vyperdatum.transformer.Transform
            Instance of the transformer class.

        Returns
        -----------
        bool:
            True if successful, otherwise False.
        """
        x, y, z, u = self.xyzu()
        success, xx, yy, zz = transformer_instance.transform_points(x, y, z,
                                                                    vdatum_check=vdatum_check)
        target_wkt = transformer_instance.crs_to.to_wkt()
        data = np.zeros([len(x), 4], dtype=np.float64)
        data[:, 0], data[:, 1], data[:, 2], data[:, 3] = xx, yy, zz, u
        minmax = np.array([np.min(data, 0), np.max(data, 0)])
        np.savez(self.input_file, wkt=np.array(target_wkt), data=data, minmax=minmax)
        return success

    @property
    def is_valid(self):
        return self.is_npz
