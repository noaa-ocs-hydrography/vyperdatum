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
root_path, vdatum_folder = os.path.split(vdatum.vdatum_path)
gtif_folder = '_'.join([vdatum_folder, 'geotiffs'])
os.chdir(root_path)
os.mkdir(gtif_folder)
failures = 0
msg = ''
total = len(vdatum.grid_files)
for count, gtx_filename in enumerate(vdatum.grid_files):
    base, ext = os.path.splitext(gtx_filename)
    gtif_filename = '.'.join([base, 'tiff'])
    gtif_path = os.path.join(gtif_folder, gtif_filename)
    gtx_path = os.path.join(vdatum_folder, gtx_filename)
    folder, file = os.path.split(gtif_path)
    if not os.path.exists(folder):
        os.mkdir(folder)
    cmd = f'gdalwarp -t_srs WGS84 {gtx_path} {gtif_path}  -wo SOURCE_EXTRA=1000 --config CENTER_LONG 0'
    response = subprocess.run(cmd)
    num_char = len(msg)
    if response.returncode != 0:
        failures += 1
        print(num_char * '\b' + f'{count}/{total}: failed to convert {gtx_path}')
        msg = ''
    else:
        msg = f'{count}/{total} completed'
        print(num_char * '\b' + msg, end = '')
if failures > 0:
    print(f'\n{failures} total failed conversions.')
os.chdir(current_path)