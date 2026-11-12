"""The polish adjustments must never disrupt the HDR: highlights above SDR white keep their
values under contrast and shadows, no pixel goes above the capture's own peak or below black,
defaults are a no-op, and the watermark only touches its corner."""
import numpy as np
import pytest

import jxl2uhdr as E

G = E.ic.ULTRAHDR.CG.BT_709


def scene():
    rng = np.random.default_rng(1)
    base = rng.uniform(0.5, 180.0, size=(48, 64, 3)).astype(np.float32)
    base[8:16, 8:24] = [2500.0, 2300.0, 2100.0]      # a bright sun
    base[30:40, 40:60] = [600.0, 650.0, 700.0]       # bright sky
    return base


def test_defaults_are_a_no_op():
    s = scene()
    assert E.apply_grade(s, G, dict(E.GRADE_DEFAULTS)) is s
    assert E.apply_grade(s, G, None) is s


@pytest.mark.parametrize("key", ["contrast", "shadows"])
@pytest.mark.parametrize("value", [-100, -40, 40, 100])
def test_curves_leave_highlights_alone(key, value):
    s = scene()
    out = E.apply_grade(s, G, {key: value})
    bright = (s @ E.LUMA_709) >= 1000.0
    np.testing.assert_allclose(out[bright], s[bright], rtol=1e-5)
    assert float(out.max()) <= float(s.max()) + 1e-3
    assert float(out.min()) >= 0.0
    assert np.isfinite(out).all()


@pytest.mark.parametrize("key", ["warmth", "vibrance"])
@pytest.mark.parametrize("value", [-100, 60, 100])
def test_colour_moves_keep_luminance_and_peak(key, value):
    s = scene()
    out = E.apply_grade(s, G, {key: value})
    assert float(out.max()) <= float(s.max()) + 1e-3
    assert float(out.min()) >= 0.0
    mid = (s @ E.LUMA_709) < 150.0
    y0, y1 = s[mid] @ E.LUMA_709, out[mid] @ E.LUMA_709
    # luminance of the mid-tones changes by less than 3 % for a neutral-preserving move
    assert np.median(np.abs(y1 - y0) / np.maximum(y0, 1e-3)) < 0.03


def test_contrast_changes_midtones():
    s = scene()
    out = E.apply_grade(s, G, {"contrast": 80})
    mid = ((s @ E.LUMA_709) > 60) & ((s @ E.LUMA_709) < 150)
    assert float((out[mid] @ E.LUMA_709).mean()) > float((s[mid] @ E.LUMA_709).mean())


def test_watermark_touches_only_its_corner_and_sits_at_sdr_white():
    s = scene()
    out = E.apply_grade(s, G, {"watermark": "@ultrashot"})
    h, w = s.shape[:2]
    np.testing.assert_array_equal(out[: h // 2, : w // 2], s[: h // 2, : w // 2])
    assert float(out.max()) <= float(s.max()) + 1e-3
    changed = np.any(out != s, axis=2)
    assert changed.any() and changed[: h // 2].sum() == 0
    assert float(out[changed].max()) <= max(float(s[changed].max()), E.SDR_WHITE_NITS) + 1e-3
