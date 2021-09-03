# -*- coding: utf-8 -*-
"""
gtx_to_gtif.py

Created on Thu Sep  2 07:52:32 2021

@author: grice

Convert the gtx files in the vdatum subdirectories with a 0 to 2pi longitude
to corrisponding geotiffs with -pi to pi georeferencing.  This conversion uses
gdalwarp in subprocess to conduct the conversion.  This process was created to
help with debugging and visualization of the grids in qgis.
"""
import os
import subprocess

from vyperdatum.core import VdatumData


# fetch the VDatum directory already initialized
vdatum = VdatumData()

current_path = os.getcwd()
os.chdir(vdatum.vdatum_path)
failures = 0
msg = ''
total = len(vdatum.grid_files)
for count, gtx_filename in enumerate(vdatum.grid_files):
    base, ext = os.path.splitext(gtx_filename)
    gtif_filename = '.'.join([base, 'tiff'])
    cmd = f'gdalwarp -t_srs WGS84 {gtx_filename} {gtif_filename}  -wo SOURCE_EXTRA=1000 --config CENTER_LONG 0'
    response = subprocess.run(cmd)
    num_char = len(msg)
    if response.returncode != 0:
        failures += 1
        print(num_char * '\b' + f'{count}/{total}: failed to convert {gtx_filename}')
        msg = ''
    else:
        msg = f'{count}/{total} completed'
        print(num_char * '\b' + msg, end = '')
if failures > 0:
    print(f'\n{failures} total failed conversions.')
os.chdir(current_path)