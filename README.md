<img align="right" src="https://upload.wikimedia.org/wikipedia/commons/7/79/NOAA_logo.svg" width="100">
<br/>

[![PyPI version](https://badge.fury.io/py/vyperdatum.svg)](https://badge.fury.io/py/vyperdatum)
[![DOI](https://zenodo.org/badge/785898982.svg)](https://zenodo.org/doi/10.5281/zenodo.13345073)
[![Read the Docs](https://readthedocs.org/projects/vyperdatum/badge/?version=latest)](https://vyperdatum.readthedocs.io/en/latest/)

## Vyperdatum

Vyperdatum is a NOAA OCS/NBS toolkit for performing high-accuracy vertical datum transformations using NOAA’s separation grids within the modern PROJ/GDAL ecosystem. It provides a high-level `Transformer` interface that builds PROJ pipelines from a source CRS (`crs_from`) to a target CRS (`crs_to`), and applies them consistently to point cloud and raster formats (e.g. GeoTIFF, BAG, VRBAG, LAZ, NPZ, and GeoParquet).

The goal of Vyperdatum is to make it easy to transform coastal and hydrographic data between tidal, orthometric, and ellipsoidal vertical datums (for example, NAD83(2011) ellipsoid heights to MLLW or NAVD88) while preserving full coordinate reference system metadata so that transformations are transparent and reproducible.

Typical use cases include:

- Normalizing hydrographic surveys to charting datums for ENC/RNC and bathymetric products  
- Building seamless coastal DEMs and bathymetric mosaics from surveys referenced to different vertical frames  
- Preparing inputs for coastal flood, storm surge, and inundation models that require a specific vertical datum  
- Converting between ellipsoidal, orthometric, and tidal datums for coastal GNSS/GNSS-tide workflows  

Under the hood, Vyperdatum uses a PROJ database augmented with NOAA grids and metadata. Transformation steps can be inferred automatically from `crs_from`/`crs_to`, or prescribed explicitly when you need fine-grained control over the pipeline. NOAA’s grid files and the updated `proj.db` are not bundled with the package; instead, you download them separately and point the `VYPER_GRIDS` environment variable at their location.


**Vyperdatum** [definition] 

## Installation
Vyperdatum requires `GDAL` which can be installed from the conda's conda-forge channel. Below, we first create a conda environment, install `GDAL` and Vperdatum.

```bash
conda create -n vd python=3.11
conda activate vd
conda install -c conda-forge proj=9.4 gdal=3.8.4 python-pdal
pip install vyperdatum
```
Before running vyperdatum, you need to download NOAA's datum files and the updated `proj.db` [![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.15184045.svg)](https://doi.org/10.5281/zenodo.15184045). Once downloaded, create a persistent environment variable `VYPER_GRIDS` to hold the path to directory where the downloaded grids and `proj.db` are located. 

## Usage
Vyperdatum offers a `Transformer` class to handle the transformation of point and raster data. The `Transformer` class applies transformation from `crs_from` to `crs_to` coordinate reference system. By default the transformation steps will be determined automatically:

```python
from vyperdatum.transformer import Transformer

crs_from = "EPSG:6346"            # NAD83(2011) 17N
crs_to = "EPSG:6346+NOAA:98"      # NAD83(2011) 17N + MLLW
tf = Transformer(crs_from=crs_from,
                 crs_to=crs_to,
                 )
```

Alternatively, you may manually prescribe the transformation steps:

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


Once an instance of the `Transformer` class is created, the `transform()` method can be called. Vyperdatum supports all GDAL-supported drivers, variable resolution BAG, LAZ and NPZ point-cloud files.

### transform
```python                
tf.transform(input_file=<PATH_TO_INPUT_RASTER_FILE>,
             output_file=<PATH_TO_OUTPUT_RASTER_FILE>
             )
```

You may also, directly call the file-specific transform methods instead of the generic `Transformer.transform()` method:

<details>
<summary>Click to see pseudo-code examples</summary>
            
```python
# dircet point transformation. x, y, z can be arrays, too.
x, y, z = 278881.198, 2719890.433, 0
xt, yt, zt = tf.transform_points(x, y, z, always_xy=True, allow_ballpark=False)

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
```
</details>

## Documentation

For a quick start, more detailed descriptions or search through the API, see Vyperdatums's documentation at: https://vyperdatum.readthedocs.io.