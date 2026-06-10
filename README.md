<img align="right" src="https://upload.wikimedia.org/wikipedia/commons/7/79/NOAA_logo.svg" width="100">

<img src="docs/_static/vyperdatum-logo.svg" alt="Vyperdatum" height="84">

<br/>

[![PyPI version](https://img.shields.io/pypi/v/vyperdatum)](https://pypi.org/project/vyperdatum/)
[![DOI](https://img.shields.io/badge/DOI-10.5281%2Fzenodo.18893503-blue)](https://doi.org/10.5281/zenodo.18893503)
[![Read the Docs](https://readthedocs.org/projects/vyperdatum/badge/?version=latest)](https://vyperdatum.readthedocs.io/en/latest/)

## Vyperdatum

Vyperdatum is a NOAA OCS/NBS toolkit for performing high-accuracy vertical datum transformations using NOAA’s separation grids within the modern PROJ/GDAL ecosystem. It provides a high-level `Transformer` interface that builds PROJ pipelines from a source CRS (`crs_from`) to a target CRS (`crs_to`), and applies them consistently to point cloud and raster formats (e.g. GeoTIFF, BAG, VRBAG, LAZ, NPZ, and GeoParquet).

The goal of Vyperdatum is to make it easy to transform coastal and hydrographic data between tidal, orthometric, and ellipsoidal vertical datums (for example, NAD83(2011) ellipsoid heights to MLLW or NAVD88) while preserving full coordinate reference system metadata so that transformations are transparent and reproducible.

Typical use cases include:

- Normalizing hydrographic surveys to charting datums for ENC/RNC and bathymetric products  
- Preparing inputs for coastal flood, storm surge, and inundation models that require a specific vertical datum  
- Converting between ellipsoidal, orthometric, and tidal datums for coastal GNSS/GNSS-tide workflows  

Under the hood, Vyperdatum uses a PROJ database augmented with NOAA grids and metadata. Transformation steps can be inferred automatically from `crs_from`/`crs_to`, or prescribed explicitly when fine-grained control over the pipeline is required. NOAA’s grid files and the updated `proj.db` are not bundled with the package; instead, they are downloaded separately and the `VYPER_GRIDS` environment variable is pointed at their location.



## Installation
Vyperdatum requires `GDAL`, which is most reliably installed from the conda-forge channel. In the steps below, a conda environment is created first, then `GDAL` and Vyperdatum are installed into it.

```bash
conda create -n vd python=3.11
conda activate vd
conda install -c conda-forge proj=9.6 gdal python-pdal
pip install vyperdatum
```
Before vyperdatum is run, NOAA's datum files and the updated `proj.db` must be downloaded [![DOI](https://img.shields.io/badge/DOI-10.5281%2Fzenodo.18893503-blue)](https://doi.org/10.5281/zenodo.18893503). Once downloaded, a persistent environment variable `VYPER_GRIDS` is set to the directory that holds the downloaded grids and `proj.db`. 

## Usage
Vyperdatum offers a `Transformer` class to handle the transformation of point and raster data. The `Transformer` class applies transformation from `crs_from` to `crs_to` coordinate reference system. By default the transformation steps will be determined automatically:

```python
from vyperdatum.transformer import Transformer

crs_from = "EPSG:6346"            # NAD83(2011) 17N (vertical: Ellipsoid)
crs_to = "EPSG:6346+NOAA:98"      # NAD83(2011) 17N + MLLW
tf = Transformer(crs_from=crs_from,
                 crs_to=crs_to,
                 )
```

Alternatively, the transformation steps may be prescribed manually:

```python
from vyperdatum.transformer import Transformer

crs_from = "EPSG:6346"            # NAD83(2011) 17N
crs_to = "EPSG:6346+NOAA:98"      # NAD83(2011) 17N + MLLW
steps = [{"crs_from": "EPSG:6346", "crs_to": "EPSG:6318", "v_shift": False},
         {"crs_from": "EPSG:6319", "crs_to": "EPSG:6318+NOAA:98", "v_shift": True},
         {"crs_from": "EPSG:6318", "crs_to": "EPSG:6346", "v_shift": False}
         ]
tf = Transformer(crs_from=crs_from,
                 crs_to=crs_to,
                 steps=steps
                 )
```


Once an instance of the `Transformer` class is created, the `transform()` method can be called. The input format is detected automatically. GDAL-supported raster drivers, variable-resolution BAG, LAZ, NPZ, XYZ, and GeoParquet inputs are supported, with a PDAL fallback for additional point-cloud formats.

### transform
```python                
tf.transform(input_file=<PATH_TO_INPUT_RASTER_FILE>,
             output_file=<PATH_TO_OUTPUT_RASTER_FILE>
             )
```

The file-specific transform methods may also be called directly instead of the generic `Transformer.transform()` method:

<details>
<summary>Click to see pseudo-code examples</summary>
            
```python
# Direct point transformation. The input x, y, z can be lists or numpy arrays.
# transform_points returns a tuple in the order (success, x, y, z).
import numpy as np
xi, yi, zi = np.array([278881.198]), np.array([2719890.433]), np.array([0])
success, xt, yt, zt = tf.transform_points(x=xi, y=yi, z=zi, always_xy=True)

# GDAL-supported raster transform  
tf.transform_raster(input_file=<PATH_TO_INPUT_RASTER_FILE>,
                    output_file=<PATH_TO_OUTPUT_RASTER_FILE>
                    )

# VRBAG transform
tf.transform_vrbag(input_file=<PATH_TO_INPUT_VRBAG_FILE>,
                   output_file=<PATH_TO_OUTPUT_VRBAG_FILE>
                   )

# LAZ transform
tf.transform_laz(input_file=<PATH_TO_INPUT_LAZ_FILE>,
                 output_file=<PATH_TO_OUTPUT_LAZ_FILE>
                 )

# NPZ transform
tf.transform_npz(input_file=<PATH_TO_INPUT_NPZ_FILE>,
                 output_file=<PATH_TO_OUTPUT_NPZ_FILE>
                 )

# XYZ transform
tf.transform_xyz(input_file=<PATH_TO_INPUT_XYZ_FILE>,
                 output_file=<PATH_TO_OUTPUT_XYZ_FILE>
                 )

# GeoParquet transform
tf.transform_geoparquet(input_file=<PATH_TO_INPUT_PARQUET_FILE>,
                        output_file=<PATH_TO_OUTPUT_PARQUET_FILE>
                        )
```
</details>

## Documentation

For a quick start, more detailed descriptions or search through the API, see Vyperdatum's documentation at: https://vyperdatum.readthedocs.io.