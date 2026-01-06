from vyperdatum.transformer import Transformer


if __name__ == "__main__":

    input_file = r"C:\Users\mohammad.ashkezari\Documents\projects\vyperdatum\untrack\data\point\MLG\Original\AR_01_BAR_20240117_PR\AR_01_BAR_20240117_PR.XYZ"
    crs_from = "ESRI:103295+NOAA:1502" # MLG depth not usable for now, use NOAA:1502 USACE height
    crs_to = "EPSG:6344+NOAA:101"  # MLLW depth (due to current db issues, I use NOAA:101 and negate to get depth)
    negate_z = True  # MLG depth is negative, NOAA:98 is positive


    tf = Transformer(crs_from=crs_from,
                     crs_to=crs_to,
                    #  steps=steps
                     )
    output_file = input_file.replace("Original", "Manual")
    tf.transform(input_file=input_file,
                 output_file=output_file,
                 pre_post_checks=True,
                 vdatum_check=False,
                 negate_z=negate_z,
                 unit_conversion=0.3048006096
                 )


    # input_file = r"C:\Users\mohammad.ashkezari\Documents\projects\vyperdatum\untrack\data\point\MLG\Original\AR_01_BAR_20240117_PR\AR_01_BAR_20240117_PR.XYZ"
    # crs_from = "EPSG:3452+NOAA:1502" # MLG depth not usable for now, use NOAA:1502 USACE height
    # crs_to = "EPSG:6344+NOAA:100"  # MLLW depth (due to current db issues, I use NOAA:101 and negate to get depth)
    # negate_z = True  # MLG depth is negative, NOAA:98 is positive

    # steps = [{"crs_from": "EPSG:3452", "crs_to": "EPSG:6318", "v_shift": False},
    #          {"crs_from": "EPSG:6318+NOAA:1502", "crs_to": "EPSG:6318+NOAA:101", "v_shift": True},
    #          {"crs_from": "EPSG:6318", "crs_to": "EPSG:6344", "v_shift": False}
    #          ]

    # tf = Transformer(crs_from=crs_from,
    #                  crs_to=crs_to,
    #                  steps=steps
    #                  )
    # output_file = input_file.replace("Original", "Manual")
    # tf.transform(input_file=input_file,
    #              output_file=output_file,
    #              pre_post_checks=True,
    #              vdatum_check=False,
    #              negate_z=negate_z,
    #              unit_conversion=0.3048006096
    #              )
