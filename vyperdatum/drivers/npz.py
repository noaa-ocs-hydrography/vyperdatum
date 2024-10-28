import warnings
import numpy as np
import pathlib
from collections import Counter
from typing import Tuple


class NPZ():
    """
    Handle loading and parsing of a .npz (numpy arrays) file.

    Attributes
    ----------
    fname: str
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

    def __init__(self, fname: str) -> None:
        """
        Load a numpy .npz file (collection of numpy arrays).

        Parameters
        ----------
        fname: str
            Full file path.
        """
        self.fname = fname
        self.content = self.load()

    def load(self) -> np.lib.npyio.NpzFile:
        """
        Load a numpy .npz file (collection of numpy arrays).

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
        numpy.lib.npyio.NpzFile
        """
        if not self.fname:
            raise ValueError("Invalid or unspecified .npz file path.")
        fname = pathlib.Path(self.fname)
        if not fname.is_file():
            raise FileNotFoundError(f"The npz file not found at: {fname}")
        if fname.suffix.lower() != ".npz":
            warnings.warn(("Expected a file with '.npz' extension"
                           f"but receieved {fname.suffix.lower()}."))
        schema = ["wkt", "data", "minmax"]
        bundle = np.load(fname)
        if Counter(bundle.files) != Counter(schema):
            raise TypeError(("Expected the following keys in the .npz file: "
                             f"{schema}, but receieved {bundle.files}."))
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
