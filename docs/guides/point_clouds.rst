Point and point-cloud workflows
===============================

In addition to file-based raster transformation, Vyperdatum transforms
coordinates directly and transforms point-cloud files.

Direct point transformation
----------------------------

:meth:`~vyperdatum.transformer.Transformer.transform_points` transforms
arrays of coordinates without any file input or output. Lists or NumPy arrays
are accepted for ``x``, ``y``, and ``z``. A four-tuple is returned in the
order ``(success, x, y, z)``, where ``success`` is a boolean and the
remaining elements are the transformed coordinate arrays.

.. code-block:: python

   import numpy as np
   from vyperdatum.transformer import Transformer

   tf = Transformer(crs_from="EPSG:6346", crs_to="EPSG:6346+NOAA:98")
   xi, yi, zi = np.array([278881.198]), np.array([2719890.433]), np.array([0])
   success, xt, yt, zt = tf.transform_points(x=xi, y=yi, z=zi, always_xy=True)

An optional ``vdatum_check`` flag compares a sample of the transformed values
against the VDatum REST API and records discrepancies when the comparison
fails.

Point-cloud files
-----------------

Point-cloud files are transformed through the format-specific methods, each
of which reads the input, applies the transformation, and writes the output:

- LAZ via :meth:`~vyperdatum.transformer.Transformer.transform_laz`.
- NPZ via :meth:`~vyperdatum.transformer.Transformer.transform_npz`.
- XYZ via :meth:`~vyperdatum.transformer.Transformer.transform_xyz`.
- GeoParquet via
  :meth:`~vyperdatum.transformer.Transformer.transform_geoparquet`.
- PDAL-supported formats via
  :meth:`~vyperdatum.transformer.Transformer.transform_pdal`.

Because point-cloud transformation is not anchored to a raster pixel grid, it
is not subject to the same-horizontal-CRS restriction that applies to the
raster path, and it is therefore the recommended route when a change of
horizontal CRS is required.
