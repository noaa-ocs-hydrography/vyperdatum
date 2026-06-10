Overview
========

Vyperdatum performs vertical datum transformations for coastal and
hydrographic data within the PROJ/GDAL ecosystem. NOAA's separation grids
and a PROJ database augmented with NOAA metadata are used to convert between
tidal, orthometric, and ellipsoidal vertical datums (for example,
NAD83(2011) ellipsoid heights to MLLW or NAVD88) while the full coordinate
reference system metadata is retained.

A high-level :class:`~vyperdatum.transformer.Transformer` is provided. The
transformer is constructed from a source CRS and a target CRS and is then
applied to point-cloud and raster files through a single ``transform``
entry point.

Typical use cases
-----------------

- Hydrographic surveys are normalized to charting datums for ENC/RNC and
  bathymetric products.
- Inputs are prepared for coastal flood, storm surge, and inundation models
  that require a specific vertical datum.
- Coordinates are converted between ellipsoidal, orthometric, and tidal
  datums for coastal GNSS and GNSS-tide workflows.

How it works
------------

Transformation steps can be inferred automatically from ``crs_from`` and
``crs_to``, or prescribed explicitly when fine-grained control over the
pipeline is required. Under the hood, a PROJ database augmented with NOAA
grids and metadata is used. NOAA's grid files and the updated ``proj.db``
are not bundled with the package; these are downloaded separately, and the
``VYPER_GRIDS`` environment variable is pointed at their location. The
:doc:`installation` and :doc:`guides/configuration` pages describe this
setup.

Relationship to the National Bathymetric Source
------------------------------------------------

Vyperdatum can be used as a standalone package as long as the separation
grids and the custom ``proj.db`` are available. Within NOAA, Vyperdatum is
used across the National Bathymetric Source (NBS) pipeline, where it is
relied upon by the ``fuse`` software. Compatibility with the NBS source code
is treated as a constraint on Vyperdatum changes.
