import os
from vyperdatum.transformer import Transformer


fname = r"C:\Users\mohammad.ashkezari\Desktop\original_vrbag\W00656_MB_VR_MLLW_5of5.bag"
crs_from = "EPSG:32617+EPSG:5866"
crs_to = "EPSG:26917+EPSG:5866"
steps = ["EPSG:32617+EPSG:5866", "EPSG:9755", "EPSG:6318", "EPSG:26917+EPSG:5866"]
tf = Transformer(crs_from=crs_from, crs_to=crs_to, steps=steps)
d, f = os.path.split(fname)
output_file = os.path.join(d, f"transformed_{f}")
tf.transform(input_file=fname, output_file=output_file)
