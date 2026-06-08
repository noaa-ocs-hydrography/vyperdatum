Supported formats and drivers
=============================

A single ``transform`` entry point accepts a range of raster and point-cloud
formats. The input format is detected automatically, and the corresponding
file-specific routine is dispatched. The detection order is reflected below.

Detected formats
----------------

- **Variable-resolution BAG** is detected first and handled by
  :meth:`~vyperdatum.transformer.Transformer.transform_vrbag`.
- **GeoParquet** point data is handled by
  :meth:`~vyperdatum.transformer.Transformer.transform_geoparquet`.
- **LAZ** point clouds are handled by
  :meth:`~vyperdatum.transformer.Transformer.transform_laz`.
- **NPZ** point arrays are handled by
  :meth:`~vyperdatum.transformer.Transformer.transform_npz`.
- **XYZ** point text is handled by
  :meth:`~vyperdatum.transformer.Transformer.transform_xyz`.
- **GDAL-supported rasters** (for example GeoTIFF) are handled by
  :meth:`~vyperdatum.transformer.Transformer.transform_raster`.
- **PDAL-supported point clouds** are handled by
  :meth:`~vyperdatum.transformer.Transformer.transform_pdal` as a final
  fallback.

When an input matches none of the supported types, ``NotImplementedError``
is raised.

Driver modules
--------------

The format-specific reading and writing logic is organized under the
``vyperdatum.drivers`` package. The full driver API is generated in the
:doc:`/api/vyperdatum/index` reference. The raster path additionally relies on the
raster and spatial helpers under ``vyperdatum.utils``.

Notes on the raster path
------------------------

The raster path applies the cutline two-pass pipeline and the same-CRS
requirement described in :doc:`raster_transformation`. Point-cloud drivers
are not subject to the same-horizontal-CRS restriction and are the
recommended route when a horizontal CRS change is required.
