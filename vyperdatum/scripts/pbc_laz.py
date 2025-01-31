from vyperdatum.transformer import Transformer


if __name__ == "__main__":
    in_fname = r"C:\Users\mohammad.ashkezari\Desktop\laz\ma2021_cent_east_Job1082403.laz"
    out_fname = r"C:\Users\mohammad.ashkezari\Desktop\laz\transformed_ma2021_cent_east_Job1082403.laz"

    crs_from = "EPSG:6348+EPSG:5703"
    crs_to = "EPSG:6348+NOAA:5320"
    steps = ["EPSG:6348+EPSG:5703", "EPSG:6318+EPSG:5703", "EPSG:6318+NOAA:5320", "EPSG:6348+NOAA:5320"]
    tf = Transformer(crs_from=crs_from, crs_to=crs_to, steps=steps)
    tf.transform(input_file=in_fname, output_file=out_fname)
