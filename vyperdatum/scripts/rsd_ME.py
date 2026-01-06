from vyperdatum.transformer import Transformer
from glob import glob
import numpy as np
from osgeo import gdal


gdal.UseExceptions()


crs_from = "EPSG:6348"
crs_to = "EPSG:6348+NOAA:98"

input_files = glob(r"C:\Users\mohammad.ashkezari\Documents\projects\vyperdatum\untrack\data\raster\RSD\ME\Original\**\*.tif", recursive=True)
for i, input_file in enumerate(input_files):
    print(f"Processing ({i}/{len(input_files)}): {input_file}")
    try:
        output_file = input_file.replace("Original", "Manual")
        tf = Transformer(crs_from=crs_from,
                        crs_to=crs_to,
                        )
        tf.transform(input_file=input_file,
                    output_file=output_file,
                    pre_post_checks=True,
                    vdatum_check=True
                    )
    except Exception as e:
        print(f"Error processing {input_file}: {e}")
        continue