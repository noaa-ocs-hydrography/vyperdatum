Environment and PROJ configuration
==================================

Vyperdatum depends on a PROJ database augmented with NOAA grids and on a set
of NOAA separation grids. Their location and PROJ's runtime behavior are
controlled through environment variables. Several of these variables are set
by the package itself at import time; one must be set by the caller before
the package is imported.

``VYPER_GRIDS``
---------------

``VYPER_GRIDS`` is the only variable that must be provided externally. It
points at the directory that holds the downloaded NOAA grids and the custom
``proj.db``. It is read at import time, and the directory, the ``proj.db``
file, and a set of required grid files are validated. If the variable is
unset, points at a missing directory, or the directory is missing required
files, an informative error is raised before any transformation is attempted.

PROJ variables set by the package
----------------------------------

When the package is imported, the following are configured before PROJ is
initialized:

- ``PROJ_NETWORK`` is set to ``ON`` so that PROJ may retrieve grids over the
  network when needed.
- ``PROJ_USER_WRITABLE_DIRECTORY`` is set to ``VYPER_GRIDS`` when that
  variable is present, so that any network-retrieved cache is written into
  the directory PROJ is configured to search.
- ``PROJ_DATA`` is set to ``VYPER_GRIDS`` so that the augmented ``proj.db``
  and the NOAA grids are discovered.

A log line reports the PROJ network state and the writable directory for each
session, and the presence of the ``NOAA`` authority in ``proj.db`` is
asserted.

Import-time ordering
--------------------

The order in which these variables are set is significant. ``PROJ_NETWORK``
and ``PROJ_USER_WRITABLE_DIRECTORY`` are established at the top of
``vyperdatum/__init__.py`` before any import that triggers PROJ
initialization. If network or writable-directory configuration is performed
after PROJ's global context has been created, it has no effect, because the
context is built once with the settings present at that moment. New
environment setup should therefore not be introduced elsewhere in the module.

``VYPER_PASS1_TILE_SIZE``
-------------------------

``VYPER_PASS1_TILE_SIZE`` is an optional integer that controls the tile
dimensions used by the tiled Pass 1 path of ``transform_raster`` for very
large rasters. Its default is 4096. The tiled path and the conditions under
which it is engaged are described in :doc:`raster_transformation`.
