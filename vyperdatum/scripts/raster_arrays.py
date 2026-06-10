
from __future__ import annotations

import os
import tempfile
import json
import gc
from pathlib import Path
from typing import List, Optional

import numpy as np
from osgeo import gdal, gdal_array
import geopandas as gpd
from shapely.geometry import Point
import pyproj as pp
import pyarrow as pa
import pyarrow.parquet as pq


gdal.UseExceptions()


class RasterArrays:
    """
    Flatten a raster into 1D arrays x, y, and bands[i], keeping only pixels
    where band 1 is NOT nodata.

    Attributes
    ----------
    x : np.ndarray or np.memmap
        1D x coordinates of valid pixel centers
    y : np.ndarray or np.memmap
        1D y coordinates of valid pixel centers
    bands : list[np.ndarray | np.memmap]
        Flattened band values at the same valid locations
    band_names : list[str]
        Band descriptions if present
    nodata : list[float | None]
        Nodata value for each band
    """

    def __init__(
        self,
        raster_path: str,
        out_dir: Optional[str] = None,
        backend: str = "memmap",   # "memmap" or "memory"
        coord_dtype=np.float32,
        band_dtype: Optional[np.dtype] = None,
        rows_per_chunk: int = 256,
        nodata_to_nan: bool = False,
        filter_on_band1_nodata: bool = True,
    ):
        self.path = str(raster_path)
        self.backend = backend
        self.coord_dtype = np.dtype(coord_dtype)
        self.band_dtype = np.dtype(band_dtype) if band_dtype is not None else None
        self.rows_per_chunk = int(rows_per_chunk)
        self.nodata_to_nan = nodata_to_nan
        self.filter_on_band1_nodata = filter_on_band1_nodata

        self.ds = gdal.Open(self.path, gdal.GA_ReadOnly)
        if self.ds is None:
            raise FileNotFoundError(f"Could not open raster: {self.path}")

        self.width = self.ds.RasterXSize
        self.height = self.ds.RasterYSize
        self.count = self.ds.RasterCount
        self.n_pixels_total = self.width * self.height

        self.geotransform = self.ds.GetGeoTransform()
        if self.geotransform is None:
            raise ValueError("Raster has no geotransform.")

        self.projection_wkt = self.ds.GetProjection()

        gt = self.geotransform
        if gt[2] != 0 or gt[4] != 0:
            raise ValueError(
                "This class currently supports only north-up rasters "
                "(no rotation/shear)."
            )

        if out_dir is None:
            out_dir = str(Path(self.path).with_suffix("")) + "_flat_arrays"
        self.out_dir = Path(out_dir)
        if self.backend == "memmap":
            self.out_dir.mkdir(parents=True, exist_ok=True)

        self.band_names: List[str] = []
        self.nodata: List[Optional[float]] = []

        # Gather band metadata
        self._init_band_metadata()

        # Count valid pixels based on band 1 nodata
        self.n_valid = self._count_valid_pixels()

        # Allocate output arrays
        self.x = self._allocate_array("x", self.coord_dtype, self.n_valid)
        self.y = self._allocate_array("y", self.coord_dtype, self.n_valid)
        self.bands = []

        for i in range(1, self.count + 1):
            band = self.ds.GetRasterBand(i)
            dtype = self.band_dtype
            if dtype is None:
                dtype = np.dtype(
                    self._gdal_to_numpy_dtype(
                        band.DataType,
                        nodata_to_nan=self.nodata_to_nan,
                        nodata_value=self.nodata[i - 1],
                    )
                )
            self.bands.append(self._allocate_band_array(i, dtype, self.n_valid))

        # Fill arrays
        self._build_flat_arrays()

    def _init_band_metadata(self) -> None:
        for i in range(1, self.count + 1):
            band = self.ds.GetRasterBand(i)
            self.band_names.append(band.GetDescription() or f"band_{i}")
            self.nodata.append(band.GetNoDataValue())

    def _allocate_array(self, name: str, dtype: np.dtype, n: int):
        if self.backend == "memory":
            return np.empty((n,), dtype=dtype)
        elif self.backend == "memmap":
            path = self.out_dir / f"{name}.dat"
            return np.memmap(path, mode="w+", dtype=dtype, shape=(n,))
        else:
            raise ValueError("backend must be 'memory' or 'memmap'")

    def _allocate_band_array(self, band_index: int, dtype: np.dtype, n: int):
        if self.backend == "memory":
            return np.empty((n,), dtype=dtype)
        else:
            path = self.out_dir / f"band_{band_index}.dat"
            return np.memmap(path, mode="w+", dtype=dtype, shape=(n,))

    @staticmethod
    def _gdal_to_numpy_dtype(
        gdal_dtype: int,
        nodata_to_nan: bool = False,
        nodata_value: Optional[float] = None,
    ):
        np_dtype = np.dtype(gdal_array.GDALTypeCodeToNumericTypeCode(gdal_dtype))
        if nodata_to_nan and nodata_value is not None and np.issubdtype(np_dtype, np.integer):
            return np.float32
        return np_dtype

    @staticmethod
    def _valid_mask(block: np.ndarray, nodata_value: Optional[float]) -> np.ndarray:
        if nodata_value is None:
            return np.ones(block.shape, dtype=bool)
        if isinstance(nodata_value, float) and np.isnan(nodata_value):
            return ~np.isnan(block)
        return block != nodata_value

    def _count_valid_pixels(self) -> int:
        if not self.filter_on_band1_nodata:
            return self.n_pixels_total

        band1 = self.ds.GetRasterBand(1)
        nd = band1.GetNoDataValue()

        # If band 1 has no nodata defined, keep everything
        if nd is None:
            return self.n_pixels_total

        total = 0
        for row_start in range(0, self.height, self.rows_per_chunk):
            nrows = min(self.rows_per_chunk, self.height - row_start)
            block = band1.ReadAsArray(
                xoff=0,
                yoff=row_start,
                win_xsize=self.width,
                win_ysize=nrows,
            )
            if block is None:
                raise RuntimeError(f"Failed reading band 1 rows {row_start}:{row_start+nrows}")

            valid = self._valid_mask(np.asarray(block), nd)
            total += int(valid.sum())

        return total

    def _build_flat_arrays(self) -> None:
        gt = self.geotransform
        x0, dx, _, y0, _, dy = gt

        band_objs = [self.ds.GetRasterBand(i) for i in range(1, self.count + 1)]
        band1_nd = self.nodata[0]

        cursor = 0

        for row_start in range(0, self.height, self.rows_per_chunk):
            nrows = min(self.rows_per_chunk, self.height - row_start)
            row_stop = row_start + nrows

            band1_block = band_objs[0].ReadAsArray(
                xoff=0,
                yoff=row_start,
                win_xsize=self.width,
                win_ysize=nrows,
            )
            if band1_block is None:
                raise RuntimeError(f"Failed reading band 1 rows {row_start}:{row_stop}")

            band1_block = np.asarray(band1_block)

            if self.filter_on_band1_nodata and band1_nd is not None:
                valid = self._valid_mask(band1_block, band1_nd)
            else:
                valid = np.ones(band1_block.shape, dtype=bool)

            rr, cc = np.nonzero(valid)
            n_valid_chunk = len(rr)

            if n_valid_chunk == 0:
                continue

            out_slice = slice(cursor, cursor + n_valid_chunk)

            # x, y at valid pixels only
            self.x[out_slice] = x0 + (cc.astype(self.coord_dtype) + 0.5) * dx
            self.y[out_slice] = y0 + ((row_start + rr).astype(self.coord_dtype) + 0.5) * dy

            # all bands at same valid locations
            for band_idx, band in enumerate(band_objs):
                block = band.ReadAsArray(
                    xoff=0,
                    yoff=row_start,
                    win_xsize=self.width,
                    win_ysize=nrows,
                )
                if block is None:
                    raise RuntimeError(
                        f"Failed to read band {band_idx + 1} rows {row_start}:{row_stop}"
                    )

                block = np.asarray(block)
                vals = block[valid]

                nd = self.nodata[band_idx]
                out = self.bands[band_idx]

                if self.nodata_to_nan and nd is not None:
                    vals = vals.astype(
                        np.float32 if out.dtype == np.float32 else np.float64,
                        copy=False,
                    )
                    if isinstance(nd, float) and np.isnan(nd):
                        vals[np.isnan(vals)] = np.nan
                    else:
                        vals[vals == nd] = np.nan
                else:
                    if vals.dtype != out.dtype:
                        vals = vals.astype(out.dtype, copy=False)

                out[out_slice] = vals

            cursor += n_valid_chunk

        self.flush()

    def flush(self) -> None:
        if isinstance(self.x, np.memmap):
            self.x.flush()
        if isinstance(self.y, np.memmap):
            self.y.flush()
        for b in self.bands:
            if isinstance(b, np.memmap):
                b.flush()

    def cleanup(self, remove_dir: bool = True) -> None:
        self.flush()
        self.ds = None

        self.x = None
        self.y = None
        self.bands = []

        gc.collect()

        if self.backend != "memmap":
            return

        for p in self.out_dir.glob("*.dat"):
            try:
                p.unlink()
            except PermissionError:
                print(f"Could not delete {p}; file may still be open.")

        if remove_dir:
            try:
                self.out_dir.rmdir()
            except OSError:
                pass

    def close(self) -> None:
        self.flush()
        self.ds = None

    def __repr__(self) -> str:
        return (
            f"RasterArrays(path={self.path!r}, \nsize=({self.height}, {self.width}), \n"
            f"bands={self.count}, \nx.shape={self.x.shape}, \n"
            f"y.shape={self.y.shape}, \nbands[0].shape={self.bands[0].shape}, \n"
            f"bands_names={self.band_names}, \nnodata_values={self.nodata}, \n"
            f"valid_pixels={self.n_valid}, \nbackend={self.backend!r})"
        )

    def _compute_output_bbox(
        self,
        transformer_instance,
        chunk_size: int,
        ignore_non_finite: bool,
        include_all_bands: bool,
    ) -> list[float] | None:
        """
        Compute output XY extent of the points that will actually be written.
        Returns [xmin, ymin, xmax, ymax] or None if no valid points exist.
        """
        xmin = np.inf
        ymin = np.inf
        xmax = -np.inf
        ymax = -np.inf
        found = False

        n = self.n_valid

        for start in range(0, n, chunk_size):
            stop = min(start + chunk_size, n)

            x = np.asarray(self.x[start:stop])
            y = np.asarray(self.y[start:stop])
            z = np.asarray(self.bands[0][start:stop])

            success, xt, yt, zt = transformer_instance.transform_points(
                x, y, z, vdatum_check=False
            )

            xt = np.asarray(xt)
            yt = np.asarray(yt)
            zt = np.asarray(zt)

            valid = np.isfinite(xt) & np.isfinite(yt)

            if ignore_non_finite:
                valid &= np.isfinite(zt)
                for arr in self.bands:
                    valid &= np.isfinite(np.asarray(arr[start:stop]))

            if not np.any(valid):
                continue

            xv = xt[valid]
            yv = yt[valid]

            xmin = min(xmin, float(np.min(xv)))
            ymin = min(ymin, float(np.min(yv)))
            xmax = max(xmax, float(np.max(xv)))
            ymax = max(ymax, float(np.max(yv)))
            found = True

        if not found:
            return None

        return [xmin, ymin, xmax, ymax]


    @staticmethod
    def _set_geo_metadata_bbox(schema, geometry_column: str, bbox: list[float] | None):
        """
        Patch GeoParquet 'geo' metadata with bbox for the active geometry column.
        """
        if bbox is None:
            return schema

        md = dict(schema.metadata or {})
        geo_raw = md.get(b"geo")
        if geo_raw is None:
            return schema

        geo = json.loads(geo_raw.decode("utf-8"))
        geo.setdefault("columns", {})
        geo["columns"].setdefault(geometry_column, {})
        geo["columns"][geometry_column]["bbox"] = [float(v) for v in bbox]

        md[b"geo"] = json.dumps(geo).encode("utf-8")
        return schema.with_metadata(md)

    def transform(
        self,
        transformer_instance,
        output_file: str,
        chunk_size: int = 150_000,
        compression: str = "gzip",
        keep_xyz: bool = False,
        include_all_bands: bool = False,
        ignore_non_finite: bool = True,
        include_NBS_additional: bool = True,
        classification: int = 1,
        set_extent_metadata: bool = True,
    ) -> bool:
        """
        Transform valid points in chunks and write a single GeoParquet file
        with geometry and optional attributes.

        Column order
        ------------
        geometry, uncertainty, classification, [optional others...]

        Parameters
        ----------
        transformer_instance
            Object with transform_points(x, y, z, vdatum_check=False)
        output_file : str
            Output GeoParquet path.
        chunk_size : int
            Number of points per chunk.
        compression : str
            Parquet compression codec.
        keep_xyz : bool
            If True, also write transformed x/y/z columns.
        include_all_bands : bool
            If True, include source band values as extra attributes.
        ignore_non_finite : bool
            If True, drop rows where any transformed x/y/z, any source band,
            or any optional derived output value is NaN, +inf, or -inf.
        include_NBS_additional : bool
            If True, add:
            - uncertainty = 1 + 0.02 * transformed_z
            - classification = constant integer value
        classification : int
            Constant integer value written to the "classification" column when
            include_NBS_additional=True.

        Returns
        -------
        bool
            True if all chunks reported success, else False.
        """
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        target_crs = pp.CRS(transformer_instance.crs_to)
        writer = None
        schema = None
        all_success = True
        wrote_any_rows = False

        overall_bbox = None
        if set_extent_metadata:
            overall_bbox = self._compute_output_bbox(
                transformer_instance=transformer_instance,
                chunk_size=chunk_size,
                ignore_non_finite=ignore_non_finite,
                include_all_bands=include_all_bands,
            )

        band_cols = []
        if include_all_bands:
            used = {"geometry", "x", "y", "z", "uncertainty", "classification"}
            for i, name in enumerate(self.band_names):
                col = str(name).strip() or f"band_{i+1}"
                if i == 0:
                    col = f"source_{col}"
                base = col
                k = 2
                while col in used:
                    col = f"{base}_{k}"
                    k += 1
                used.add(col)
                band_cols.append(col)

        try:
            n = self.n_valid

            for start in range(0, n, chunk_size):
                stop = min(start + chunk_size, n)

                x = np.asarray(self.x[start:stop])
                y = np.asarray(self.y[start:stop])
                z = np.asarray(self.bands[0][start:stop])

                success, xt, yt, zt = transformer_instance.transform_points(
                    x, y, z, vdatum_check=False, allow_ballpark=False
                )
                all_success = all_success and bool(success)

                xt = np.asarray(xt)
                yt = np.asarray(yt)
                zt = np.asarray(zt)

                band_slices = [np.asarray(b[start:stop]) for b in self.bands]

                if include_NBS_additional:
                    uncertainty = np.where(
                        zt < 0,
                        1.0 + 0.02 * np.abs(zt),
                        1.0,
                    )
                    uncertainty = np.round(uncertainty, 2).astype(np.float32)
                    classification_arr = np.full(zt.shape, classification, dtype=np.int32)

                if ignore_non_finite:
                    valid = np.isfinite(xt) & np.isfinite(yt) & np.isfinite(zt)

                    # Drop points where PROJ failed the gridshift and passed Z through unchanged
                    # (Using a small tolerance of 0.001 to account for float precision)
                    # valid &= (np.abs(zt - z) > 0.001)

                    for arr in band_slices:
                        valid &= np.isfinite(arr)

                    if include_NBS_additional:
                        valid &= np.isfinite(uncertainty)

                    if not np.any(valid):
                        continue

                    xt = xt[valid]
                    yt = yt[valid]
                    zt = zt[valid]
                    band_slices = [arr[valid] for arr in band_slices]

                    if include_NBS_additional:
                        uncertainty = uncertainty[valid]
                        classification_arr = classification_arr[valid]

                if xt.size == 0:
                    continue

                data = {}

                if include_NBS_additional:
                    data["uncertainty"] = uncertainty
                    data["classification"] = classification_arr

                if keep_xyz:
                    data["x"] = xt
                    data["y"] = yt
                    data["z"] = zt

                if include_all_bands:
                    for i, col_name in enumerate(band_cols):
                        data[col_name] = band_slices[i]

                geometry = gpd.points_from_xy(xt, yt, z=zt)

                

                gdf = gpd.GeoDataFrame(
                    data,
                    geometry=geometry,
                    crs=target_crs,
                )


                ordered_cols = ["geometry"]
                if include_NBS_additional:
                    ordered_cols.extend(["uncertainty", "classification"])
                if keep_xyz:
                    ordered_cols.extend(["x", "y", "z"])
                if include_all_bands:
                    ordered_cols.extend(band_cols)

                gdf = gdf[ordered_cols]

                chunk_table = pa.table(
                    gdf.to_arrow(index=False, geometry_encoding="WKB")
                )

                if writer is None:
                    with tempfile.NamedTemporaryFile(suffix=".parquet", delete=False) as tmp:
                        tmp_name = tmp.name

                    try:
                        gdf.iloc[:1].to_parquet(
                            tmp_name,
                            index=False,
                            compression=compression,
                            geometry_encoding="WKB",
                        )
                        bootstrap_table = pq.read_table(tmp_name)
                        schema = bootstrap_table.schema
                        schema = self._set_geo_metadata_bbox(
                            schema=schema,
                            geometry_column="geometry",
                            bbox=overall_bbox,
                        )
                    finally:
                        if os.path.exists(tmp_name):
                            os.remove(tmp_name)

                    chunk_table = pa.Table.from_arrays(
                        [chunk_table[name] for name in schema.names],
                        schema=schema,
                    )

                    writer = pq.ParquetWriter(
                        str(output_path),
                        schema=schema,
                        compression=compression,
                    )
                else:
                    chunk_table = pa.Table.from_arrays(
                        [chunk_table[name] for name in schema.names],
                        schema=schema,
                    )

                writer.write_table(chunk_table)
                wrote_any_rows = True

            if not wrote_any_rows:
                raise ValueError("No finite transformed points were available to write.")

            return all_success

        finally:
            if writer is not None:
                writer.close()
