<img align="right" src="https://upload.wikimedia.org/wikipedia/commons/7/79/NOAA_logo.svg" width="100">
<br/>

[![PyPI version](https://badge.fury.io/py/vyperdatum.svg)](https://badge.fury.io/py/vyperdatum)
[![DOI](https://zenodo.org/badge/785898982.svg)](https://zenodo.org/doi/10.5281/zenodo.13345073)
[![Read the Docs](https://readthedocs.org/projects/vyperdatum/badge/?version=latest)](https://vyperdatum.readthedocs.io/en/latest/)

## Vyperdatum

**Vyperdatum** [definition] 

## Installation
Vyperdatum requires `GDAL` which can be installed from the conda's conda-forge channel. Below, we first create a conda environment, install `GDAL` and Vperdatum.

```bash
conda create -n vd python=3.11
conda activate vd
conda install -c conda-forge proj=9.4 gdal=3.8.4 python-pdal
pip install vyperdatum
```
Before running vyperdatum, you need to copy NOAA's datum files and the updated `proj.db` into the PROJ data directory [download link will be added here]. This process may get automated in the future. The Proj data directory path can be found here:

```python
import pyproj as pp
pp.datadir.get_data_dir()
```

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