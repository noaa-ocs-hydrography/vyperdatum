import os
from typing import Optional
import logging
import subprocess
import json
import pdal
from vyperdatum.drivers.base import Driver
from vyperdatum.utils.crs_utils import auth_code


logger = logging.getLogger("root_logger")


class PDAL(Driver):
    def __init__(self, input_file: str, output_file: str, invalid_error: bool = True) -> None:
        """
        Load a pdal-supported file or a remote point cloud format
        such as Entwine Pointe Tile (EPT).

        Parameters
        ----------
        input_file: str
            Full file path or address to a remote point cloud format
            such as Entwine Pointe Tile (EPT).
        output_file: str
            Full file path for the output file.
        invalid_error: bool, default True
            If True, throws an error when the input file has an unexpected format.

        Raises
        --------
        ValueError:
            If the input file is not recognized.

        Returns
        -----------
        None
        """
        super().__init__()
        self.input_file = input_file
        self.output_file = output_file
        if not self.input_file.lower().startswith("http") and not os.path.isfile(self.input_file):
            raise FileNotFoundError(f"The input file not found at {self.input_file}.")
        _, err = self.info(fname=self.input_file, args=["--schema"])
        self._is_valid = ~bool(err)
        if err and invalid_error:
            msg = f"PDAL doesn't recognize or cannot access the input: {self.input_file}"
            logger.exception(msg)
            raise ValueError(msg)
        return

    def info(self,
             fname: str,
             args: Optional[list[str]] = None) -> tuple[Optional[dict], Optional[str]]:
        """
        Spawn a new process to run `pdal info` and capture its output.

        Parameters
        -----------
        fname: str
            Path to the input file.
        args: Optional[list[str]]
            Optional pdal info arguments.

        Returns
        --------
        stdout: Optional[dict], std_err: Optional[str]
            standard output and error.
        """
        try:
            sout, serr = dict({}), None
            resp = subprocess.run(["pdal", "info", *args, fname],
                                  stderr=subprocess.PIPE,
                                  stdout=subprocess.PIPE
                                  )
            sout = json.loads(resp.stdout.decode()) if resp.stdout else None
            serr = resp.stderr.decode() if resp.stderr else None
        except Exception as e:
            logger.exception(str(e))
            sout, serr = dict({}), None
        return sout, serr

    def exec_pipeline(self, pipe_string: str):
        """
        Execute a general pdal pipeline.

        Parameters
        -----------
        pipe_string: str
            PDAL's pipeline json object in string format.
        """
        try:
            pipe_string = os.linesep.join([s for s in pipe_string.splitlines() if s])
            p = pdal.Pipeline(pipe_string)
            count = p.execute()
            arrays = p.arrays
            metadata = p.metadata
            log = p.log
        except Exception as e:
            logger.exception(str(e))
        return

    def fetch_entwine(self,
                      bounds: Optional[list[float]],
                      resolution: Optional[int],
                      output_format: str = "writers.las"
                      ) -> bool:
        """
        Download a subset of Etwine resource defined by `bounds: [x_min, x_max, y_min, y_max]`.
        The subset data is converted into the `output_format` which is a
        PDAL type.

        Parameters
        -----------
        bounds: Optional[list[float]]
            Bounding box that delimits the remote Etwine resource to be downloaded.
            It should be a list of float values in this order: [x_min, x_max, y_min, y_max].
        output_format: str, default 'writers.las'
            PDAL writers type; defaults to 'writers.las'.
            See more https://pdal.io/en/2.8.1/stages/writers.html.

        Returns
        --------
        bool
            True if download succeed, otherwise False.
        """
        bounds = f',"bounds": "([{bounds[0]}, {bounds[1]}], [{bounds[2]}, {bounds[3]}])"' if bounds else ''
        resolution = f',"resolution": {resolution}' if resolution else ''
        try:
            succeed = False
            out_file = self.output_file.replace("\\", "/")
            pip_string = f'''
                        [
                        {{
                        "type":"readers.ept",
                        "filename":"{self.input_file}"
                        {bounds}
                        {resolution}
                        }},
                        {{
                        "type":"{output_format}",
                        "filename":"{out_file}"
                        }}
                        ]
                        '''
            self.exec_pipeline(pipe_string=pip_string)
            succeed = os.path.isfile(self.output_file)
        except Exception as e:
            succeed = False
            logger.error(f"Error in fetch_entwine: {e}")
        return succeed

    def wkt(self, fname: str) -> str:
        """
        Return the WKT associated with the input file `fname`.

        Parameters
        -----------
        fname: str
            Path to the input file.

        Raises
        -----------
        ValueError
            When `pdal info --metadata <fname>` fails.

        Returns
        -----------
        str
        """
        resp, err = self.info(fname=fname, args=["--metadata"])
        if bool(err):
            raise ValueError(f"Error in getting metadata: {err}")
        # expected keys in metadata.srs: ['compoundwkt', 'horizontal', 'isgeocentric', 'isgeographic', 'json', 'prettycompoundwkt', 'prettywkt', 'proj4', 'units', 'vertical', 'wkt']
        return resp["metadata"]["srs"]["compoundwkt"]

    @property
    def is_valid(self):
        return self._is_valid

    def transform(self, transformer_instance, vdatum_check: bool) -> None:
        """
        Create a PDAL pipeline to apply CRS transformation on the input data
        according to the `transformer_instance`.

        Parameters
        -----------
        transformer_instance: vyperdatum.transformer.Transform
            Instance of the transformer class.

        Returns
        -----------
        None
        """
        in_file = self.input_file.replace("\\", "/")
        out_file = self.output_file.replace("\\", "/")
        pip_string = f'''
                      [
                      "{in_file}",
                      {{
                      "type":"filters.reprojection",
                      "out_srs":"{auth_code(transformer_instance.crs_to)}"
                      }},
                      "{out_file}"
                      ]
                      '''
        self.exec_pipeline(pipe_string=pip_string)
        return


if __name__ == "__main__":
    from vyperdatum.transformer import Transformer
    import pyproj as pp
    # fname = r"C:\Users\mohammad.ashkezari\Documents\projects\vyperdatum\untrack\data\raster\BlueTopo_BC25L26L_20230919.tiff"
    # fname = "https://na-c.entwine.io/dublin/ept.json"
    fname = r"C:\Users\mohammad.ashkezari\Documents\projects\vyperdatum\untrack\data\point\laz\ma2021_cent_east_Job1082403.laz"
    oname = r"C:\Users\mohammad.ashkezari\Documents\projects\vyperdatum\untrack\data\point\laz\_t_ma2021_cent_east_Job1082403.laz"
    p = PDAL(input_file=fname, output_file=oname)
    crs_from = "EPSG:6348+EPSG:5703"
    crs_to = "EPSG:6348+NOAA:5320"
    steps = ["EPSG:6348+EPSG:5703", "EPSG:6318+EPSG:5703", "EPSG:6318+NOAA:5320", "EPSG:6348+NOAA:5320"]
    tf = Transformer(crs_from=crs_from, crs_to=crs_to, steps=steps)
    p.transform(tf)
    wkt = p.wkt(fname=fname)
    print(wkt)
    # print(pp.CRS(wkt).to_authority())


    # pdl = PDAL(input_file="https://na-c.entwine.io/dublin/ept.json",
    #            output_file=r"C:\Users\mohammad.ashkezari\Documents\projects\vyperdatum\untrack\data\pdal\entwine.las")
    # succeed = pdl.fetch_entwine(bounds=None, resolution=20, output_format="writers.las")
    # assert succeed, "fetch_entwine failed!"
