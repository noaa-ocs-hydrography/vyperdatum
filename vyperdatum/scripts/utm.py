import numpy as np
import pandas as pd
import geopandas as gpd
from shapely.geometry import Point
from pyproj import Transformer
import pyproj as pp

def generate_random_utm_points(utm_zone, n_points=100):
    """
    Generate random geographic points in a given UTM zone.

    Parameters:
        utm_zone (int): UTM zone number (1 to 60).
        hemisphere (str): 'N' for Northern or 'S' for Southern Hemisphere.
        n_points (int): Number of points to generate.

    Returns:
        GeoDataFrame: with geometry, UTM, and lat/lon coordinates.
    """
    if not 1 <= utm_zone <= 60:
        raise ValueError("UTM zone must be between 1 and 60.")
    hemisphere = "N"


    # Geographic bounds of UTM zone
    lon_min = (utm_zone - 1) * 6 - 180
    lon_max = lon_min + 6
    lat_min = 0 if hemisphere.upper() == 'N' else -80
    lat_max = 84 if hemisphere.upper() == 'N' else 0

    # Generate random lat/lon within bounds
    lats = np.random.uniform(lat_min, lat_max, n_points)
    lons = np.random.uniform(lon_min, lon_max, n_points)



    crs_utm_83 = f"EPSG:{26900 + utm_zone}"
    crs_geodetic_83 = ":".join(pp.CRS(crs_utm_83).geodetic_crs.to_authority())

    crs_utm_2011 = f"EPSG:{6329 + utm_zone}"
    crs_geodetic_2011 = ":".join(pp.CRS(crs_utm_2011).geodetic_crs.to_authority())


    # Transform to UTM
    transformer_83 = Transformer.from_crs(crs_geodetic_83, crs_utm_83, always_xy=True)
    eastings_83, northings_83 = transformer_83.transform(lons, lats)

    transformer_2011 = Transformer.from_crs(crs_geodetic_2011, crs_utm_2011, always_xy=True)
    eastings_2011, northings_2011 = transformer_2011.transform(lons, lats)

    # Convert zipped pairs to NumPy arrays
    coords_83 = np.column_stack((eastings_83, northings_83))
    coords_2011 = np.column_stack((eastings_2011, northings_2011))

    # Compute deviation (Euclidean norm of differences)
    deviation = np.linalg.norm(coords_2011 - coords_83, axis=1)

    # Create GeoDataFrame
    df = pd.DataFrame({
        'Zone': [utm_zone] * n_points,
        'NAD83': [crs_geodetic_83] * n_points,
        'UTM_83': [crs_utm_83] * n_points,
        'NAD83_2011': [crs_geodetic_2011] * n_points,
        'UTM_83_2011': [crs_utm_2011] * n_points,
        'Longitude': lons,
        'Latitude': lats,
        'Easting_83': eastings_83,
        'Northing_83': northings_83,
        'Easting_2011': eastings_2011,
        'Northing_2011': northings_2011,
        'Deviation': deviation
    })

    return df


if __name__ == "__main__":
    utm_zone = 17  # Example UTM zone
    n_points = 100  # Number of points to generate
    df = generate_random_utm_points(utm_zone, n_points)
    print(df)