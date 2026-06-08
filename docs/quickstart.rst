Quickstart
==========

The :class:`~vyperdatum.transformer.Transformer` class handles the
transformation of point and raster data. A transformer is constructed from a
source CRS (``crs_from``) and a target CRS (``crs_to``). By default, the
transformation steps are determined automatically.

Automatic steps
---------------

.. code-block:: python

   from vyperdatum.transformer import Transformer

   crs_from = "EPSG:6346"            # NAD83(2011) 17N (vertical: Ellipsoid)
   crs_to = "EPSG:6346+NOAA:98"      # NAD83(2011) 17N + MLLW
   tf = Transformer(crs_from=crs_from,
                    crs_to=crs_to,
                    )

Prescribed steps
----------------

The transformation steps may also be prescribed explicitly. Each step is a
dictionary that names a source and target CRS as ``authority:code`` and a
boolean ``v_shift`` flag indicating whether the step applies a vertical
shift.

.. code-block:: python

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

Transforming a file
-------------------

Once a transformer has been created, the ``transform`` method is called with
an input path and an output path. The input format is detected automatically,
and the appropriate file-specific routine is dispatched. GDAL-supported
raster drivers, variable-resolution BAG, LAZ, NPZ, XYZ, and GeoParquet inputs
are supported.

.. code-block:: python

   tf.transform(input_file="<PATH_TO_INPUT_FILE>",
                output_file="<PATH_TO_OUTPUT_FILE>")

File-specific methods
---------------------

The file-specific transform methods may be called directly instead of the
generic ``transform`` method. Direct point transformation accepts lists or
NumPy arrays for ``x``, ``y``, and ``z`` and returns a four-tuple in the
order ``(success, x, y, z)``.

.. code-block:: python

   import numpy as np

   # Direct point transformation.
   xi, yi, zi = np.array([278881.198]), np.array([2719890.433]), np.array([0])
   success, xt, yt, zt = tf.transform_points(x=xi, y=yi, z=zi, always_xy=True)

   # GDAL-supported raster transform.
   tf.transform_raster(input_file="<PATH_TO_INPUT_RASTER_FILE>",
                       output_file="<PATH_TO_OUTPUT_RASTER_FILE>")

   # VRBAG transform.
   tf.transform_vrbag(input_file="<PATH_TO_INPUT_VRBAG_FILE>",
                      output_file="<PATH_TO_OUTPUT_VRBAG_FILE>")

   # LAZ transform.
   tf.transform_laz(input_file="<PATH_TO_INPUT_LAZ_FILE>",
                    output_file="<PATH_TO_OUTPUT_LAZ_FILE>")

   # NPZ transform.
   tf.transform_npz(input_file="<PATH_TO_INPUT_NPZ_FILE>",
                    output_file="<PATH_TO_OUTPUT_NPZ_FILE>")

   # GeoParquet transform.
   tf.transform_geoparquet(input_file="<PATH_TO_INPUT_PARQUET_FILE>",
                           output_file="<PATH_TO_OUTPUT_PARQUET_FILE>")

The supported formats and the behavior of the raster path are described in
:doc:`guides/formats_and_drivers` and :doc:`guides/raster_transformation`.
