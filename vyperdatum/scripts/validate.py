import pyproj as pp
from vyperdatum.transformer import Transformer
from pyproj.transformer import TransformerGroup

print(f"proj dat dir: {pp.datadir.get_data_dir()}")

crs_from = f"EPSG:6318+NOAA:25101"
crs_to = f"EPSG:6318+NOAA:98"

t1 = pp.Transformer.from_crs(crs_from=crs_from,
                                crs_to=crs_to,
                                allow_ballpark=True,
                                only_best=True
                                )

# tf = Transformer(crs_from=crs_from,crs_to=crs_to)

tg = TransformerGroup(crs_from=crs_from,
                    crs_to=crs_to,
                    allow_ballpark=True,
                    )

print(f"Number of transformers: {len(tg.transformers)}")