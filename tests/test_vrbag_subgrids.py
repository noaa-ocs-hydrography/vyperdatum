"""
`vrbag.subgrid_point_transform()` must transform every refined subgrid of a VR BAG,
not just the first few.
"""
import h5py
import numpy as np

from vyperdatum.drivers import vrbag
from vyperdatum.enums import VRBAG as vrb_enum

VR_META_DTYPE = [("index", np.uint32),
                 ("dimensions_x", np.uint32), ("dimensions_y", np.uint32),
                 ("resolution_x", np.float32), ("resolution_y", np.float32),
                 ("sw_corner_x", np.float32), ("sw_corner_y", np.float32)]
VR_REF_DTYPE = [("depth", np.float32), ("depth_uncrt", np.float32)]
SUBGRID_DIM = 2
Z_SHIFT = 10.0

# (i, j) of the refined base-grid cells -> start index in `varres_refinements`.
# Six refined cells over several rows, so more than the first three must be handled.
REFINED = {(0, 1): 0, (0, 3): 4, (1, 0): 8, (2, 2): 12, (3, 1): 16, (3, 4): 20}


def _write_fake_vrbag(path, shape, refined):
    """
    Write a minimal HDF5 file with the `BAG_root` layout of a VR BAG: a
    `varres_metadata` grid where the cells in `refined` point to a 2x2 subgrid in
    `varres_refinements` and every other cell is marked NO_REF_INDEX.
    """
    meta = np.zeros(shape, dtype=VR_META_DTYPE)
    meta["index"] = vrb_enum.NO_REF_INDEX.value
    for (i, j), start in refined.items():
        meta[i, j] = (start, SUBGRID_DIM, SUBGRID_DIM, 1.0, 1.0, 0.0, 0.0)
    n_ref = SUBGRID_DIM * SUBGRID_DIM * len(refined)
    with h5py.File(path, "w") as f:
        root = f.create_group("BAG_root")
        root.create_dataset("varres_metadata", data=meta)
        root.create_dataset("varres_refinements", data=np.zeros((1, n_ref), dtype=VR_REF_DTYPE))


class _FakeTransformer:
    """Stands in for `Transformer`; shifts z by Z_SHIFT and records each call."""

    def __init__(self):
        self.calls = []

    def transform_points(self, x, y, z, **kwargs):
        self.calls.append(np.asarray(z).copy())
        return True, x, y, np.asarray(z) + Z_SHIFT


def test_subgrid_point_transform_handles_all_refined_subgrids(tmp_path, monkeypatch):
    # single_subgrid_point_transform() writes error.txt to the cwd on failure.
    monkeypatch.chdir(tmp_path)
    fname = tmp_path / "fake_vr.bag"
    _write_fake_vrbag(fname, shape=(4, 5), refined=REFINED)

    def fake_get_subgrid_points(fname, i, j):
        start = REFINED[(i, j)]
        n = SUBGRID_DIM * SUBGRID_DIM
        x = np.arange(n, dtype=float)
        y = np.arange(n, dtype=float)
        z = np.full(n, float(start))
        return start, x, y, z

    monkeypatch.setattr(vrbag, "get_subgrid_points", fake_get_subgrid_points)
    tf = _FakeTransformer()

    start_indices, transformed_refs = vrbag.subgrid_point_transform(str(fname), tf=tf)

    assert len(tf.calls) == len(REFINED)
    assert sorted(start_indices) == sorted(REFINED.values())
    assert len(transformed_refs) == len(start_indices)
    for start, zz in zip(start_indices, transformed_refs):
        np.testing.assert_array_equal(zz, np.full(SUBGRID_DIM * SUBGRID_DIM, start + Z_SHIFT))
    assert not (tmp_path / "error.txt").exists()
