
nad83_itrf2008_pipeline = '+proj=pipeline +step +proj=axisswap +order=2,1 ' \
                          '+step +proj=unitconvert +xy_in=deg +xy_out=rad ' \
                          '+step +proj=cart +ellps=GRS80 ' \
                          '+step +inv +proj=helmert +x=0.99343 +y=-1.90331 +z=-0.52655 +rx=0.02591467 +ry=0.00942644999999999 +rz=0.01159935 +s=0.00171504 +dx=0.00079 +dy=-0.0006 +dz=-0.00134 +drx=6.667e-05 +dry=-0.00075744 +drz=-5.133e-05 +ds=-0.00010201 +t_epoch=1997 +convention=coordinate_frame ' \
                          '+step +inv +proj=cart +ellps=GRS80  ' \
                          '+step +proj=unitconvert +xy_in=rad +xy_out=deg  ' \
                          '+step +proj=axisswap +order=2,1'

nad83_itrf2014_pipeline = '+proj=pipeline +step +proj=axisswap +order=2,1 ' \
                          '+step +proj=unitconvert +xy_in=deg +xy_out=rad ' \
                          '+step +proj=cart +ellps=GRS80 ' \
                          '+step +inv +proj=helmert +x=1.0053 +y=-1.9092 +z=-0.5416 +rx=0.0267814 +ry=-0.0004203 +rz=0.0109321 +s=0.00037 +dx=0.0008 +dy=-0.0006 +dz=-0.0014 +drx=6.67e-05 +dry=-0.0007574 +drz=-5.13e-05 +ds=-7e-05 +t_epoch=2010 +convention=coordinate_frame ' \
                          '+step +inv +proj=cart +ellps=GRS80 ' \
                          '+step +proj=unitconvert +xy_in=rad +xy_out=deg ' \
                          '+step +proj=axisswap +order=2,1'

reference_frames = ['nad83', 'itrf08']

datum_definition = {
    'ellipse'  : [],
    'geoid'   : ['+proj=vgridshift grids=GEOID'],
    'navd88'  : ['+proj=vgridshift grids=GEOID'],
    'tss'      : ['+proj=vgridshift grids=GEOID',
                  '+inv +proj=vgridshift grids=REGION\\tss.gtx'],
    'mllw'     : ['+proj=vgridshift grids=GEOID',
                  '+inv +proj=vgridshift grids=REGION\\tss.gtx',
                  '+proj=vgridshift grids=REGION\\mllw.gtx'],
    'noaa chart datum': ['+proj=vgridshift grids=GEOID',
                         '+inv +proj=vgridshift grids=REGION\\tss.gtx',
                         '+proj=vgridshift grids=REGION\\mllw.gtx'],
    'mhw'     : ['+proj=vgridshift grids=GEOID',
                 '+inv +proj=vgridshift grids=REGION\\tss.gtx',
                 '+proj=vgridshift grids=REGION\\mhw.gtx'],
    'noaa chart height': ['+proj=vgridshift grids=GEOID',
                          '+inv +proj=vgridshift grids=REGION\\tss.gtx',
                          '+proj=vgridshift grids=REGION\\mhw.gtx'],
    'usace hudson river datum' : ['+proj=vgridshift grids=GEOID',
                          '+proj=vgridshift grids=REGION\\HudsonRiverDatum.tif'],
    'mtl'     : ['+proj=vgridshift grids=GEOID',
                 '+inv +proj=vgridshift grids=REGION\\tss.gtx',
                 '+proj=vgridshift grids=REGION\\mtl.gtx'],
    'dtl'     : ['+proj=vgridshift grids=GEOID',
                 '+inv +proj=vgridshift grids=REGION\\tss.gtx',
                 '+proj=vgridshift grids=REGION\\dtl.gtx']
    }


def get_regional_pipeline(from_datum: str, to_datum: str, region_name: str, geoid_name: str):
    """
    Return a string describing the pipeline to use to convert between the provided datums.

    Parameters
    ----------
    from_datum : str
        A string corresponding to one of the stored datums.
    to_datum : str
        A string corresponding to one of the stored datums.
    region_name: str
        A region name corrisponding to a VDatum subfolder name.
    geoid_name
        name of the geoid used in the pipeline

    Raises
    ------
    ValueError
        If an input string is not found in the datum definition database a
        value error is returned.

    Returns
    -------
    regional_pipeline : str
        A string describing the pipeline to use to convert between the
        provided datums.

    """
    from_datum = from_datum.lower()
    to_datum = to_datum.lower()
    if from_datum == to_datum:
        return None

    _validate_datum_names(from_datum, to_datum)
    input_datum_def = datum_definition[from_datum].copy()
    output_datum_def = datum_definition[to_datum].copy()
    input_datum_def, output_datum_def = compare_datums(input_datum_def, output_datum_def)
    reversed_input_def = inverse_datum_def(input_datum_def)
    transformation_def = ['+proj=pipeline', *reversed_input_def, *output_datum_def]
    pipeline = ' +step '.join(transformation_def)
    regional_pipeline = pipeline.replace('REGION', region_name)
    regional_pipeline = regional_pipeline.replace('GEOID', geoid_name)

    return regional_pipeline


def _validate_datum_names(from_datum: str, to_datum: str):
    """
    Raise an error if the provided datum names are not found in the datum
    definition dictionary.

    Parameters
    ----------
    from_datum
        datum string for the source datum, must be in datum definitions
    to_datum : str
        datum string for the destination datum, must be in datum definitions
    """

    if from_datum not in datum_definition:
        raise ValueError(f'Input datum {from_datum} not found in datum definitions: {list(datum_definition.keys())}.')
    if to_datum not in datum_definition:
        raise ValueError(f'Output datum {to_datum} not found in datum definitions: {list(datum_definition.keys())}')


def compare_datums(in_datum_def: list, out_datum_def: list):
    """
    Compare two lists describing the datums.  Remove common parts of the definition starting from the first entry.
    Stop when they do not agree.

    Parameters
    ----------
    in_datum_def
        The datum definition as described in the datum defition database.
    out_datum_def
        The datum definition as described in the datum defition database.

    Returns
    -------
    list
        A reduced list of the input datum and output datum layers.
    """

    num_to_compare = min(len(in_datum_def), len(out_datum_def))
    remove_these = []
    for n in range(num_to_compare):
        if in_datum_def[n] == out_datum_def[n]:
            remove_these.append(in_datum_def[n])
    for rmve in remove_these:
        in_datum_def.remove(rmve)
        out_datum_def.remove(rmve)
    return [in_datum_def, out_datum_def]


def inverse_datum_def(datum_def: list):
    """
    Reverse the order of the datum definition list and prepend 'inv' to each
    layer.

    Parameters
    ----------
    datum_def
        A list describing the layers of a datum definition.

    Returns
    -------
    list
        The provided list reversed with 'inv' prepended to each layer.

    """
    inverse = []
    for layer in datum_def[::-1]:
        if '+inv' in layer:
            nlayer = layer.replace('+inv ', '')
            inverse.append(nlayer)
        else:
            inverse.append(' '.join(['+inv', layer]))
    return inverse
