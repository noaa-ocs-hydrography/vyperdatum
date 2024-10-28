import os
import glob
from vyperdatum.transformer import Transformer
from vyperdatum.pipeline import Pipeline


if __name__ == "__main__":
    files = glob.glob(r"C:\Users\mohammad.ashkezari\Documents\projects\vyperdatum\untrack\data\raster\PBC\V\Original\**\*.tif", recursive=True)
    for i, input_file in enumerate(files):
        print(f"{i+1}/{len(files)}: {input_file}")
        if os.path.basename(input_file).startswith("MA"):
            crs_from = "EPSG:6348"
            crs_to = "EPSG:6348+NOAA:5320"
            tf = Transformer(crs_from=crs_from,
                             crs_to=crs_to,
                             steps=["EPSG:6348", "EPSG:6319", "EPSG:6318+NOAA:5320", "EPSG:6348+NOAA:5320"]
                            #  steps=Pipeline(crs_from=crs_from, crs_to=crs_to).linear_steps()
                            #  steps=Pipeline(crs_from=crs_from, crs_to=crs_to).graph_steps()
                             )
            tf.transform_raster(input_file=input_file,
                                output_file=input_file.replace("Original", "Manual"),
                                overview=False,
                                )
        elif os.path.basename(input_file).startswith("ma"):
            crs_from = "EPSG:26919"
            crs_to = "EPSG:26919+NOAA:5320"
            tf = Transformer(crs_from=crs_from,
                             crs_to=crs_to,
                             steps=["EPSG:26919", "EPSG:6319", "EPSG:6318+NOAA:5320", "EPSG:26919+NOAA:5320"]
                            #  steps=Pipeline(crs_from=crs_from, crs_to=crs_to).linear_steps()
                            #  steps=Pipeline(crs_from=crs_from, crs_to=crs_to).graph_steps()
                             )
            tf.transform_raster(input_file=input_file,
                                output_file=input_file.replace("Original", "Manual"),
                                overview=False,
                                )
        elif os.path.basename(input_file).startswith("ct") or os.path.basename(input_file).startswith("rh"):
            crs_from = "EPSG:26919"
            crs_to = "EPSG:26919+NOAA:5434"
            tf = Transformer(crs_from=crs_from,
                             crs_to=crs_to,
                            #  steps=["EPSG:26919", "EPSG:6319", "EPSG:6318+NOAA:5434", "EPSG:26919+NOAA:5434"]
                            #  steps=Pipeline(crs_from=crs_from, crs_to=crs_to).linear_steps()
                             steps=Pipeline(crs_from=crs_from, crs_to=crs_to).graph_steps()
                             )
            tf.transform_raster(input_file=input_file,
                                output_file=input_file.replace("Original", "Manual"),
                                overview=False,
                                )
        print(f'\n{"*"*50} {i+1}/{len(files)} Completed {"*"*50}\n')
