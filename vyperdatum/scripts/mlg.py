import os
from typing import Optional, List, Union
from pathlib import Path
import numpy as np
import pandas as pd
import geopandas as gpd
from shapely.geometry import Point
from vyperdatum.transformer import Transformer


class XYZ:
    def __init__(self,
                 input_file: str,
                 skiprows: Optional[int] = None,
                 col_names: Optional[List[str]] = None,
                 negate_z: bool = False,
                 unit_conversion: float = 1.0
                 ):
        self.input_file = input_file
        self.skiprows = self._detect_data_start() if skiprows is None else skiprows
        self.col_names = col_names
        self.negate_z = negate_z
        self.unit_conversion = unit_conversion
        self.df = self._parse()

    def _detect_data_start(self) -> Optional[int]:
        with open(self.input_file, "r") as f:
            for i, line in enumerate(f):
                parts = line.strip().split(",")
                if len(parts) >= 3:
                    try:
                        float(parts[0])
                        float(parts[1])
                        float(parts[2])
                        return i
                    except ValueError:
                        continue
        raise ValueError("No valid data lines found in file.")

    def _parse(self) -> pd.DataFrame:
        """
        Reads the .XYZ file into a pandas DataFrame.
        If self.col_names is not set, assumes the first three columns are x, y, z.

        Returns:
            pd.DataFrame: the parsed data
        """
        df = pd.read_csv(self.input_file, sep=",", skiprows=self.skiprows)
        num_cols = df.shape[1]
        if self.col_names:
            base_names = self.col_names
        else:
            base_names = ["x", "y", "z"]
        if num_cols > len(base_names):
            column_names = base_names + [f"col{i}" for i in range(len(base_names)+1, num_cols + 1)]
        else:
            column_names = base_names[:num_cols]
        df.columns = column_names
        if self.negate_z:
            df["z"] = -df["z"]
        df["z"] *= self.unit_conversion
        return df

    def transform(self,
                  crs_from: str,
                  crs_to: str,
                  steps: Optional[List[dict]] = None
                  ) -> pd.DataFrame:
        """
        Transform the coordinates from one CRS to another using a Transformer.

        Parameters:
        -----------
            crs_from (str): The source coordinate reference system.
            crs_to (str): The target coordinate reference system.
        """
        tf = Transformer(crs_from=crs_from, crs_to=crs_to, steps=steps)
        x, y, z = self.df["x"].values, self.df["y"].values, self.df["z"].values
        success, xt, yt, zt = tf.transform_points(x, y, z,
                                                  always_xy=True,
                                                  allow_ballpark=False,
                                                  only_best=True,
                                                  vdatum_check=False)
        if not success:
            raise ValueError("Transformation failed.")
        self.df["x_t"], self.df["y_t"], self.df["z_t"] = xt, yt, zt
        if self.negate_z:
            self.df["z"] = -self.df["z"]
            self.df["z_t"] = -self.df["z_t"]
        self.df["Uncertainty"] = 1 + 0.02 * self.df["z_t"].abs()
        return self.df

    def to_gpkg(self,
                crs: str,
                output_file: str) -> None:
        tdf = pd.DataFrame({"x": self.df["x_t"].values,
                            "y": self.df["y_t"].values,
                            "Elevation": self.df["z_t"].values,
                            })
        tdf["geometry"] = tdf.apply(lambda row: Point(row["x"], row["y"], row["Elevation"]), axis=1)
        tdf["Uncertainty"] = self.df["Uncertainty"].values
        gdf = gpd.GeoDataFrame(tdf, geometry="geometry", crs=crs)
        gdf.to_file(output_file, driver="GPKG")
        return


# from vyperdatum.pipeline import Pipeline
# import sys
# # print(Pipeline(crs_from="ESRI:103060", crs_to="EPSG:6318").graph_steps())
# print(Pipeline(crs_from="EPSG:6783", crs_to="EPSG:6344").graph_steps())
# sys.exit()



input_file = r"C:\Users\mohammad.ashkezari\Documents\projects\vyperdatum\untrack\data\point\MLG\Original\AR_01_BAR_20240117_PR\AR_01_BAR_20240117_PR.XYZ"
crs_from = "EPSG:3452+NOAA:1502" # MLG depth not usable for now, use NOAA:1502 USACE height
crs_to = "EPSG:6344+NOAA:100"  # MLLW depth (due to current db issues, I use NOAA:101 and negate to get depth)
negate_z = True  # MLG depth is negative, NOAA:98 is positive


steps = [{"crs_from": "EPSG:3452", "crs_to": "EPSG:6318", "v_shift": False},
         {"crs_from": "EPSG:6318+NOAA:1502", "crs_to": "EPSG:6318+NOAA:101", "v_shift": True},
         {"crs_from": "EPSG:6318", "crs_to": "EPSG:6344", "v_shift": False}
         ]

xyz = XYZ(input_file=input_file,
          negate_z=negate_z,
          unit_conversion=0.3048006096
        #   skiprows=15,
        #   col_names=["xi", "yi", "zi"]
          )
df = xyz.transform(crs_from=crs_from, crs_to=crs_to,
                   steps=steps
                   )
output_file = input_file.replace("Original", "Manual").replace(".XYZ", ".gpkg")
os.makedirs(os.path.dirname(output_file), exist_ok=True)
xyz.to_gpkg(crs=crs_to, output_file=output_file)

print(df.head())


