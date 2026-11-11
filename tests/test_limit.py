"""The optional HDR peak limit must cap highlights smoothly and leave everything below the knee alone."""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import jxl2uhdr as E  # noqa: E402

ic = E.ic


def ramp(peak, w=1024, h=16):
    r = np.linspace(0.0, 1.0, w, dtype=np.float32)[None, :, None].repeat(h, 0)
    return np.repeat(r, 3, axis=2) * peak


def test_limit_caps_peak_and_keeps_shadows():
    n = ramp(3000.0)
    out = E.limit_peak(n, ic.ULTRAHDR.CG.BT_709, 1000.0, log=lambda m: None)
    lum = out @ E.LUMA_709
    assert lum.max() <= 1000.0 * 1.001
    assert lum.max() > 950.0                     # approaches the limit, not far below it
    below = (n @ E.LUMA_709) <= 740.0            # under the 75 % knee: untouched
    assert np.allclose(out[below], n[below])
    assert np.all(np.diff(lum[0]) >= -1e-3)      # still monotonic across the ramp


def test_limit_is_hue_preserving_and_caps_saturated_highlights():
    px = np.array([[[2500.0, 500.0, 100.0]]], np.float32)   # red highlight: luminance ~ 900, red channel 2500
    out = E.limit_peak(px, ic.ULTRAHDR.CG.BT_709, 1000.0, log=lambda m: None)[0, 0]
    ratio = out / px[0, 0]
    assert np.allclose(ratio, ratio[0])          # all channels scaled equally
    assert out.max() <= 1000.0 * 1.001           # the brightest channel is what gets limited


def test_encode_with_limit(tmp_path):
    data = E.encode_uhdr(ramp(3000.0), ic.ULTRAHDR.CG.BT_709, str(tmp_path / "lim.jpg"),
                         limit_nits=1000.0, log=lambda m: None)
    back = ic.ultrahdr_decode(data, dtype=np.float16)[..., :3].astype(np.float32) * E.SDR_WHITE_NITS
    assert back.max() < 1060.0
