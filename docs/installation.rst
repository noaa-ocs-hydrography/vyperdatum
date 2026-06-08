Installation
============

Vyperdatum requires ``GDAL``, which is most reliably installed from the
conda-forge channel. A conda environment is created first, then ``GDAL`` and
Vyperdatum are installed into it.

.. code-block:: bash

   conda create -n vd python=3.11
   conda activate vd
   conda install -c conda-forge proj=9.6 gdal python-pdal
   pip install vyperdatum

Downloading the NOAA grids and proj.db
--------------------------------------

NOAA's datum grid files and the updated ``proj.db`` are not bundled with the
package and are downloaded separately. The archive is published on Zenodo:

   https://doi.org/10.5281/zenodo.18893503

Once the archive has been downloaded and extracted, a persistent environment
variable named ``VYPER_GRIDS`` is set to the directory that holds the
downloaded grids and ``proj.db``. The grids directory and ``proj.db`` are
validated at import time; if ``VYPER_GRIDS`` is unset, points at a missing
directory, or is missing required files, an informative error is raised. The
:doc:`guides/configuration` page documents the environment variables that
Vyperdatum reads and sets.

Verifying the installation
---------------------------

After ``VYPER_GRIDS`` has been set, the package import itself acts as a
validation step. A successful import confirms that the grids directory and
``proj.db`` were found and that the ``NOAA`` authority is present in the PROJ
database.

.. code-block:: python

   import vyperdatum
   print(vyperdatum.__version__)
