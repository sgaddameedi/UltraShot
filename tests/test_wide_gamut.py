"""scRGB captures with colours outside BT.709 (HDR10 content through OBS or a capture card) must
keep those colours: the decoder moves them to BT.2020 instead of clamping negative channels."""
import numpy as np
import imagecodecs as ic

import jxl2uhdr as E


def scrgb_jxl(path, rgb):
    """Write a float16 scRGB JPEG XL, which is what load_hdr sees from OBS and the NVIDIA App."""
    open(path, "wb").write(ic.jpegxl_encode(rgb.astype(np.float16), distance=0.0, effort=3))


def test_wide_gamut_scrgb_is_kept(tmp_path):
    # a saturated BT.2020 red: in BT.709 terms its green and blue are negative
    red_2020 = np.array([1.0, 0.0, 0.0], np.float32) * 4.0          # 4.0 == 320 nits in scRGB units
    red_709 = red_2020 @ E.M_2020_TO_709.T
    assert red_709[1] < 0 and red_709[2] < 0
    img = np.full((32, 32, 3), 0.25, np.float32)
    img[8:24, 8:24] = red_709
    p = tmp_path / "wide.jxl"; scrgb_jxl(str(p), img)
    nits, gamut = E.load_hdr(str(p), "auto", log=lambda m: None)
    assert gamut == E.ic.ULTRAHDR.CG.BT_2100
    # the patch comes back as the same BT.2020 red, not a clipped BT.709 one
    got = nits[16, 16] / E.SCRGB_WHITE_NITS
    np.testing.assert_allclose(got, red_2020, atol=0.02)
    back_709 = got @ E.M_2020_TO_709.T
    assert back_709[1] < -0.3 and back_709[2] < -0.03       # the negatives are still there


def test_plain_scrgb_stays_bt709(tmp_path):
    img = np.random.default_rng(3).uniform(0.0, 2.0, size=(16, 16, 3)).astype(np.float32)
    p = tmp_path / "plain.jxl"; scrgb_jxl(str(p), img)
    nits, gamut = E.load_hdr(str(p), "auto", log=lambda m: None)
    assert gamut == E.ic.ULTRAHDR.CG.BT_709
    np.testing.assert_allclose(nits / E.SCRGB_WHITE_NITS, img, atol=0.01)


def test_wide_gamut_survives_the_ultra_hdr_file(tmp_path):
    red_2020 = np.array([1.0, 0.0, 0.0], np.float32) * 3.0
    img = np.full((64, 64, 3), 0.2, np.float32)
    img[16:48, 16:48] = red_2020 @ E.M_2020_TO_709.T
    p = tmp_path / "wide.jxl"; scrgb_jxl(str(p), img)
    nits, gamut = E.load_hdr(str(p), "auto", log=lambda m: None)
    out = tmp_path / "wide.jpg"
    E.encode_uhdr(nits, gamut, str(out), log=lambda m: None)
    data = open(out, "rb").read()
    assert ic.ultrahdr_check(data)
    # libultrahdr decodes a BT.2100 file in BT.2020 coordinates, 1.0 == SDR white
    back = ic.ultrahdr_decode(data, dtype=np.float16)[..., :3].astype(np.float32) * (E.SDR_WHITE_NITS / E.SCRGB_WHITE_NITS)
    px = back[32, 32]
    np.testing.assert_allclose(px, red_2020, atol=0.1)                 # the BT.2020 red came back as itself
    assert (px @ E.M_2020_TO_709.T)[1] < -0.2                          # which is outside BT.709
