

import pandas as pd
from vyperdatum.db import DB
import pyproj as pp
from pyproj.transformer import TransformerGroup


def test_noaa_transforms():
    """
    Check if PROJ can instantiate a transformer using the NOAA-defined transformations.
    """
    sql = "select * from coordinate_operation_view where deprecated=0 and (source_crs_auth_name='NOAA' or target_crs_auth_name='NOAA')"
    df = DB().query(sql, dataframe=True)
    failures = {"source_crs": [], "target_crs": [], "error_msg": []}
    failed_transforms = pd.DataFrame.from_dict(failures)
    for _, row in df.iterrows():
        source_crs = f"{row['source_crs_auth_name']}:{row['source_crs_code']}"
        target_crs = f"{row['target_crs_auth_name']}:{row['target_crs_code']}"
        tg = TransformerGroup(crs_from=pp.CRS(source_crs),
                              crs_to=pp.CRS(target_crs),
                              allow_ballpark=False
                              )
        if len(tg.transformers) == 0:
            error_msg = ""
            try:
                pp.Transformer.from_crs(crs_from=pp.CRS(source_crs),
                                        crs_to=pp.CRS(target_crs),
                                        allow_ballpark=False,
                                        only_best=True
                                        )

            except Exception as e:
                error_msg = str(e)
            failures["source_crs"].append(source_crs)
            failures["target_crs"].append(target_crs)
            failures["error_msg"].append(error_msg)
    failed_transforms = pd.DataFrame.from_dict(failures)
    failed_transforms.to_csv("failed_transformers.csv", index=False)
    print(f"{len(failed_transforms)}/{len(df)} NOAA transformations failed to instantiate.")



test_noaa_transforms()