import os
import glob
import pathlib
import pandas as pd
from vyperdatum.transformer import Transformer
import geopandas as gpd
from shapely.geometry import Point


if __name__ == "__main__":
    steps = [
            {"crs_from": "ESRI:102684", "crs_to": "EPSG:4267"},
            {"crs_from": "EPSG:4267+EPSG:5702", "crs_to": "EPSG:6318+NOAA:98"},
            {"crs_from": "EPSG:6318", "crs_to": "EPSG:6348"}
            ]
    input_file = r"C:\Users\mohammad.ashkezari\Desktop\BASIN 3-27-24.csv"
    temp_file = r"C:\Users\mohammad.ashkezari\Desktop\temp.csv"
    output_file = r"C:\Users\mohammad.ashkezari\Desktop\BASIN.csv"
    df = pd.read_csv(input_file)
    df["Raw Elevation Reading"] = -1 * df["Raw Elevation Reading"]
    x, y, z = df["Easting"].values, df["Northing"].values, df["Raw Elevation Reading"].values
    tf = Transformer(crs_from=steps[0]["crs_from"],
                     crs_to=steps[-1]["crs_to"],
                     steps=steps)
    xt, yt, zt = tf.transform_points(x, y, z,
                                     always_xy=True,
                                     allow_ballpark=False,
                                     only_best=True,
                                     vdatum_check=False)
    df["x_t"], df["y_t"] = xt, yt
    df["z_t"] = zt
    df.to_csv(output_file, index=False)

    tdf = pd.DataFrame({"x": xt, "y": yt, "z": zt})
    tdf.to_csv(temp_file, index=False)
    tdf["geometry"] = tdf.apply(lambda row: Point(row["x"], row["y"], row["z"]), axis=1)
    gdf = gpd.GeoDataFrame(tdf, geometry="geometry", crs="EPSG:6348+NOAA:98")
    gdf.to_file(output_file.replace("csv", "gpkg"), driver="GPKG")
