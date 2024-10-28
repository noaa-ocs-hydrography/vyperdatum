import os
import time
from typing import Union
import pathlib
import logging
import shutil
from copy import deepcopy
import h5py
import concurrent.futures
import numpy as np
import pyproj as pp
from tqdm import tqdm
from osgeo import gdal
from vyperdatum.transformer import Transformer
from vyperdatum.utils.raster_utils import raster_metadata

logger = logging.getLogger("root_logger")


class VRBAG():
    def __init__(self,
                 input_file: str
                 ) -> None:
        """

        Parameters
        ----------
        input_file : str
            Full path to the BAG file.
        """
        self.NO_META = 0xffffffff
        self.NDV_REF = 1000000
        self.input_file = input_file
        bag = h5py.File(self.input_file)
        self.meta_gdal = raster_metadata(self.input_file)
        self.meta_xml = bag["BAG_root/metadata"]
        self.vr_meta = bag["BAG_root/varres_metadata"]
        self.vr_ref = bag["BAG_root/varres_refinements"][0]
        self.vr = "varres_refinements" in list(bag["BAG_root"].keys())
        bag.close()
        return

    def subgrid_transform(self,
                          rasters_dir: str,
                          i: int,
                          j: int,
                          tf: Transformer
                          ) -> tuple[int, np.ndarray]:
        """
        Extract a subgrid from from the vrbag file, covert to GeoTiff, and apply transformation.

        Parameters
        ----------
        rasters_dir : str
            Absolute path to the directory where the output TIFF files will be stored.
        i: int
            First index of the subgrid.
        j: int
            Second index of the subgrid.
        tf: vyperdatum.transformer.Transformer
            Instance of the transformer class.
        nodata_value: float
            No_Data_Value used for the generated GeoTiff.

        Returns
        ----------
            The starting index of the subgrid in the varres_refinements layer.
            The transformed subgrid in form of a 1-d array.
        """

        try:
            geot = self.meta_gdal["geo_transform"]
            wkt = self.meta_gdal["wkt"]
            bag = h5py.File(self.input_file)
            root = bag["BAG_root"]
            vr_meta = root["varres_metadata"]
            vr_ref = root["varres_refinements"][0]
            start = vr_meta[i, j][0]

            dim_x, dim_y = vr_meta[i, j][1], vr_meta[i, j][2]
            res_x, res_y = vr_meta[i, j][3], vr_meta[i, j][4]
            sw_corner_x, sw_corner_y = vr_meta[i, j][5], vr_meta[i, j][6]

            sub_x_min = sw_corner_x + j * geot[1]
            sub_y_min = sw_corner_y + i * abs(geot[5])
            sub_extent = [sub_x_min, sub_y_min, sub_x_min + geot[1], sub_y_min + abs(geot[5])]
            sub_geot = (sub_extent[0], res_x, 0, sub_extent[3], 0, -res_y)
            sub_grid = vr_ref[start:start+(dim_x*dim_y)]["depth"].reshape((dim_y, dim_x))

            # Save subgrid as Geotiff
            driver = gdal.GetDriverByName("GTiff")
            sub_raster_fname = f"{rasters_dir}{i}_{j}.tiff"
            out_ds = driver.Create(sub_raster_fname, sub_grid.shape[1],
                                   sub_grid.shape[0], 1, gdal.GDT_Float32)
            out_ds.SetProjection(wkt)
            out_ds.SetGeoTransform(sub_geot)
            band = out_ds.GetRasterBand(1)
            band.WriteArray(sub_grid)
            band.SetNoDataValue(self.NDV_REF)
            band.FlushCache()
            band.ComputeStatistics(False)
            out_ds = None

            transformed_sub_fname = f"{rasters_dir}t_{i}_{j}.tiff"
            tf.transform_raster(input_file=sub_raster_fname, output_file=transformed_sub_fname,
                                pre_post_checks=False, vdatum_check=False)
            ds = gdal.Open(transformed_sub_fname)
            transformed_refs = ds.GetRasterBand(1).ReadAsArray().flatten()
            ds = None
            gdal.Unlink(sub_raster_fname)
            gdal.Unlink(transformed_sub_fname)
        except Exception as e:
            print(e)
            start, transformed_refs = None, None
        return start, transformed_refs

    def subgrid_raster_transform(self,
                                 rasters_dir: str
                                 ) -> tuple[list[int], list[float]]:
        """
        Identify the subgrids within the vrbag and return the starting
        index and the depth values within each subgrid.

        Parameters
        ----------
        rasters_dir : str
            Absolute path to the directory where the output TIFF files will be stored.

        Returns
        ----------
        list[int], list[float]
            Starting index of each subgrid.
            Transformed subgrid depth values.
        """

        if rasters_dir.split("/")[0].lower() != "vsimem":
            if os.path.isdir(rasters_dir):
                shutil.rmtree(rasters_dir)
            os.makedirs(rasters_dir)
        bag = h5py.File(self.input_file)
        root = bag["BAG_root"]
        vr_meta = root["varres_metadata"]
        start_indices, transformed_refs, ii, jj = [], [], [], []
        tf = Transformer(crs_from="EPSG:32617+EPSG:5866",
                         crs_to="EPSG:26917+EPSG:5866",
                         steps=["EPSG:32617+EPSG:5866", "EPSG:9755", "EPSG:6318", "EPSG:26917+EPSG:5866"]
                         )
        for i in tqdm(range(vr_meta.shape[0]), desc="Making subgrid rasters"):
            for j in range(vr_meta.shape[1]):
                start = vr_meta[i, j][0]
                if start == self.NO_META:
                    continue
                ii.append(i)
                jj.append(j)
        bag.close()
        with concurrent.futures.ProcessPoolExecutor() as executor:
            futureObjs = executor.map(self.subgrid_transform,
                                      [rasters_dir] * len(ii),
                                      ii, jj,
                                      [tf] * len(ii)
                                      )
            for i, fo in enumerate(futureObjs):
                if fo[0] is not None:
                    start_indices.append(fo[0])
                    transformed_refs.append(fo[1])
        return start_indices, transformed_refs

    def update_vr_refinements(self,
                              index: list[int],
                              arr: list[np.ndarray]
                              ):
        bag = h5py.File(self.input_file, "r+")
        root = bag.require_group("/BAG_root")
        vr_ref = root["varres_refinements"]
        vr_ref_type = [("depth", np.float32), ("depth_uncrt", np.float32)]
        vr_ref = np.array(vr_ref, dtype=vr_ref_type)
        for i, index_start in enumerate(index):
            vr_ref[0][index_start:len(arr[i])+index_start]["depth"] = arr[i]
        del root["varres_refinements"]
        root.create_dataset("varres_refinements",
                            maxshape=(1, None),
                            data=vr_ref,
                            # fillvalue=np.array([(NDV_REF, NDV_REF)], dtype=vr_ref_type),
                            compression="gzip",
                            compression_opts=9
                            )
        bag.close()
        return


if __name__ == "__main__":
    vb = VRBAG(input_file=r"C:\Users\mohammad.ashkezari\Desktop\original_vrbag\W00656_MB_VR_MLLW_5of5.bag")
    tic = time.time()
    index, zt = vb.subgrid_raster_transform(rasters_dir="/vsimem/sub_grids/")
    print("total time: ", time.time() - tic)
    vb.update_vr_refinements(index=index, arr=zt)
