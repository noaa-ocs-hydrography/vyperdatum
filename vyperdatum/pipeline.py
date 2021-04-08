# All datum definitions are defined relative to the same 'pivot' ellipsoid.

datum_definition = {
    'nad83'    : [],
    'geoid12b' : ['proj=vgridshift grids=core\\geoid12b\\g2012bu0.gtx'],
    'xgeoid18b': ['proj=vgridshift grids=core\\xgeoid18b\\AK_18B.gtx'],
    'navd88'   : ['proj=vgridshift grids=core\\geoid12b\\g2012bu0.gtx'],
    'tss'      : ['proj=vgridshift grids=core\\geoid12b\\g2012bu0.gtx',
                  '+inv proj=vgridshift grids=REGION\\tss.gtx'],
    'mllw'     : ['proj=vgridshift grids=core\\geoid12b\\g2012bu0.gtx',
                  '+inv proj=vgridshift grids=REGION\\tss.gtx',
                  'proj=vgridshift grids=REGION\\mllw.gtx'],
    'noaa chart datum': ['proj=vgridshift grids=core\\geoid12b\\g2012bu0.gtx',
                         '+inv proj=vgridshift grids=REGION\\tss.gtx',
                         'proj=vgridshift grids=REGION\\mllw.gtx'],
    'mhw'     : ['proj=vgridshift grids=core\\geoid12b\\g2012bu0.gtx',
                 '+inv proj=vgridshift grids=REGION\\tss.gtx',
                 'proj=vgridshift grids=REGION\\mhw.gtx'],
    'noaa chart height': ['proj=vgridshift grids=core\\geoid12b\\g2012bu0.gtx',
                          '+inv proj=vgridshift grids=REGION\\tss.gtx',
                          'proj=vgridshift grids=REGION\\mhw.gtx']
    }


def get_regional_pipeline(from_datum: str, to_datum: str, region_name: str, is_alaska: bool = False):
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
    is_alaska
        if True, regions are in alaska, which means we need to do a string replace to go to xgeoid17b

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
    transformation_def = ['proj=pipeline', *reversed_input_def, *output_datum_def]
    pipeline = ' step '.join(transformation_def)
    regional_pipeline = pipeline.replace('REGION', region_name)
    if is_alaska:
        regional_pipeline = regional_pipeline.replace('geoid12b', 'xgeoid17b')
        regional_pipeline = regional_pipeline.replace('g2012bu0', 'AK_17B')
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
        raise ValueError(f'Input datum {from_datum} not found in datum definitions.')
    if to_datum not in datum_definition:
        raise ValueError(f'Output datum {to_datum} not found in datum definitions.')


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
        inverse.append(' '.join(['inv', layer]))
    return inverse
