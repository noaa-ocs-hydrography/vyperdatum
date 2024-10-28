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
conda install -c conda-forge gdal=3.8.4
pip install vyperdatum
```

## Usage
Vyperdatum offers a `Transformer` class to handle the transformation of point and raster data. The `Transformer` class applies transformation from `crs_from` to `crs_to` coordinate reference systems. The transformation steps can be prescribed manually or let the `Pipeline` class to infer: 

```python
from vyperdatum.transformer import Transformer
from vyperdatum.pipeline import Pipeline

crs_from = "EPSG:6346"
crs_to = "EPSG:6346+NOAA:5224"
tf = Transformer(crs_from=crs_from,
                 crs_to=crs_to,
                 steps=["EPSG:6346", "EPSG:6319", "EPSG:6318+NOAA:5224", "EPSG:6346+NOAA:5224"]
                 #  steps=Pipeline(crs_from=crs_from, crs_to=crs_to).linear_steps()
                 #  steps=Pipeline(crs_from=crs_from, crs_to=crs_to).graph_steps()                 
                 )
```

Once an instance of the `Transformer` class is created, raster or point transformation methods can be called.

### raster transform                
```python                
tf.transform_raster(input_file=<PATH_TO_INPUT_RASTER_FILE>,
                    output_file=<PATH_TO_OUTPUT_RASTER_FILE>
                    )
```

### point transform                
```python
# random values
x, y, z = 278881.198, 2719890.433, 0
xt, yt, zt = tf.transform_points(x, y, z, always_xy=True, allow_ballpark=False)
```

Vyperdatum `Transformer` class offers a few methods to support file formats that are not supported by GDAL, such as Variable Resolution BAG, and LAZ point cloud data. 

#### VRBAG Transform
```python
input_file = "PATH_TO_INPUT_VRBAG.bag"
output_file = "PATH_TO_OUTPUT_VRBAG.bag"
tf.transform_vrbag(input_file=input_file, output_file=output_file)
```

#### LAZ Transform
```python
input_file = "PATH_TO_INPUT_LAZ.laz"
output_file = "PATH_TO_OUTPUT_LAZ.laz"
tf.transform_laz(input_file=input_file, output_file=output_file)
```

## Documentation

For a quick start, more detailed descriptions or search through the API, see Vyperdatums's documentation at: https://vyperdatum.readthedocs.io.