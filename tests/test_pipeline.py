import pytest
from vyperdatum.pipeline import Pipeline, nwld_NAD832011_steps
from vyperdatum.utils import crs_utils


@pytest.mark.parametrize("crs_from, crs_to", [("EPSG:6348", "EPSG:6348+NOAA:5320"),
                                              ("EPSG:26919", "EPSG:26919+NOAA:5434"),
                                              ("EPSG:6347", "EPSG:6347+NOAA:5200")
                                              ])
def test_linear_path(crs_from, crs_to):
    pipe = Pipeline(crs_from=crs_from,
                    crs_to=crs_to
                    )
    linear_route = pipe.linear_steps()
    graph_route = pipe.graph_steps()
    expected = {
                ("EPSG:6348", "EPSG:6348+NOAA:5320"): {
                                                       "linear": ["EPSG:6348", "EPSG:6319",
                                                                  "EPSG:6318+NOAA:5320",
                                                                  "EPSG:6348+NOAA:5320"],
                                                       "graph": ["EPSG:6348", "EPSG:6319",
                                                                 "NOAA:8322",
                                                                 "EPSG:6348+NOAA:5320"]
                                                       },
                ("EPSG:26919", "EPSG:26919+NOAA:5434"): {
                                                       "linear": ["EPSG:26919", "EPSG:4269",
                                                                  "EPSG:6319",
                                                                  "EPSG:6318+NOAA:5434",
                                                                  "EPSG:4269+NOAA:5434",
                                                                  "EPSG:26919+NOAA:5434"],
                                                       "graph": ["EPSG:26919", "EPSG:4269",
                                                                 "EPSG:6319", "NOAA:8436",
                                                                 "EPSG:4269+NOAA:5434",
                                                                 "EPSG:26919+NOAA:5434"]
                                                       },
                ("EPSG:6347", "EPSG:6347+NOAA:5200"): {
                                                       "linear": ["EPSG:6347", "EPSG:6319",
                                                                  "EPSG:7912",
                                                                  "EPSG:9000+NOAA:5200",
                                                                  "EPSG:6318+NOAA:5200",
                                                                  "EPSG:6347+NOAA:5200"],
                                                       "graph":  ["EPSG:6347", "EPSG:6319",
                                                                  "EPSG:7912", "NOAA:8200",
                                                                  "EPSG:6318+NOAA:5200",
                                                                  "EPSG:6347+NOAA:5200"]
                                                       }
                }
    assert linear_route == expected[(crs_from, crs_to)]["linear"], (f"Linear transformation test"
                                                                    f" for {crs_from} --> {crs_to}"
                                                                    " failed.")
    assert graph_route == expected[(crs_from, crs_to)]["graph"], (f"Graph transformation test"
                                                                  f" for {crs_from} --> {crs_to}"
                                                                  " failed.")


@pytest.mark.parametrize("crs_from, crs_to, expected", [
    # NAD83(2011) 3D in or out: no horizontal step, the vertical shift starts/ends at EPSG:6319
    ("EPSG:6319", "EPSG:6318+NOAA:98",
     [{"crs_from": "EPSG:6319", "crs_to": "EPSG:6318+NOAA:98", "v_shift": True}]),
    ("EPSG:6319", "EPSG:6346+NOAA:98",
     [{"crs_from": "EPSG:6319", "crs_to": "EPSG:6318+NOAA:98", "v_shift": True},
      {"crs_from": "EPSG:6318", "crs_to": "EPSG:6346", "v_shift": False}]),
    ("EPSG:6318+NOAA:98", "EPSG:6319",
     [{"crs_from": "EPSG:6318+NOAA:98", "crs_to": "EPSG:6319", "v_shift": True}]),
    ("EPSG:6346+NOAA:98", "EPSG:6319",
     [{"crs_from": "EPSG:6346", "crs_to": "EPSG:6318", "v_shift": False},
      {"crs_from": "EPSG:6318+NOAA:98", "crs_to": "EPSG:6319", "v_shift": True}]),
    # unchanged: projected input/output still go through EPSG:6318
    ("EPSG:6346", "EPSG:6346+NOAA:98",
     [{"crs_from": "EPSG:6346", "crs_to": "EPSG:6318", "v_shift": False},
      {"crs_from": "EPSG:6319", "crs_to": "EPSG:6318+NOAA:98", "v_shift": True},
      {"crs_from": "EPSG:6318", "crs_to": "EPSG:6346", "v_shift": False}]),
])
def test_nwld_NAD832011_steps_nad83_3d(crs_from, crs_to, expected):
    h0, v0 = crs_utils.crs_components(crs_from)
    h1, v1 = crs_utils.crs_components(crs_to)
    steps = nwld_NAD832011_steps(h0, v0, h1, v1)
    assert steps == expected, f"Unexpected steps for {crs_from} --> {crs_to}: {steps}"
    assert crs_utils.validate_transform_steps_dict(steps), (f"Invalid steps for"
                                                            f" {crs_from} --> {crs_to}: {steps}")
