from vyperdatum.transformer import Transformer


input_file = r"C:\Users\mohammad.ashkezari\Documents\projects\vyperdatum\untrack\data\geoparquet_test\South_Locust_Point_&_Masonville_&_Ferry_Bar_&_Fairfield_2023_Elevation_MLLW_3ftx3ft.parquet"
output_file = r"C:\Users\mohammad.ashkezari\Documents\projects\vyperdatum\untrack\data\geoparquet_test\output.parquet"

crs_from = "EPSG:6347+NOAA:98"
crs_to = "EPSG:6347+EPSG:5703"
tf = Transformer(crs_from=crs_from, crs_to=crs_to)
tf.transform(input_file=input_file,
             output_file=output_file,
             pre_post_checks=True,
             vdatum_check=True
             )