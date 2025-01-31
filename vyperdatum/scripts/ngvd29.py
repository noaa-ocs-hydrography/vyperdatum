import os
from vyperdatum.transformer import Transformer
from vyperdatum.pipeline import Pipeline




if __name__ == "__main__":
    parent_dir = r"C:\Users\mohammad.ashkezari\Documents\projects\vyperdatum\untrack\data\raster\RSD\Alaska\Original"
    crs_from = "EPSG:6318+EPSG:7968"
    crs_to = "EPSG:6318+NOAA:98"
    # print(Pipeline(crs_from=crs_from, crs_to=crs_to).graph_steps())

    tf = Transformer(crs_from=crs_from,
                     crs_to=crs_to,
                     steps=['EPSG:6318+EPSG:7968', 'EPSG:6319', 'EPSG:7912', 'EPSG:9989', 'EPSG:9990+NOAA:98', 'EPSG:4267']
                     #  steps=Pipeline(crs_from=crs_from, crs_to=crs_to).linear_steps()
                     #  steps=Pipeline(crs_from=crs_from, crs_to=crs_to).graph_steps()
                     )

    # for i, input_file in enumerate(files[:1]):
    #     print(f"{i+1}/{len(files)}: {input_file}")
    #     tf = Transformer(crs_from=crs_from,
    #                      crs_to=crs_to,
    #                      steps=["EPSG:6346", "EPSG:6319", "EPSG:6318+NOAA:5224", "EPSG:6346+NOAA:5224"]
    #                     #  steps=Pipeline(crs_from=crs_from, crs_to=crs_to).linear_steps()
    #                     #  steps=Pipeline(crs_from=crs_from, crs_to=crs_to).graph_steps()
    #                      )
    #     tf.transform_raster(input_file=input_file,
    #                         output_file=input_file.replace("Original", "Manual"),
    #                         overview=False,
    #                         )
    #     print(f'\n{"*"*50} {i+1}/{len(files)} Completed {"*"*50}\n')
