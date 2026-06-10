Vyperdatum
==========

Vyperdatum is a NOAA OCS/NBS toolkit for high-accuracy vertical datum
transformations that uses NOAA's separation grids within the modern
PROJ/GDAL ecosystem. A high-level :class:`~vyperdatum.transformer.Transformer`
interface builds PROJ pipelines from a source CRS (``crs_from``) to a target
CRS (``crs_to``) and applies them consistently across point-cloud and raster
formats, including GeoTIFF, BAG, VRBAG, LAZ, NPZ, and GeoParquet.

The intent of Vyperdatum is to make transformations between tidal,
orthometric, and ellipsoidal vertical datums straightforward while full
coordinate reference system metadata is preserved, so that transformations
remain transparent and reproducible.

.. toctree::
   :maxdepth: 2
   :caption: Getting started

   overview
   installation
   quickstart

.. toctree::
   :maxdepth: 2
   :caption: Guides

   guides/configuration
   guides/raster_transformation
   guides/formats_and_drivers
   guides/point_clouds

.. toctree::
   :maxdepth: 2
   :caption: Reference

   api/vyperdatum/index

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
