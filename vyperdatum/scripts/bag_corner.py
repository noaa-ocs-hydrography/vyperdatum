from vyperdatum.transformer import Transformer
from io import BytesIO
import h5py
import numpy as np
from lxml import etree
import pyproj as pp


def transform_w(p):
    crs_from = "EPSG:32617+EPSG:5866"
    crs_to = "EPSG:26917+EPSG:5866"
    tf = Transformer(crs_from=crs_from,
                     crs_to=crs_to,
                     steps=["EPSG:32617", "EPSG:9755", "EPSG:6318", "EPSG:26917"]
                     )
    y, x, z = tf.transform_points(p[1], p[0], 0, always_xy=False, allow_ballpark=False)
    return f"{x},{y}"


def transform_h(p):
    crs_from = "EPSG:32619+EPSG:5866"
    crs_to = "EPSG:6348+EPSG:5866"
    tf = Transformer(crs_from=crs_from,
                     crs_to=crs_to,
                     steps=["EPSG:32619", "EPSG:9755", "EPSG:6318", "EPSG:6348"]
                     )
    y, x, z = tf.transform_points(p[1], p[0], 0, always_xy=False, allow_ballpark=False)
    return f"{x},{y}"


def corner_points(bag_fname: str):
    """
    Return the corner points.
    """
    bag = h5py.File(bag_fname)
    meta = bag["BAG_root/metadata"]
    buffer = BytesIO(meta[()])
    tree = etree.parse(buffer)
    root = tree.getroot()
    gml = ".//{" + root.nsmap['gml'] + "}"
    return root.find(f"{gml}coordinates").text


def change_corner_points(bag_fname: str, new_points: str, wkt_h: str, wkt_v: str):
    """
    Update the metadata's corner points with new points.
    """
    bag = h5py.File(bag_fname)
    meta = bag["BAG_root/metadata"]
    buffer = BytesIO(meta[()])
    tree = etree.parse(buffer)
    root = tree.getroot()
    gml = ".//{" + root.nsmap['gml'] + "}"
    gco = ".//{" + root.nsmap['gco'] + "}"
    root.find(f"{gml}coordinates").text = new_points
    root.findall(f"{gco}CharacterString")[6].text = wkt_h
    root.findall(f"{gco}CharacterString")[8].text = wkt_v
    # tree.write(xml_fname)
    # xml = etree.tostring(root, pretty_print=True).decode("ascii")
    xmet = etree.tostring(root).decode()
    bag.close()
    bag = h5py.File(bag_fname, mode="r+")
    root = bag.require_group("/BAG_root")
    del bag["/BAG_root/metadata"]
    metadata = np.array(list(xmet), dtype="S1")
    root.create_dataset("metadata", maxshape=(None,), data=metadata, compression="gzip", compression_opts=9)
    bag.close()
    return


def update_W00656():
    w_p1 = (278881.198477, 2719890.433477)
    w_p2 = (293586.271523, 2734595.506523)
    new_w_corners = transform_w(w_p1) + " " + transform_w(w_p2)
    bag_fname = "W00656_MB_VR_MLLW_5of5.bag"
    print(corner_points(bag_fname=bag_fname))
    change_corner_points(bag_fname=bag_fname, new_points=new_w_corners, wkt_h=pp.CRS("EPSG:26917").to_wkt(), wkt_v=pp.CRS("EPSG:5866").to_wkt())
    print(corner_points(bag_fname=bag_fname))
    return


def update_H12137():
    h_p1 = (259274.885634, 4549506.909634)
    h_p2 = (280112.069366, 4570344.093366)
    new_h_corners = transform_h(h_p1) + " " + transform_h(h_p2)
    bag_fname = "H12137_MB_VR_MLLW_1of1.bag"
    print(corner_points(bag_fname=bag_fname))
    change_corner_points(bag_fname=bag_fname, new_points=new_h_corners, wkt_h=pp.CRS("EPSG:6348").to_wkt(), wkt_v=pp.CRS("EPSG:5866").to_wkt())
    print(corner_points(bag_fname=bag_fname))
    return


update_W00656()
update_H12137()



# bag_fname = "W00656_MB_VR_MLLW_5of5.bag"
# bag = h5py.File(bag_fname)
# meta = bag["BAG_root/metadata"]
# buffer = BytesIO(meta[()])
# tree = etree.parse(buffer)
# root = tree.getroot()
# gco = ".//{" + root.nsmap['gco'] + "}"
# css = root.findall(f"{gco}CharacterString")
# print(len(css))
# for i, cs in enumerate(css):
#     print(i)
#     print(cs.text[:5])
#     print("///////")
# bag.close()