# import pytest
# from vyperdatum.pipeline import Pipeline


# @pytest.mark.parametrize("crs_from, crs_to", [("EPSG:6348", "EPSG:6348+NOAA:5320"),
#                                               ("EPSG:26919", "EPSG:26919+NOAA:5434"),
#                                               ("EPSG:6347", "EPSG:6347+NOAA:5200")
#                                               ])
# def test_linear_path(crs_from, crs_to):
#     pipe = Pipeline(crs_from=crs_from,
#                     crs_to=crs_to
#                     )
#     linear_route = pipe.linear_steps()
#     graph_route = pipe.graph_steps()
#     expected = {
#                 ("EPSG:6348", "EPSG:6348+NOAA:5320"): {
#                                                        "linear": ["EPSG:6348", "EPSG:6319",
#                                                                   "EPSG:6318+NOAA:5320",
#                                                                   "EPSG:6348+NOAA:5320"],
#                                                        "graph": ["EPSG:6348", "EPSG:6319",
#                                                                  "NOAA:8322",
#                                                                  "EPSG:6348+NOAA:5320"]
#                                                        },
#                 ("EPSG:26919", "EPSG:26919+NOAA:5434"): {
#                                                        "linear": ["EPSG:26919", "EPSG:4269",
#                                                                   "EPSG:6319",
#                                                                   "EPSG:6318+NOAA:5434",
#                                                                   "EPSG:4269+NOAA:5434",
#                                                                   "EPSG:26919+NOAA:5434"],
#                                                        "graph": ["EPSG:26919", "EPSG:4269",
#                                                                  "EPSG:6319", "NOAA:8436",
#                                                                  "EPSG:4269+NOAA:5434",
#                                                                  "EPSG:26919+NOAA:5434"]
#                                                        },
#                 ("EPSG:6347", "EPSG:6347+NOAA:5200"): {
#                                                        "linear": ["EPSG:6347", "EPSG:6319",
#                                                                   "EPSG:7912",
#                                                                   "EPSG:9000+NOAA:5200",
#                                                                   "EPSG:6318+NOAA:5200",
#                                                                   "EPSG:6347+NOAA:5200"],
#                                                        "graph":  ["EPSG:6347", "EPSG:6319",
#                                                                   "EPSG:7912", "NOAA:8200",
#                                                                   "EPSG:6318+NOAA:5200",
#                                                                   "EPSG:6347+NOAA:5200"]
#                                                        }
#                 }
#     assert linear_route == expected[(crs_from, crs_to)]["linear"], (f"Linear transformation test"
#                                                                     f" for {crs_from} --> {crs_to}"
#                                                                     " failed.")
#     assert graph_route == expected[(crs_from, crs_to)]["graph"], (f"Graph transformation test"
#                                                                   f" for {crs_from} --> {crs_to}"
#                                                                   " failed.")
