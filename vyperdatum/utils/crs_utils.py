import logging
import subprocess
from colorama import Fore, Style
from typing import Optional, Tuple
import pyproj as pp
from pyproj.transformer import TransformerGroup


logger = logging.getLogger("root_logger")


def crs_components(crs: pp.CRS, raise_no_auth: bool = True) -> Tuple[str, Optional[str]]:
    """
    Return CRS horizontal and vertical components string representation
    in form of code:authority. If the input CRS is horizontal, the vertical
    component will be None.

    Raises
    -------
    ValueError:
        If either code or authority of the crs (or its sub_crs) can not be determined.

    Returns
    --------
    Tuple[str, Optional[str]]:
        Horizontal and vertical components of crs in form of code:authority
    """
    if isinstance(crs, str):
        crs = pp.CRS(crs)
    h, v = None, None
    if crs.is_compound:
        try:
            sub_h = pp.CRS(crs.sub_crs_list[0])
            # if sub_h.is_bound:
            #     sub_h = sub_h.source_crs
            h = ":".join(sub_h.to_authority())
        except:
            if sub_h.is_bound:
                h = "BOUNDCRS"
            else:
                h = "UnknownAuthorityCode"
        try:
            sub_v = pp.CRS(crs.sub_crs_list[1])
            # if sub_v.is_bound:
            #     sub_v = sub_v.source_crs
            v = ":".join(sub_v.to_authority())
        except:
            if sub_v.is_bound:
                v = "BOUNDCRS"
            else:
                v = "UnknownAuthorityCode"
    else:
        # if crs.is_bound:
        #     crs = crs.source_crs
        ac = crs.to_authority(min_confidence=100)
        if not ac and raise_no_auth:
            raise ValueError(f"Unable to produce authority name and code for this crs:\n{crs}")
        h = ":".join(crs.to_authority())
    return h, v


def auth_code(crs: pp.CRS, raise_no_auth: bool = True) -> Optional[str]:
    """
    Return CRS string representation in form of code:authority

    Raises
    -------
    ValueError:
        If either code or authority of the crs (or its sub_crs) can not be determined.

    Returns
    --------
    str:
        crs string in form of code:authority
    """
    if isinstance(crs, str):
        crs = pp.CRS(crs)
    ## might fail for pyproj.CRS("EPSG:4269").geodetic_crs.to_3d().to_authority(min_confidence=100)
    ac = crs.to_authority(min_confidence=100)
    if not ac and crs.is_compound:
        try:
            h = ":".join(pp.CRS(crs.sub_crs_list[0]).to_authority())
        except:
            h = "UnknownAuthorityCode"
        try:
            v = ":".join(pp.CRS(crs.sub_crs_list[1]).to_authority())
        except:
            v = "UnknownAuthorityCode"
        return f"{h}+{v}"
    if not ac and raise_no_auth:
        raise ValueError(f"Unable to produce authority name and code for this crs:\n{crs}")
    return ":".join(ac)


def vertical_shift(crs_from: pp.CRS, crs_to: pp.CRS) -> bool:
    """
    Return True if transformation from `crs_from` to `crs_to` results
    in vertical shifts.

    Parameters
    ----------
    crs_from: pyproj.crs.CRS
        Projection of input data.
    crs_to: pyproj.crs.CRS
        Projection of output data.

    Raises
    -------
    TypeError:
        If either one of `crs_from` or `crs_to` is not of type pyproj.CRS.

    Returns
    -------
    bool
    """
    if not isinstance(crs_from, pp.CRS) or not isinstance(crs_to, pp.CRS):
        raise TypeError("Both `crs_from` and `crs_to` must be of type pyproj.CRS.")
    if crs_from.equals(crs_to):
        return False
    vertical = False
    # if (not crs_from.is_projected and not crs_to.is_projected
    #     and len(crs_from.axis_info) + len(crs_to.axis_info) == 5):  # 2D+3D
    #     vertical = True
    # if len(crs_from.axis_info) + len(crs_to.axis_info) == 6:  # 3D + 3D
    #     s_v = crs_from.sub_crs_list[1] if crs_from.is_compound else None
    #     t_v = crs_to.sub_crs_list[1] if crs_to.is_compound else None
    #     if s_v is None and t_v is None and crs_from.datum.ellipsoid != crs_to.datum.ellipsoid:
    #         vertical = True
    #     elif s_v != t_v:
    #         vertical = True

    if crs_from.is_compound or crs_to.is_compound:
        s_v = crs_from.sub_crs_list[1] if crs_from.is_compound else None
        t_v = crs_to.sub_crs_list[1] if crs_to.is_compound else None
        if s_v != t_v:
            vertical = True
    elif (crs_from.datum.ellipsoid and  # WGS84-based CRS datum's ellipsoid is None
          crs_to.datum.ellipsoid and
          crs_from.datum.ellipsoid != crs_to.datum.ellipsoid):
        vertical = True
    return vertical


def crs_epoch(crs: pp.CRS) -> Optional[str]:
    """
    Return the input CRS reference epoch, if the input CRS is Dynamic.
    otherwise return `None`.

    Parameters
    ----------
    crs: pyproj.crs.CRS
        pyproj CRS instance.

    Raises
    -------
    TypeError:
        If `crs` is not of type pyproj.CRS.
    """
    if not isinstance(crs, pp.CRS):
        raise TypeError("`crs` must be of type pyproj.CRS.")
    dynamic = crs.datum.to_json_dict()["type"] == "DynamicGeodeticReferenceFrame"
    epoch = crs.datum.to_json_dict().get("frame_reference_epoch")
    return str(epoch) if dynamic and epoch else None


def add_epoch_option(s_crs: pp.CRS, t_crs: pp.CRS, warp_kwargs: dict):
    """
    Add epoch info to the GDAL warp options if either source or target CRSs are dynamic.

    Parameters
    ----------
    s_crs: pyproj.crs.CRS
        Source CRS object used in gdal Warp.
    t_crs: pyproj.crs.CRS
        Target CRS object used in gdal Warp.
    warp_kwargs: dict
        Optional GDAL warp options.

    Raises
    -------
    TypeError:
        If either one of `crs_from` or `crs_to` is not of type pyproj.CRS.

    Returns
    -------
    dict
        GDAL warp options.
    """
    if not isinstance(s_crs, pp.CRS) or not isinstance(t_crs, pp.CRS):
        raise TypeError("Both `s_crs` and `t_crs` must be of type pyproj.CRS.")
    s_epoch = crs_epoch(s_crs)
    t_epoch = crs_epoch(t_crs)
    options = {"options": []}
    if s_epoch:
        options["options"].append(f"s_coord_epoch={s_epoch}")
    if t_epoch:
        options["options"].append(f"t_coord_epoch={t_epoch}")
    if len(options["options"]) > 0:
        warp_kwargs |= {"options": options["options"]}
    return warp_kwargs


def validate_transform_steps(steps: Optional[list[str]]) -> bool:
    """
    Check if all transformation steps can be successfully instantiated by PROJ.

    Parameters
    ---------
    steps: Optional[list[str]]
        List of strings in form of `authority:code` representing the CRSs involved
        in a transformation pipeline.

    Raises
    -------
    NotImplementedError:
        When no transformer is identified.

    Returns
    --------
    bool:
        `False` if either one of the transformation steps fail, otherwise return `True`.
    """
    approve = True
    if not steps or len(steps) < 2:
        logger.error(f"{Fore.RED}Invalid transformation steps: {steps}")
        print(Style.RESET_ALL)
        return False
    for i in range(len(steps)-1):
        try:
            t1 = pp.Transformer.from_crs(crs_from=steps[i],
                                         crs_to=steps[i+1],
                                         allow_ballpark=False,
                                         only_best=True
                                         )
            tg = TransformerGroup(crs_from=steps[i],
                                  crs_to=steps[i+1],
                                  allow_ballpark=False,
                                  )
            # pyproj doesn't return proj string when there are more than 1 transformers
            if len(tg.transformers) < 2:
                if len(tg.transformers) == 0:
                    err_msg = (f"{Fore.RED}No transformers identified for the following "
                               f"transformation:\n\tcrs_from: {steps[i]}\n\tcrs_to: {steps[i+1]}")
                    logger.error(err_msg)
                    print(Style.RESET_ALL)
                    raise NotImplementedError(err_msg)
                ps = t1.to_proj4() or str(t1)
                error_hint = ""
                if not ps:
                    error_hint = "Null Proj string"
                elif "proj=noop" in ps:
                    error_hint = "proj=noop"
                elif "Error" in ps:
                    error_hint = "Error in Proj string"
                if error_hint:
                    logger.error(f"{Fore.RED}Invalid transformation step ({error_hint}): "
                                 f"{steps[i]} --> {steps[i+1]}")
                    print(Style.RESET_ALL)
                    approve = False
        except Exception as e:
            logger.error(f"{Fore.RED}Error in validation of transformation step: "
                         f"{steps[i]} --> {steps[i+1]}\n Error Msg: {e}",
                         stack_info=False, exc_info=False
                         )
            print(Style.RESET_ALL)
            approve = False
    return approve


def commandline(command: str,
                args: Optional[list[str]] = None) -> tuple[Optional[dict], Optional[str]]:
    """
    Spawn a new process to run a commandline utility and capture its output.

    Parameters
    -----------
    command: str
        The name of command (utility) to run. Example: `projinfo`
    args: Optional[list[str]]
        Optional arguments.

    Returns
    --------
    stdout: Optional[dict], std_err: Optional[str]
        standard output and error.
    """
    try:
        sout, serr = dict({}), None
        resp = subprocess.run([command, *args],
                              stderr=subprocess.PIPE,
                              stdout=subprocess.PIPE
                              )
        sout = resp.stdout.decode() if resp.stdout else None
        serr = resp.stderr.decode() if resp.stderr else None
    except Exception as e:
        logger.exception(str(e))
        sout, serr = dict({}), None
    return sout, serr


def validate_transform_steps_dict(steps: Optional[list[dict]]) -> bool:
    """
    Check if all transformation steps can be successfully instantiated by PROJ.

    Parameters
    ---------
    steps: Optional[list[dict]]
        List of dict objects containing crs_from/to in form of `authority:code`
        representing the CRSs involved in a transformation pipeline.

    Raises
    -------
    NotImplementedError:
        When no transformer is identified.

    Returns
    --------
    bool:
        `False` if either one of the transformation steps fail, otherwise return `True`.
    """
    approve = True
    if not steps or len(steps) < 1:
        logger.error(f"{Fore.RED}Invalid transformation steps: {steps}")
        print(Style.RESET_ALL)
        return False
    for i in range(len(steps)):
        try:
            t1 = pp.Transformer.from_crs(crs_from=steps[i]["crs_from"],
                                         crs_to=steps[i]["crs_to"],
                                         allow_ballpark=False,
                                         only_best=True
                                         )
            tg = TransformerGroup(crs_from=steps[i]["crs_from"],
                                  crs_to=steps[i]["crs_to"],
                                  allow_ballpark=False,
                                  )
            # pyproj doesn't return proj string when there are more than 1 transformers
            if len(tg.transformers) < 2:               
                if len(tg.transformers) == 0:
                    err_msg = (f"{Fore.RED}No transformers identified for the following "
                               f"transformation:\n\tcrs_from: {steps[i]['crs_from']}\n\tcrs_to: {steps[i]['crs_to']}")
                    logger.error(err_msg)
                    print(Style.RESET_ALL)
                    raise NotImplementedError(err_msg)
                ps = t1.to_proj4() or str(t1)
                error_hint = ""
                if not ps:
                    error_hint = "Null Proj string"
                elif "proj=noop" in ps:
                    error_hint = "proj=noop"
                elif "Error" in ps:
                    error_hint = "Error in Proj string"
                if error_hint:
                    logger.error(f"{Fore.RED}Invalid transformation step ({error_hint}): "
                                 f"{steps[i]['crs_from']} --> {steps[i]['crs_to']}")
                    print(Style.RESET_ALL)
                    approve = False
        except Exception as e:
            logger.error(f"{Fore.RED}Error in validation of transformation step: "
                         f"{steps[i]['crs_from']} --> {steps[i]['crs_to']}\n Error Msg: {e}",
                         stack_info=False, exc_info=False
                         )
            print(Style.RESET_ALL)
            approve = False
    return approve

def multiple_geodetic_crs(steps: Optional[list[dict]]) -> bool:
    """
    Check if there are more than one geodetic crs in the pipeline.

    Parameters
    ---------
    steps: Optional[list[dict]]
        List of dict objects containing crs_from/to in form of `authority:code`
        representing the CRSs involved in a transformation pipeline.


    Returns
    --------
    bool:
        `False` if all horizontal CRSs in the pipeline share the same geodetic CRS, otherwise return `True`.
    """
    geodetics = []
    for step in steps:
        h = step["crs_from"].split("+")[0]
        geodetics.append(":".join(pp.CRS(pp.CRS(h).geodetic_crs.to_2d()).to_authority()))
        h = step["crs_to"].split("+")[0]
        geodetics.append(":".join(pp.CRS(pp.CRS(h).geodetic_crs.to_2d()).to_authority()))
    geodetics = ["EPSG:6318" if g == "EPSG:4269" else g for g in geodetics]
    return len(set(geodetics)) != 1

def multiple_projections(steps: Optional[list[dict]]) -> bool:
    """
    Check if there are more than one projection types in the pipeline.

    Parameters
    ---------
    steps: Optional[list[dict]]
        List of dict objects containing crs_from/to in form of `authority:code`
        representing the CRSs involved in a transformation pipeline.


    Returns
    --------
    bool:
        `False` if all projected CRSs use the same projection, otherwise return `True`.
    """
    def _projection_type(c: pp.CRS) -> str:
        lower_name = c.name.lower()
        spcs_keywords = ["state plane", "spcs", "fips", "stateplane"]
        if "utm" in lower_name:
            return "utm"
        elif any(s in lower_name for s in spcs_keywords):    
            return "spcs"
        else:
            return "others"
    projs = []
    for step in steps:
        c = pp.CRS(step["crs_from"].split("+")[0])
        if c.is_projected:
            projs.append(_projection_type(c))
        c = pp.CRS(step["crs_to"].split("+")[0])
        if c.is_projected:
            projs.append(_projection_type(c))
    return len(set(projs)) > 1

def pipeline_string(crs_from: str, crs_to, input_metadata=None) -> Optional[str]:
    """
    Extract PROJ pipeline string from the output of projinfo utility.

    Parameters
    -----------
    crs_from: str
        Source CRS in auth:code format.
    crs_to: str
        Target CRS in auth:code format.
    input_metadata: dict
        Input raster metadata object.

    Returns
    --------
    Optional[str]
    """
    args = ["-s", crs_from, "-t", crs_to,
            "--spatial-test", "intersects",
            "--hide-ballpark"]
    if input_metadata:
        bbox = [str(v) for v in input_metadata["geo_extent"]]
        args += ["--bbox", ",".join(bbox)]
    out, err = commandline(command="projinfo", args=args)
    if not out:
        raise ValueError(f"Potential error in getting projinfo output: {err}")

    start = out.find("+proj=pipeline")
    if start == -1:
        logger.error("`PROJ string:` not found in the projinfo output")
        return None

    splits = out[start:].splitlines(keepends=False)
    pipe = ""
    for split in splits:
        if len(split.strip()) == 0:
            break
        pipe += split
    return pipe


def vertical_axis_direction(crs_auth_code) -> str:
    crs = pp.CRS(crs_auth_code)    
    if not crs.is_vertical and not crs.is_compound:
        return "Not a vertical or compound CRS."    
    crs_dict = crs.to_json_dict()    
    if crs.is_compound:
        v_crs_dict = crs_dict['components'][1]
    else:
        v_crs_dict = crs_dict

    try:
        axis = v_crs_dict['coordinate_system']['axis'][0]
        direction = axis['direction'].lower()
        
        if direction in ["up", "down"]:
            return direction
        else:
            axis_name = axis.get('name', 'unknown')
            return f"Unknown direction: {direction} for {axis_name} axis in {crs_auth_code}"
            
    except (KeyError, IndexError):
        return f"Could not parse axis information for {crs_auth_code}"



def flip_vertical_vaxis(auth_code) -> str:
    """
    Finds the flipped VCRS by explicitly swapping 'height' and 'depth' 
    in the CRS name and searching the database for that exact name.
    """
    original_crs = pp.CRS.from_user_input(auth_code)
    auth_name = auth_code.split(':')[0]
    try:
        orig_name = original_crs.name
    except AttributeError:
        orig_name = original_crs.to_json_dict().get('name', '')
    lower_name = orig_name.lower()
    if "height" in lower_name:
        target_name = orig_name.replace("height", "depth").replace("Height", "Depth")
    elif "depth" in lower_name:
        target_name = orig_name.replace("depth", "height").replace("Depth", "Height")
    else:
        raise ValueError(f"CRS name '{orig_name}' does not contain 'height' or 'depth'.")
    codes = pp.get_codes(auth_name, "VERTICAL_CRS", allow_deprecated=True)
    for code in codes:
        full_code = f"{auth_name}:{code}"
        if full_code == auth_code:
            continue
        candidate_crs = pp.CRS.from_user_input(full_code)
        try:
            cand_name = candidate_crs.name
        except AttributeError:
            cand_name = candidate_crs.to_json_dict().get('name', '')
        if cand_name == target_name:
            return full_code
    raise ValueError(f"Could not find a CRS named '{target_name}' in authority {auth_name}.")


def get_meter_vcrs(auth_code):
    if auth_code is None:
        return None
        
    crs = pp.CRS.from_user_input(auth_code)
    auth_name = auth_code.split(':')[0].upper()
    
    crs_dict = crs.to_json_dict()
    axis_info = crs_dict['coordinate_system']['axis'][0]
    
    if axis_info.get('unit') == "metre":
        return auth_code

    target_datum = crs_dict.get('datum', {}).get('name')
    target_dir = axis_info.get('direction').lower()
    target_bbox = crs_dict.get('bbox')
    orig_name = crs_dict.get('name', '')

    # Handle NOAA-specific versioning (e.g., "nwldatum_4.7.0")
    version_clue = None
    nwld_clue = "National_Water_Level_Datum/nwldatum_"
    if auth_name == "NOAA" and nwld_clue in orig_name:
        try:
            version_clue = orig_name.split(nwld_clue)[1].split("_")[0]
        except IndexError:
            pass

    codes = pp.get_codes(auth_name, "VERTICAL_CRS", allow_deprecated=True)
    best_match = None
    
    for code in codes:
        full_code = f"{auth_name}:{code}"
        if full_code == auth_code:
            continue
            
        candidate_crs = pp.CRS.from_user_input(full_code)
        cand_dict = candidate_crs.to_json_dict()
        cand_axis = cand_dict['coordinate_system']['axis'][0]
        
        if cand_axis.get('unit') != "metre":
            continue
        if cand_axis.get('direction').lower() != target_dir:
            continue
        if cand_dict.get('datum', {}).get('name') != target_datum:
            continue

        cand_name = cand_dict.get('name', '')        
        if version_clue and version_clue not in cand_name:
            continue

        if cand_dict.get('bbox') == target_bbox:
            return full_code
            
        best_match = full_code

    if best_match:
        return best_match
        
    raise ValueError(f"No meter-based VCRS found for {auth_code} in {auth_name}.")
