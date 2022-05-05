
import os, sys, configparser, glob, hashlib
from copy import deepcopy
from typing import Any
import numpy as np
from pyproj import datadir
from vyperdatum.vdatum_validation import vdatum_hashlookup, vdatum_geoidlookup
from vyperdatum.vypercrs import geoid_frame_lookup, geoid_possibilities

grid_formats = ['.tif', '.tiff', '.gtx']


class DatumData:
    """
    Gets and maintains datum information for use with Vyperdatum.

    The VDatum path location is stored in a config file which is in the user's directory.  Use configparser to sync
    self._config and the ini file.

    Optionally, user may provide a vdatum directory here on initialization to set the vdatum path the first time
    """

    def __init__(self, vdatum_directory: str = None, parent=None):
        self.parent = parent

        self.datums_root_path = ''

        self._config = {'vdatum_path': ''}  # dict of all the settings
        self.config_path_file = ''  # path to the config file that maintains the settings between runs

        self._get_stored_vyper_config()
        if vdatum_directory:  # overwrite the loaded path if you want to change it on initialization
            self.set_vdatum_directory(vdatum_directory)
        else:
            self.set_vdatum_directory(self.vdatum_path)
        self.get_vdatum_version()
        self.set_other_paths(self._config)

        # get list of vdatum versions in the provided path
        # build a dictionary of the regions, grid files, and uncertainties
        # get a list of the extended regions in the provided path
        # build a dictionary of the regions, grid files, and uncertainties
        # set the default version of VDatum based on config, or latest if not available in config

        self.regions = []
        self.grid_files = {}  # dict of file names to file paths for the gtx files
        self.polygon_files = {}  # dict of file names to file paths for the kml files
        self.uncertainties = {}  # dict of file names to uncertainties for each grid
        self.vdatum_path = ''  # path to the parent vdatum folder
        self.vdatum_version = ''
        self.extended_region = {}  # dict of region to custom region data from the custom region's config file
        self.extended_region_lookup = {}  # dict of extended region path to list of regions associated with that path



    def set_config(self, ky: str, value: Any):
        """
        Setter for the _config attribute.  Use this instead of setting _config directly, will set both the _config
        key/value and the configparser ini file.

        Parameters
        ----------
        ky
            key to set in the dict
        value
            value to set in the dict
        """

        try:
            config = configparser.ConfigParser()
            config.read(self.config_path_file)
            for k, v in self._config.items():
                config['Default'][k] = v

            self._config[ky] = value  # set the class attribute
            config['Default'][ky] = value  # set the ini matching attribute
            with open(self.config_path_file, 'w') as configfile:
                config.write(configfile)
        except:
            # get a number of exceptions here when reading and writing to the config file in multiprocessing
            try:
                if self.parent:
                    self.parent.log_warning('Unable to set {} in config file {}'.format(ky, self.config_path_file))
            except AttributeError:  # logger not initialized yet
                print('WARNING: Unable to set {} in config file {}'.format(ky, self.config_path_file))
        if ky == 'vdatum_path':
            self.vdatum_path = value

    def remove_from_config(self, ky: str):
        """
        Drop the given key from the _config attribute.  Use this instead of dealing with _config directly, will set both
        the _config key/value and the configparser ini file.

        Parameters
        ----------
        ky
            key to remove from the dict
        """

        try:
            config = configparser.ConfigParser()
            config.read(self.config_path_file)
            for k, v in self._config.items():
                config['Default'][k] = v

            if ky in self._config:
                self._config.pop(ky)
            if ky in config['Default']:
                config['Default'].pop(ky)
                with open(self.config_path_file, 'w') as configfile:
                    config.write(configfile)
        except:
            # get a number of exceptions here when reading and writing to the config file in multiprocessing
            try:
                if self.parent:
                    self.parent.log_warning('Unable to remove {} from config file {}'.format(ky, self.config_path_file))
            except AttributeError:  # logger not initialized yet
                print('WARNING: Unable to remove {} from config file {}'.format(ky, self.config_path_file))

    def _get_stored_vyper_config(self):
        """
        Runs on initialization, will read from the ini file and set the vdatum path, config attribute
        """
        try:
            vyperdatum_folder = os.path.join(os.path.expanduser('~'), 'vyperdatum')
            self.config_path_file = os.path.join(vyperdatum_folder, 'vdatum.config')
            # get the config
            if os.path.exists(self.config_path_file):
                self._config = self._read_from_config_file()
            else:
                default_vdatum_path = os.path.join(os.path.splitdrive(sys.executable)[0], '/VDatum')
                self._config = self._create_new_config_file({'vdatum_path': default_vdatum_path})
            self.vdatum_path = self._config['vdatum_path']
        except:
            # get a number of exceptions here when reading and writing to the config file in multiprocessing
            try:
                if self.parent:
                    self.parent.log_warning('Unable to get stored vdatum config file {}'.format(self.config_path_file))
            except AttributeError:  # logger not initialized yet
                print('WARNING: Unable to get stored vdatum config file {}'.format(self.config_path_file))

    def _read_from_config_file(self):
        """
        Read from the generated configparser file path, set the object vdatum settings.

        Returns
        -------
        dict
            dictionary of settings
        """

        settings = {}
        try:
            config_file = configparser.ConfigParser()
            config_file.read(self.config_path_file)
            sections = config_file.sections()
            for section in sections:
                config_file_section = config_file[section]
                for key in config_file_section:
                    settings[key] = config_file_section[key]
        except:
            # get a number of exceptions here when reading and writing to the config file in multiprocessing
            try:
                if self.parent:
                    self.parent.log_warning('Unable to read from existing config file {}'.format(self.config_path_file))
            except AttributeError:  # logger not initialized yet
                print('WARNING: Unable to read from existing config file {}'.format(self.config_path_file))
        # ensure a vdatum path attribute is in the settings to make the rest of the code work
        if 'vdatum_path' not in settings:
            settings['vdatum_path'] = ''
        return settings

    def _create_new_config_file(self, default_settings: dict) -> dict:
        """
        Create a new configparser file, return the settings and the configparser object

        Parameters
        ----------
        default_settings
            default settings we want to write to the configparser file

        Returns
        -------
        dict
            settings within the file
        """

        try:
            config_folder, config_file = os.path.split(self.config_path_file)
            if not os.path.exists(config_folder):
                os.mkdir(config_folder)
            config = configparser.ConfigParser()
            config['Default'] = default_settings
            with open(self.config_path_file, 'w') as configfile:
                config.write(configfile)
        except:
            # get a number of exceptions here when reading and writing to the config file in multiprocessing
            try:
                if self.parent:
                    self.parent.log_warning('Unable to create new config file {}'.format(self.config_path_file))
            except AttributeError:  # logger not initialized yet
                print('WARNING: Unable to create new config file {}'.format(self.config_path_file))
        return default_settings

    def set_vdatum_directory(self, vdatum_path: str):
        """
        Called when self.settings['vdatum_directory'] is updated.  We find all the grids and polygons in the vdatum
        directory and save the dicts to the attributes in this class.
        """

        self.set_config('vdatum_path', vdatum_path)
        if not os.path.exists(self.vdatum_path):
            raise ValueError(f'VDatum is not found at the provided path: {self.vdatum_path}')

        # special case for vdatum directory, we want to give pyproj the new path if it isn't there already
        orig_proj_paths = datadir.get_data_dir()
        if vdatum_path not in orig_proj_paths:
            datadir.append_data_dir(vdatum_path)

        # also want to populate grids and polygons with what we find
        self.grid_files, self.regions = get_grid_list(vdatum_path)
        self.polygon_files = get_region_polygons(vdatum_path)
        self.uncertainties = get_vdatum_uncertainties(vdatum_path)

        self.vdatum_path = self._config['vdatum_path']

    def set_external_region_directory(self, external_path: str, external_key: str = 'external_path'):
        """
        Set a new external region directory, a directory that can hold custom region files that are outside the base vdatum
        folders.  Ensure you use a '*****_path' style key such that the reading other paths method will detect it.

        Parameters
        ----------
        external_path
            path to the directory containing the custom region folders
        external_key
            key to lookup the folder group, must have a _path at the end of the key
        """

        assert external_key.endswith('_path')
        self.set_config(external_key, external_path)
        self.set_other_paths({external_key: external_path})
        try:
            if self.parent:
                self.parent.log_info \
                    (f'Added {len(self.extended_region_lookup[external_key])} new region(s) from {external_path}')
        except AttributeError:  # logger not initialized yet
            print(f'Added {len(self.extended_region_lookup[external_key])} new regions from {external_path}')

    def remove_external_region_directory(self, external_key: str):
        """
        Users add a new external region directory using set_external_region_directory.  To remove this directory from
        the datum_data class, we need to remove the key from the config file/config data, and also remove any associated
        regions.

        Parameters
        ----------
        external_key
            key to lookup the folder group, must have a _path at the end of the key
        """

        if external_key in self._config:
            self.remove_from_config(external_key)
        if external_key in self.extended_region_lookup:
            regions = self.extended_region_lookup.pop(external_key)
            num_regions = len(regions)
            for region in regions:
                self.regions.remove(region)
                self.polygon_files.pop(region)
                self.extended_region.pop(region)
                if region in self.uncertainties:
                    self.uncertainties.pop(region)
            try:
                if self.parent:
                    self.parent.log_info(f'Removed {num_regions} region(s) associated with {external_key}')
            except AttributeError:  # logger not initialized yet
                print(f'Removed {num_regions} region(s) associated with {external_key}')

    def set_other_paths(self, config: dict):
        """
        Get other paths (as *_path) from the config and add to proj path.
        """

        self.extended_region = {}
        orig_proj_paths = datadir.get_data_dir()
        for entry in config.keys():
            if entry.endswith('_path') and entry != 'vdatum_path':
                new_path = config[entry]
                if os.path.exists(new_path):
                    if new_path not in orig_proj_paths:
                        datadir.append_data_dir(new_path)
                    other_grids, other_regions = get_grid_list(new_path)
                    self.extended_region_lookup[entry] = []
                    for region in other_regions:
                        valid_region = False
                        polygon_file = os.path.join(new_path ,region ,region + '.gpkg')
                        if os.path.exists(polygon_file):
                            config_path = os.path.join(new_path ,region ,region + '.config')
                            if os.path.exists(polygon_file):
                                new_region_info = read_regional_config(config_path)
                                if 'reference_frame' in new_region_info and 'reference_geoid' in new_region_info:
                                    valid_region = True
                        if valid_region:
                            self.extended_region_lookup[entry].append(region)
                            if region in self.regions:  # ensure the region is only added once
                                self.regions.remove(region)
                            self.regions.append(region)
                            self.polygon_files[region] = polygon_file
                            self.extended_region[region] = new_region_info
                            if 'uncertainty_tss' in new_region_info:
                                self.uncertainties[region] = {'tss': new_region_info['uncertainty_tss'],
                                                              'mhhw': new_region_info['uncertainty_mhhw'],
                                                              'mhw': new_region_info['uncertainty_mhw'],
                                                              'mlw': new_region_info['uncertainty_mlw'],
                                                              'mllw': new_region_info['uncertainty_mllw'],
                                                              'dtl': new_region_info['uncertainty_dtl'],
                                                              'mtl': new_region_info['uncertainty_mtl']}

    def get_vdatum_version(self):
        """
        Get the current vdatum version that vyperdatum generates on the fly.  If this has been run before, the version
        will be encoded in a new vdatum_vyperversion.txt file that we can read instead so that we don't have to do the
        lengthy check.
        """

        if not os.path.exists(self.vdatum_path):
            raise ValueError(f'VDatum is not found at the provided path: {self.vdatum_path}')
        vyperversion_file = os.path.join(self.vdatum_path, 'vdatum_vyperversion.txt')
        if os.path.exists(vyperversion_file):
            with open(vyperversion_file, 'r') as vfile:
                vversion = vfile.read()
        else:
            try:
                if self.parent:
                    self.parent.log_info \
                        (f'Performing hash comparison to identify VDatum version, should only run once for a new VDatum directory...')
            except AttributeError:  # logger not initialized yet
                print \
                    (f'Performing hash comparison to identify VDatum version, should only run once for a new VDatum directory...')
            vversion = return_vdatum_version(self.grid_files, self.vdatum_path, save_path=vyperversion_file)
            if vversion:
                try:
                    if self.parent:
                        self.parent.log_info(f'Generated new version file: {vyperversion_file}')
                except AttributeError:  # logger not initialized yet
                    print(f'Generated new version file: {vyperversion_file}')
        self.vdatum_version = vversion

    def get_geoid_name(self, region_name: str, vdatum_version: str = None) -> str:
        """
        Return the geoid path from the vdatum version lookup matching the given version for the given region

        Parameters
        ----------
        region_name
            name of the region that we want the geoid for
        vdatum_version
            vdatum version string for the vdatum version we are interested in

        Returns
        -------
        str
            geoid name, ex: r'core\geoid12b\g2012bu0.gtx'
        """

        if not vdatum_version:
            vdatum_version = self.vdatum_version
        try:
            geoid_name = vdatum_geoidlookup[vdatum_version][region_name]
        except KeyError:
            geoid_name = self.extended_region[region_name]['reference_geoid']

        return geoid_name

    def get_geoid_frame(self, region_name: str, vdatum_version: str = None) -> str:
        """
        Return the geoid reference frame from the vdatum version lookup matching the given version for the given region

        Parameters
        ----------
        region_name
            name of the region that we want the geoid for
        vdatum_version
            vdatum version string for the vdatum version we are interested in

        Returns
        -------
        str
            reference frame used in the given region, ex: NAD83(2011)
        """

        if not vdatum_version:
            vdatum_version = self.vdatum_version
        try:
            geoid_frame = geoid_frame_lookup[vdatum_geoidlookup[vdatum_version][region_name]]
        except KeyError:
            geoid_frame = self.extended_region[region_name]['reference_frame']

        return geoid_frame


def get_grid_list(vdatum_directory: str):
    """
    Search the vdatum directory to find all gtx files

    Parameters
    ----------
    vdatum_directory
        absolute folder path to the vdatum directory

    Returns
    -------
    dict
        dictionary of {grid name: grid path, ...}
    list
        list of vdatum regions
    """

    grid_list = []
    for gfmt in grid_formats:
        search_path = os.path.join(vdatum_directory, '*/*{}'.format(gfmt))
        grid_list += glob.glob(search_path)
    if len(grid_list) == 0:
        errmsg = f'No grid files found in the provided VDatum directory: {vdatum_directory}'
        print(errmsg)
    grids = {}
    regions = []
    for grd in grid_list:
        grd_path, grd_file = os.path.split(grd)
        grd_path, grd_folder = os.path.split(grd_path)
        gtx_name = '/'.join([grd_folder, grd_file])
        gtx_subpath = os.path.join(grd_folder, grd_file)
        grids[gtx_name] = gtx_subpath
        regions.append(grd_folder)
    regions = list(set(regions))
    return grids, regions


def get_region_polygons(datums_directory: str, extension: str = 'kml') -> dict:
    """"
    Search the datums directory to find all geometry files.  All datums are assumed to reside in a subfolder.

    Parameters
    ----------
    datums_directory : str
        absolute folder path to the vdatum directory

    extension : str
        the geometry file extension to search for

    Returns
    -------
    dict
        dictionary of {kml name: kml path, ...}
    """

    search_path = os.path.join(datums_directory, f'*/*.{extension}')
    geom_list = glob.glob(search_path)
    if len(geom_list) == 0:
        errmsg = f'No {extension} files found in the provided directory: {datums_directory}'
        print(errmsg)
    geom = {}
    for filename in geom_list:
        geom_path, geom_file = os.path.split(filename)
        root_dir, geom_name = os.path.split(geom_path)
        geom[geom_name] = filename
    return geom


def get_vdatum_uncertainties(vdatum_directory: str):
    """"
    Parse the sigma file to build a dictionary of gridname: uncertainty for each layer.

    Parameters
    ----------
    vdatum_directory
        absolute folder path to the vdatum directory

    Returns
    -------
    dict
        dictionary of {kml name: kml path, ...}
    """
    acc_file = os.path.join(vdatum_directory, 'vdatum_sigma.inf')

    # use the polygon search to get a dict of all grids quickly
    grid_dict = get_region_polygons(vdatum_directory)
    for k in grid_dict.keys():
        grid_dict[k] = {'tss': 0, 'mhhw': 0, 'mhw': 0, 'mlw': 0, 'mllw': 0, 'dtl': 0, 'mtl': 0}
    # add in the geoids we care about
    grid_entries = list(grid_dict.keys())
    if os.path.exists(acc_file):
        with open(acc_file, 'r') as afil:
            for line in afil.readlines():
                data = line.split('=')
                if len(data) == 2:  # a valid line, ex: akglacier.navd88.lmsl=8.0
                    data_entry, val = data
                    sub_data = data_entry.split('.')
                    if len(sub_data) == 3:
                        region, src, target = sub_data
                        if region == 'conus':
                            if src == 'navd88' and target == 'nad83':
                                grid_dict['geoid12b'] = float(val.lstrip().rstrip()) * 0.01
                            elif src in geoid_possibilities:
                                grid_dict[f'{src}'] = float(val.lstrip().rstrip()) * 0.01
                        else:
                            match = np.where(np.array([entry.lower().find(region) for entry in grid_entries]) == 0)
                            if match[0].size:
                                if len(match[0]) > 1:
                                    raise ValueError \
                                        (f'Found multiple matches in vdatum_sigma file for entry {data_entry}')
                                elif match:
                                    grid_key = grid_entries[match[0][0]]
                                    val = val.lstrip().rstrip()
                                    if val == 'n/a':
                                        val = 0
                                    if src == 'navd88' and target == 'lmsl':
                                        grid_dict[grid_key]['tss'] = float(val) * 0.01
                                    elif src == 'lmsl':
                                        grid_dict[grid_key][target] = float(val) * 0.01
                                else:
                                    print(f'No match for vdatum_sigma entry {data_entry}!')
    else:
        print(f'No uncertainty file found at {acc_file}')
    return grid_dict


def read_regional_config(config_path: str) -> dict:
    """
    read the config for the extended datum region and return the information.  All sections in the config
    will be removed so no duplicative keys should exist between sections.

    Parameters
    ----------
    config_path : str
        A config file contining the information for the region.

    Returns
    -------
    dict
        key / value pairs for the region inforamtion.

    """
    settings = {}
    config_file = configparser.ConfigParser()
    config_file.read(config_path)
    sections = config_file.sections()
    for section in sections:
        config_file_section = config_file[section]
        for key in config_file_section:
            settings[key] = config_file_section[key]
    return settings


def hash_a_file(filepath: str):
    """
    Generate a new md5 hash for the provided file

    Parameters
    ----------
    filepath
        full absolute file path to the file to hash

    Returns
    -------
    str
        new md5 hex digest for the file
    """

    md5 = hashlib.md5()
    with open(filepath, 'rb') as f:
        data = f.read()
        md5.update(data)
    return md5.hexdigest()


def hash_vdatum_grids(grid_files: dict, vdatum_path: str):
    """
    Generate a new md5 hash for each grid file in the provided dictionary

    Parameters
    ----------
    grid_files
        dictionary of {file name: file path} for the grids in this vdatum directory
    vdatum_path
        path to the vdatum folder

    Returns
    -------
    dict
        dictionary of {file path: file hash}
    """

    hashdict = {}
    for grd in grid_files.keys():
        hashdict[grd] = hash_a_file(os.path.join(vdatum_path, grd))
    return hashdict


def return_vdatum_version(grid_files: dict, vdatum_path: str, save_path: str = None):
    """
    Return the vdatum version either by brute force using our vdatum hash lookup check, or by reading the vdatum
    version file that vyperdatum generates, if this check has been run once before.

    Parameters
    ----------
    grid_files
        dictionary of {file name: file path} for the grids in this vdatum directory
    vdatum_path
        path to the vdatum folder
    save_path
        if provided, saves the vdatum version to a new text file in the vdatum directory

    Returns
    -------
    str
        vdatum version identifier
    """

    myversion = ''
    hashdict = hash_vdatum_grids(grid_files, vdatum_path)
    acc_file = os.path.join(vdatum_path, 'vdatum_sigma.inf')
    if os.path.exists(acc_file):
        acc_hash = hash_a_file(acc_file)
        cpy_vdatum_hashlookup = deepcopy(vdatum_hashlookup)
        for vdversion, vdhashes in cpy_vdatum_hashlookup.items():
            sigmahash = vdhashes.pop('vdatum_sigma.inf')
            if hashdict == vdhashes and acc_hash == sigmahash:
                myversion = vdversion
                print('Found {}'.format(myversion))
                break
        if myversion and save_path:
            with open(save_path, 'w') as ofile:
                ofile.write(myversion)
        if not myversion:
            raise EnvironmentError(f'Unable to find version for {vdatum_path} in the currently accepted versions: {list(vdatum_hashlookup.keys())}')
    else:
        print(f'Unable to find sigma file {acc_file}, no vdatum version found')
    return myversion