import glob
from vyperdatum.transformer import Transformer
from vyperdatum.utils.raster_utils import raster_metadata, update_raster_wkt
from vyperdatum.utils.vdatum_rest_utils import vdatum_cross_validate
import pyproj as pp




if __name__ == "__main__":

    parent_dir = r"C:\Users\mohammad.ashkezari\Documents\projects\vyperdatum\untrack\data\raster\PBA\PBA_WestCoast_UTM10N_NCD\Original\**\*.bag"
    files = glob.glob(parent_dir, recursive=True)[:1]
    crs_from = "EPSG:26910+NOAA:98"
    crs_to = "EPSG:26910+NOAA:88"

    # crs_from = "EPSG:26910+EPSG:5866"
    # crs_to = "EPSG:6339+EPSG:5866"
    # steps = [{'crs_from': 'EPSG:26910', 'crs_to': 'EPSG:6318', 'v_shift': False},
    #          {'crs_from': 'EPSG:6318', 'crs_to': 'EPSG:6339', 'v_shift': False}]

    steps = [
        {'crs_from': 'EPSG:26910', 'crs_to': 'EPSG:6318', 'v_shift': False},
        {'crs_from': 'EPSG:6318+NOAA:98', 'crs_to': 'EPSG:6318+NOAA:88', 'v_shift': True},
        # {'crs_from': 'EPSG:6318', 'crs_to': 'EPSG:26910', 'v_shift': False},
             ]


    # ###################################################
    # import pytest
    # import sys
    # # coords_lat_lon = (39, -76.5, 0)
    
    # # steps = [
    # # {'crs_from': 'EPSG:6349', 'crs_to': 'EPSG:6319', 'v_shift': True}
    # #         ] 

    # # success, x, y, z = Transformer(crs_from="EPSG:6349", crs_to="EPSG:6319", steps=steps).transform_points([coords_lat_lon[0]],[coords_lat_lon[1]],[coords_lat_lon[2]])
    # # print(x, y, z)
    # # # assert pytest.approx(x, abs=.01) == coords_lat_lon[0], "x coordinate should remain unchanged."
    # # # assert pytest.approx(y, abs=.01) == coords_lat_lon[1], "y coordinate should remain unchanged."
    # # # assert pytest.approx(z, abs=.01) == -33.29, "incorrect z coordinate transformation."    
    # # sys.exit



    # x1 = 613922.931016
    # y1 = 5061381.271016

    # ## fake inside
    # x1 = 614956
    # y1 = 5064834

    # x2 = 618970.618984
    # y2 = 5066428.958984

    # tf = Transformer(crs_from=crs_from,
    #                     crs_to=crs_to,
    #                     steps=steps
    #                     )
    # # _, y1, x1, _ = tf.transform_points([y1], [x1], [0], always_xy=False, allow_ballpark=False)
    # # _, y2, x2, _ = tf.transform_points([y2], [x2], [0], always_xy=False, allow_ballpark=False)

    # _, xx, yy, zz = tf.transform_points([y1], [x1], [0])
    # print(xx, yy, zz)

    
    # sys.exit()
    # ###################################################


    for i, input_file in enumerate(files):
        print(f"{i+1}/{len(files)}: {input_file}")
        # meta = raster_metadata(input_file)
        # print(meta['h_authcode'], meta['v_authcode'])
        tf = Transformer(crs_from=crs_from,
                         crs_to=crs_to,
                         steps=steps
                         )
        output_file = input_file.replace("Original", "Manual")
        tf.transform(input_file=input_file,
                     output_file=output_file,
                     pre_post_checks=True,
                     vdatum_check=False
                     )
        print(f'\n{"*"*50} {i+1}/{len(files)} Completed {"*"*50}\n')
