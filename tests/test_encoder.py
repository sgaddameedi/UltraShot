"""Engine tests: synthetic HDR data in, Ultra HDR JPEG out, no GUI and no sample files needed."""
import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import jxl2uhdr as E  # noqa: E402

ic = E.ic


def ramp(peak_nits, w=512, h=64):
    """Horizontal gray ramp from 0 to peak_nits, float32 HxWx3."""
    r = np.linspace(0.0, 1.0, w, dtype=np.float32)[None, :, None].repeat(h, 0)
    return np.repeat(r, 3, axis=2) * peak_nits


def decode_nits(data):
    return ic.ultrahdr_decode(data, dtype=np.float16)[..., :3].astype(np.float32) * E.SDR_WHITE_NITS


@pytest.mark.parametrize("peak", [400.0, 1000.0, 4000.0])
def test_hdr_layer_round_trips(tmp_path, peak):
    out = tmp_path / "ramp.jpg"
    data = E.encode_uhdr(ramp(peak), ic.ULTRAHDR.CG.BT_709, str(out), log=lambda m: None)
    assert out.exists() and ic.ultrahdr_check(data)
    back = decode_nits(data)
    assert abs(back.max() - peak) / peak < 0.03, "HDR peak must survive the gain map"
    # the brightest column should be close to the source across the ramp, not clipped
    col = back[:, :, 0].mean(axis=0)
    for frac in (0.25, 0.5, 0.75, 1.0):
        i = int(col.size * frac) - 1
        assert abs(col[i] - peak * frac) / peak < 0.03


def test_capacity_matches_gain_map(tmp_path):
    """libultrahdr's default HDRCapacityMax (10000 nits) would make phones apply only part of the
    gain map. The encoder must match the capacity to the real maximum boost."""
    data = E.encode_uhdr(ramp(800.0), ic.ULTRAHDR.CG.BT_709, str(tmp_path / "cap.jpg"), log=lambda m: None)
    _, _, meta = ic.ultrahdr_decode_jpeg(data)
    boost = float(max(meta["max_content_boost"]))
    cap = float(meta["hdr_capacity_max"])
    assert abs(cap - boost) / boost < 0.05


def test_signalling_present(tmp_path):
    data = E.encode_uhdr(ramp(600.0), ic.ULTRAHDR.CG.BT_709, str(tmp_path / "sig.jpg"), log=lambda m: None)
    assert b"urn:iso:std:iso:ts:21496" in data, "ISO 21496-1 gain map metadata"
    assert b"hdr-gain-map" in data, "Adobe/Android XMP gain map metadata"
    assert data.count(b"\xff\xd8") >= 2, "primary + gain map JPEGs"


def test_sdr_base_respects_exposure():
    n = ramp(120.0)   # below the knee, so exposure acts linearly
    dark = E.make_sdr(n, ic.ULTRAHDR.CG.BT_709, 0.0, 0.6)[..., :3].astype(np.float32).mean()
    bright = E.make_sdr(n, ic.ULTRAHDR.CG.BT_709, 1.0, 0.6)[..., :3].astype(np.float32).mean()
    assert bright > dark * 1.2
    assert E.make_sdr(n, ic.ULTRAHDR.CG.BT_709, 0.0, 0.6).dtype == np.uint8


def test_crop_aspect_positions():
    img = np.zeros((1080, 1920, 3), np.float32)
    c = E.crop_aspect(img, "4:5", 50, 50)
    assert c.shape[0] == 1080 and abs(c.shape[1] / c.shape[0] - 0.8) < 0.01
    left = E.crop_aspect(np.arange(1920, dtype=np.float32)[None, :, None].repeat(1080, 0).repeat(3, 2), "1:1", 0, 50)
    assert left[0, 0, 0] == 0.0
    right = E.crop_aspect(np.arange(1920, dtype=np.float32)[None, :, None].repeat(1080, 0).repeat(3, 2), "1:1", 100, 50)
    assert right[0, -1, 0] == 1919.0


def test_pq_decode_reference_points():
    codes = np.array([[[0.0, 0.0, 0.0], [0.5081, 0.5081, 0.5081], [1.0, 1.0, 1.0]]], np.float32)
    nits = E.pq_to_nits(codes)
    assert abs(nits[0, 1, 0] - 100.0) < 1.0      # PQ 0.5081 ≈ 100 nits
    assert abs(nits[0, 2, 0] - 10000.0) < 1.0
