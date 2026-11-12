#!/usr/bin/env python3
"""Convert an HDR screenshot (ReShade .jxl, NVIDIA/Game Bar .jxr) into an Ultra HDR
JPEG (gain map) that Instagram renders in HDR. Conversion engine of UltraShot.

Usage:
    python jxl2uhdr.py input.jxl output.jpg [--max-width 1440] [--exposure 0.0]
                       [--quality 100] [--transfer auto|scrgb|pq|hlg]

ReShade 6.7+ writes HDR screenshots as lossless JXL:
  * scRGB games -> float16, linear, BT.709 primaries, 1.0 == 80 nits
  * HDR10 games -> 16-bit PQ (or HLG), BT.2100 primaries
NVIDIA App / Windows Game Bar write JXR: float scRGB, 1.0 == 80 nits.
All are converted to linear light, optionally resized (Lanczos, in linear
light), scaled so 1.0 == 203 nits (what libultrahdr expects), and encoded with
Google's libultrahdr through the imagecodecs package.

The HDR layer is always written untouched. --exposure only changes the SDR
base image (what non-HDR screens and Instagram's preview show); the gain map
is recomputed so HDR viewers still get the original scene brightness.

Requires:  pip install imagecodecs numpy pillow
"""
import argparse
import math
import sys

import numpy as np
import imagecodecs as ic
from PIL import Image

SDR_WHITE_NITS = 203.0  # libultrahdr: linear 1.0 == 203 nits
SCRGB_WHITE_NITS = 80.0  # scRGB: linear 1.0 == 80 nits

XMP_NS = b"http://ns.adobe.com/xap/1.0/\x00"

# linear BT.2020 -> linear BT.709
M_2020_TO_709 = np.array([[1.6605, -0.5876, -0.0728],
                          [-0.1246, 1.1329, -0.0083],
                          [-0.0182, -0.1006, 1.1187]], dtype=np.float32)
LUMA_2020 = np.array([0.2627, 0.6780, 0.0593], dtype=np.float32)
LUMA_709 = np.array([0.2126, 0.7152, 0.0722], dtype=np.float32)


def insert_app1_xmp(jpeg, xmp):
    """Insert an APP1 XMP segment right after the SOI marker."""
    payload = XMP_NS + xmp.encode("utf-8")
    seg = b"\xff\xe1" + (len(payload) + 2).to_bytes(2, "big") + payload
    assert jpeg[:2] == b"\xff\xd8"
    return jpeg[:2] + seg + jpeg[2:]


def gainmap_xmp(meta):
    """Adobe/Android 'hdrgm' XMP for the gain map image (same values libultrahdr writes)."""
    l2 = lambda v: math.log2(v)
    return (
        '<x:xmpmeta xmlns:x="adobe:ns:meta/" x:xmptk="Adobe XMP Core 5.1.2">'
        '<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">'
        '<rdf:Description rdf:about="" xmlns:hdrgm="http://ns.adobe.com/hdr-gain-map/1.0/" '
        'hdrgm:Version="1.0" '
        f'hdrgm:GainMapMin="{l2(meta["min_content_boost"][0]):.6f}" '
        f'hdrgm:GainMapMax="{l2(meta["max_content_boost"][0]):.6f}" '
        f'hdrgm:Gamma="{meta["gamma"][0]:.6f}" '
        f'hdrgm:OffsetSDR="{meta["offset_sdr"][0]:.6f}" '
        f'hdrgm:OffsetHDR="{meta["offset_hdr"][0]:.6f}" '
        f'hdrgm:HDRCapacityMin="{l2(meta["hdr_capacity_min"]):.6f}" '
        f'hdrgm:HDRCapacityMax="{l2(meta["hdr_capacity_max"]):.6f}" '
        'hdrgm:BaseRenditionIsHDR="False"/>'
        '</rdf:RDF></x:xmpmeta>'
    )


def primary_xmp(gainmap_length):
    """Container directory XMP for the primary image."""
    return (
        '<x:xmpmeta xmlns:x="adobe:ns:meta/" x:xmptk="Adobe XMP Core 5.1.2">'
        '<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">'
        '<rdf:Description rdf:about="" '
        'xmlns:Container="http://ns.google.com/photos/1.0/container/" '
        'xmlns:Item="http://ns.google.com/photos/1.0/container/item/" '
        'xmlns:hdrgm="http://ns.adobe.com/hdr-gain-map/1.0/" hdrgm:Version="1.0">'
        '<Container:Directory><rdf:Seq>'
        '<rdf:li rdf:parseType="Resource">'
        '<Container:Item Item:Semantic="Primary" Item:Mime="image/jpeg"/></rdf:li>'
        '<rdf:li rdf:parseType="Resource">'
        f'<Container:Item Item:Semantic="GainMap" Item:Mime="image/jpeg" Item:Length="{gainmap_length}"/>'
        '</rdf:li></rdf:Seq></Container:Directory>'
        '</rdf:Description></rdf:RDF></x:xmpmeta>'
    )


def add_xmp_signaling(uhdr, gamut):
    """libultrahdr 2.x writes only ISO 21496-1 metadata. Older readers (Android 14,
    some apps) look for the XMP 'hdrgm' form, so add that too. The primary XMP is
    inserted before the MPF segment, which keeps the MPF offsets valid."""
    base, gm, meta = ic.ultrahdr_decode_jpeg(uhdr)
    gm = insert_app1_xmp(gm, gainmap_xmp(meta))
    merged = ic.ultrahdr_encode_jpeg(base, gm, gamut=gamut, **meta)
    # the merge adds its own ISO segment to the gain map, so measure the final length
    _, gm_final, _ = ic.ultrahdr_decode_jpeg(merged)
    return insert_app1_xmp(merged, primary_xmp(len(gm_final)))


def pq_to_nits(v):
    """SMPTE ST 2084 EOTF. v in [0,1] -> nits (0..10000)."""
    m1, m2 = 2610 / 16384, 2523 / 4096 * 128
    c1, c2, c3 = 3424 / 4096, 2413 / 4096 * 32, 2392 / 4096 * 32
    v = np.clip(v, 0.0, 1.0).astype(np.float64)
    p = np.power(v, 1.0 / m2)
    num = np.maximum(p - c1, 0.0)
    den = c2 - c3 * p
    return 10000.0 * np.power(num / den, 1.0 / m1)


def nits_to_pq(nits):
    """Inverse SMPTE ST 2084: nits (0..10000) -> PQ code value in [0,1]."""
    m1, m2 = 2610 / 16384, 2523 / 4096 * 128
    c1, c2, c3 = 3424 / 4096, 2413 / 4096 * 32, 2392 / 4096 * 32
    y = np.clip(np.asarray(nits, dtype=np.float64) / 10000.0, 0.0, 1.0)
    p = np.power(y, m1)
    return np.power((c1 + c2 * p) / (1.0 + c3 * p), m2)


def hlg_to_nits(v, peak=1000.0):
    """BT.2100 HLG inverse OETF + OOTF (gamma 1.2, 1000-nit display)."""
    a, b, c = 0.17883277, 0.28466892, 0.55991073
    v = np.clip(v, 0.0, 1.0).astype(np.float64)
    scene = np.where(v <= 0.5, (v * v) / 3.0, (np.exp((v - c) / a) + b) / 12.0)
    y = 0.2627 * scene[..., 0] + 0.6780 * scene[..., 1] + 0.0593 * scene[..., 2]
    return peak * scene * np.power(np.maximum(y, 1e-9), 0.2)[..., None]


def crop_aspect(rgb, aspect, cx, cy):
    """Crop to aspect 'W:H'. cx, cy in 0..100 choose which part of the frame
    to keep (50,50 = centre; 0,0 = top-left; 100,100 = bottom-right)."""
    aw, ah = (float(v) for v in aspect.split(":"))
    h, w = rgb.shape[:2]
    target = aw / ah
    if w / h > target:
        nw, nh = int(round(h * target)), h
    else:
        nw, nh = w, int(round(w / target))
    x0 = int(round((w - nw) * cx / 100.0))
    y0 = int(round((h - nh) * cy / 100.0))
    return rgb[y0:y0 + nh, x0:x0 + nw]


def resize_linear(rgb, max_width):
    h, w = rgb.shape[:2]
    if w <= max_width:
        return rgb
    nh = round(h * max_width / w)
    out = np.empty((nh, max_width, 3), dtype=np.float32)
    for c in range(3):
        im = Image.fromarray(rgb[..., c].astype(np.float32), mode="F")
        out[..., c] = np.asarray(im.resize((max_width, nh), Image.LANCZOS))
    return np.maximum(out, 0.0)


def srgb_oetf(x):
    x = np.clip(x, 0.0, 1.0)
    return np.where(x <= 0.0031308, 12.92 * x, 1.055 * np.power(x, 1 / 2.4) - 0.055)


def make_sdr(nits, gamut, exposure, knee):
    """Tone-map linear nits to an 8-bit sRGB base image.

    exposure: stops applied to the SDR only. knee: luminance (1.0 == 203 nits)
    where the highlight roll-off starts; everything below is left untouched.
    """
    if gamut == ic.ULTRAHDR.CG.BT_2100:
        rgb = nits @ M_2020_TO_709.T
    else:
        rgb = nits.astype(np.float32)
    rgb = np.maximum(rgb, 0.0) * (2.0 ** exposure / SDR_WHITE_NITS)

    y = rgb @ LUMA_709
    # soft shoulder: identity below knee, rational roll-off toward 1.0 above
    # (keeps some separation between 300-nit and 1000-nit highlights)
    over = np.maximum(y - knee, 0.0)
    y_out = np.where(y > knee, knee + (1.0 - knee) * over / (over + (1.0 - knee)), y)
    gain = np.where(y > 1e-6, y_out / np.maximum(y, 1e-6), 1.0)
    rgb = rgb * gain[..., None]

    # pull saturated colours toward their luminance instead of clipping a channel
    mx = rgb.max(axis=2)
    need = mx > 1.0
    if need.any():
        t = np.where(need, (1.0 - y_out) / np.maximum(mx - y_out, 1e-6), 1.0)
        rgb = y_out[..., None] + (rgb - y_out[..., None]) * t[..., None]

    out = np.empty(rgb.shape[:2] + (4,), dtype=np.uint8)
    out[..., :3] = np.round(srgb_oetf(rgb) * 255.0).astype(np.uint8)
    out[..., 3] = 255
    return out


def load_hdr(path, transfer="auto", log=print, info=None):
    """Decode an HDR screenshot to linear nits (float32 HxWx3). Returns (nits, gamut).
    If `info` is a dict it is filled with what the container held: format, dtype, bits, transfer,
    primaries.

    JPEG XL (ReShade): float16 scRGB or 16-bit PQ/HLG.
    JPEG XR (NVIDIA App, Windows Game Bar, Xbox): float16/float32 scRGB, 1.0 == 80 nits.
    """
    with open(path, "rb") as f:
        data = f.read()
    if ic.jpegxl_check(data):
        img = ic.jpegxl_decode(data)
        fmt = "JPEG XL"
    elif ic.jpegxr_check(data):
        img = ic.jpegxr_decode(data)
        fmt = "JPEG XR"
    else:
        raise ValueError("input is not a JPEG XL or JPEG XR file")
    if img.ndim != 3 or img.shape[2] not in (3, 4):
        raise ValueError(f"unexpected image shape {img.shape}; need RGB or RGBA")
    rgb = img[..., :3]

    if transfer == "auto":
        if np.issubdtype(rgb.dtype, np.floating):
            transfer = "scrgb"
        elif rgb.dtype == np.uint16:
            transfer = "pq"
        else:
            raise ValueError(f"{rgb.dtype} input looks like an SDR screenshot, not HDR. "
                             "Make sure the game ran in HDR and ReShade saved an HDR JXL.")

    if transfer == "scrgb":
        nits = rgb.astype(np.float32) * SCRGB_WHITE_NITS
        gamut = ic.ULTRAHDR.CG.BT_709
    else:
        if rgb.dtype == np.uint16:
            codes = rgb.astype(np.float32) / 65535.0
        elif np.issubdtype(rgb.dtype, np.floating):
            codes = rgb.astype(np.float32)
        else:
            codes = rgb.astype(np.float32) / np.iinfo(rgb.dtype).max
        nits = (pq_to_nits(codes) if transfer == "pq" else hlg_to_nits(codes)).astype(np.float32)
        gamut = ic.ULTRAHDR.CG.BT_2100

    nits = np.maximum(nits, 0.0)  # HDR layer: never exposure-adjusted
    log(f"{path}: {rgb.shape[1]}x{rgb.shape[0]} {rgb.dtype} as {transfer}; "
        f"peak {nits.max():.0f} nits, mean {nits.mean():.1f} nits")
    if info is not None:
        bits = rgb.dtype.itemsize * 8
        info.update(format=fmt, dtype=str(rgb.dtype), bits=bits, channels=img.shape[2],
                    pixel_type=(f"{bits}-bit float, linear scRGB (1.0 = 80 nits)" if transfer == "scrgb"
                                else f"{bits}-bit integer, {transfer.upper()} code values"),
                    transfer={"scrgb": "linear (scRGB)", "pq": "PQ (SMPTE ST 2084)", "hlg": "HLG (BT.2100)"}[transfer],
                    primaries="BT.709 / sRGB" if gamut == ic.ULTRAHDR.CG.BT_709 else "BT.2020 / BT.2100")
    return nits, gamut


def limit_peak(nits, gamut, limit, log=print):
    """Opt-in soft limit of the HDR layer's luminance to `limit` nits.

    Captures from scRGB games can carry highlights far above what the display showed (3000-nit
    suns on a 1000-nit monitor), and an HDR phone will reproduce them in full. A rational shoulder
    starting at 75 % of the limit compresses the brightest channel toward the limit, hue-preserving,
    so the result matches what the game looked like on a display of that peak. Off by default:
    this is the one place the HDR data is deliberately altered."""
    # the brightest channel, not luminance: a saturated highlight (a red sun, a blue lantern) must be
    # limited too, as a real display would clip it; all channels are scaled equally so hue is kept
    y = nits.max(axis=2)
    k = 0.75 * limit
    over = np.maximum(y - k, 0.0)
    y_out = np.where(y > k, k + (limit - k) * over / (over + (limit - k)), y)
    gain = np.where(y > 1e-6, y_out / np.maximum(y, 1e-6), 1.0).astype(np.float32)
    affected = float((y > k).mean() * 100.0)
    log(f"HDR peak limited to {limit:.0f} nits (roll-off from {k:.0f}); {affected:.2f}% of pixels affected, "
        f"source peak {nits.max():.0f} nits")
    return nits * gain[..., None]


# ----------------------------------------------------------------------------- polish
# Per-capture adjustments, applied in linear light before the SDR base is rendered and the gain
# map is encoded, so the source is untouched and nothing is rounded until the final JPEG. They are
# built so the HDR survives them: the contrast and shadow curves fade out above SDR white and
# leave the highlights exactly as captured, warmth and vibrance move colours around their own
# luminance without changing it, the watermark sits at SDR white, and the result is never allowed
# above the capture's own peak or below black.
GRADE_DEFAULTS = dict(warmth=0, contrast=0, vibrance=0, shadows=0, watermark="")


def _smoothstep(x, lo, hi):
    t = np.clip((x - lo) / (hi - lo), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def grade_is_default(grade):
    g = grade or {}
    return all(not g.get(k) for k in ("warmth", "contrast", "vibrance", "shadows")) and not str(g.get("watermark") or "").strip()


def _watermark(out, text):
    """Draw `text` in the bottom-right corner at SDR white with a soft shadow, sized to the width."""
    from PIL import ImageDraw, ImageFilter, ImageFont
    h, w = out.shape[:2]
    size, margin = max(12, int(w * 0.022)), int(w * 0.016)
    try:
        font = ImageFont.truetype(r"C:\Windows\Fonts\segoeuib.ttf", size)
    except OSError:
        font = ImageFont.load_default()
    mask = Image.new("L", (w, h), 0)
    d = ImageDraw.Draw(mask)
    bb = d.textbbox((0, 0), text, font=font)
    x, y = w - margin - (bb[2] - bb[0]) - bb[0], h - margin - (bb[3] - bb[1]) - bb[1]
    shadow = Image.new("L", (w, h), 0)
    ImageDraw.Draw(shadow).text((x + size * 0.06, y + size * 0.06), text, font=font, fill=255)
    shadow = shadow.filter(ImageFilter.GaussianBlur(max(1.0, size * 0.08)))
    d.text((x, y), text, font=font, fill=255)
    a = np.asarray(mask, np.float32)[..., None] / 255.0 * 0.85
    s = np.asarray(shadow, np.float32)[..., None] / 255.0 * 0.6
    out = out * (1.0 - s)
    return out * (1.0 - a) + SDR_WHITE_NITS * a


def apply_grade(nits, gamut, grade):
    """Apply the per-capture polish to linear nits. Returns the input untouched when nothing is set."""
    if grade_is_default(grade):
        return nits
    g = dict(GRADE_DEFAULTS)
    g.update({k: v for k, v in (grade or {}).items() if v is not None})
    w = LUMA_2020 if gamut == ic.ULTRAHDR.CG.BT_2100 else LUMA_709
    out = nits.astype(np.float32, copy=True)
    peak = float(out.max())
    warmth = float(g["warmth"]) / 100.0
    if warmth:
        gr, gb = 1.0 + 0.12 * warmth, 1.0 - 0.12 * warmth
        gg = (1.0 - w[0] * gr - w[2] * gb) / w[1]          # a neutral keeps its luminance
        out *= np.array([gr, gg, gb], np.float32)
    contrast, shadows = float(g["contrast"]) / 100.0, float(g["shadows"]) / 100.0
    if contrast or shadows:
        Y = np.maximum(out @ w, 1e-4)
        gain = np.ones_like(Y)
        if contrast:
            pivot = 0.18 * SDR_WHITE_NITS
            curve = pivot * (Y / pivot) ** (1.0 + 0.5 * contrast)
            protect = 1.0 - _smoothstep(Y, SDR_WHITE_NITS, 1000.0)   # highlights stay as captured
            gain *= 1.0 + (curve / Y - 1.0) * protect
        if shadows:
            reach = 1.0 - _smoothstep(Y, 0.0, 80.0)
            gain *= 1.0 + 0.7 * shadows * reach * reach
        out *= gain[..., None]
    vib = float(g["vibrance"]) / 100.0
    if vib:
        Y = (out @ w)[..., None]
        mx, mn = out.max(axis=2, keepdims=True), out.min(axis=2, keepdims=True)
        sat = np.where(mx > 1e-4, 1.0 - mn / np.maximum(mx, 1e-4), 0.0)
        amount = 0.9 * vib * (1.0 - sat) if vib > 0 else 0.9 * vib   # boosts muted colours most
        out = np.maximum(Y + (out - Y) * (1.0 + amount), 0.0)
    text = str(g.get("watermark") or "").strip()
    if text:
        out = _watermark(out, text)
    return np.clip(out, 0.0, max(peak, SDR_WHITE_NITS)).astype(np.float32)


def encode_uhdr(nits, gamut, output, *, crop="", crop_x=50.0, crop_y=50.0, max_width=0,
                exposure=0.0, knee=0.6, auto_sdr=False, quality=100, peak_nits=0.0,
                limit_nits=0.0, log=print):
    """Crop/resize linear nits and write an Ultra HDR JPEG. Returns the bytes written."""
    if crop:
        nits = crop_aspect(nits, crop, crop_x, crop_y)
        log(f"cropped to {nits.shape[1]}x{nits.shape[0]} ({crop})")
    if limit_nits and limit_nits > 0:
        nits = limit_peak(nits, gamut, float(limit_nits), log)
    if max_width:
        nits = resize_linear(nits, max_width)
        log(f"resized to {nits.shape[1]}x{nits.shape[0]}")

    lin = nits / SDR_WHITE_NITS
    rgba = np.empty(lin.shape[:2] + (4,), dtype=np.float16)
    rgba[..., :3] = lin
    rgba[..., 3] = 1.0

    kw = dict(level=quality, gainmap_level=quality,
              transfer=ic.ULTRAHDR.CT.LINEAR, gamut=gamut, scale=1,
              usage=ic.ULTRAHDR.USAGE.QUALITY, multichannel=True,
              codec=ic.ULTRAHDR.CODEC.JPEG)
    content_peak = float(nits.max())
    auto_peak = not peak_nits
    if auto_peak:
        peak_nits = min(max(math.ceil(content_peak), 250.0), 10000.0)
    kw["nits"] = float(peak_nits)
    if not auto_sdr:
        sdr = make_sdr(nits, gamut, exposure, knee)
        kw["sdr"] = sdr
        log(f"SDR base: exposure {exposure:+.2f} stops, knee {knee}, "
            f"mean level {sdr[..., :3].mean():.0f}/255")
    else:
        log("SDR base: libultrahdr automatic tone map")

    out = ic.ultrahdr_encode(rgba, **kw)
    if auto_peak:
        # libultrahdr derives HDRCapacityMax from the target peak (default 10000 nits),
        # not from the gain map's real maximum boost. When the capacity is far above
        # the boost, a phone with 4x headroom applies only ~35% of the gain map and
        # the HDR layer looks dim. Re-encode with the peak matched to the gain map so
        # it is applied in full on any display with enough headroom.
        _, _, meta = ic.ultrahdr_decode_jpeg(out)
        boost_nits = SDR_WHITE_NITS * float(max(meta["max_content_boost"]))
        if abs(boost_nits - peak_nits) > 0.02 * peak_nits:
            kw["nits"] = peak_nits = min(max(boost_nits, 250.0), 10000.0)
            out = ic.ultrahdr_encode(rgba, **kw)
    _, _, meta = ic.ultrahdr_decode_jpeg(out)
    log(f"gain map: max boost {float(max(meta['max_content_boost'])):.2f}x "
        f"({SDR_WHITE_NITS * float(max(meta['max_content_boost'])):.0f} nits), "
        f"fully applied from {float(meta['hdr_capacity_max']):.2f}x display headroom "
        f"(target peak {peak_nits:.0f} nits)")
    out = add_xmp_signaling(out, gamut)
    import os
    tmp = f"{output}.{os.getpid()}.part"   # per-process name: two converters can't clobber each other
    with open(tmp, "wb") as f:
        f.write(out)
    os.replace(tmp, output)
    ok = ic.ultrahdr_check(out)
    log(f"wrote {output} ({len(out) / 1e6:.1f} MB), gain map present: {bool(ok)}, "
        f"ISO 21496-1: {b'urn:iso:std:iso:ts:21496' in out}, XMP hdrgm: {b'hdr-gain-map' in out}")

    # round-trip check: what an HDR viewer will reconstruct from the file
    back = ic.ultrahdr_decode(out, dtype=np.float16)[..., :3].astype(np.float32) * SDR_WHITE_NITS
    log(f"HDR layer after encode: peak {back.max():.0f} nits, mean {back.mean():.1f} nits "
        f"(source peak {nits.max():.0f}, mean {nits.mean():.1f})")
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("input")
    ap.add_argument("output")
    ap.add_argument("--crop", default="",
                    help="crop to this aspect, e.g. 4:5 (Instagram portrait), 1:1, 16:9")
    ap.add_argument("--crop-x", type=float, default=50.0,
                    help="horizontal position of the crop window, 0=left 50=centre 100=right")
    ap.add_argument("--crop-y", type=float, default=50.0,
                    help="vertical position of the crop window, 0=top 50=centre 100=bottom")
    ap.add_argument("--max-width", type=int, default=0,
                    help="downscale so width <= this (0 = keep full size)")
    ap.add_argument("--exposure", type=float, default=0.0,
                    help="SDR base brightness in stops (+1 = twice as bright); HDR layer is unaffected")
    ap.add_argument("--knee", type=float, default=0.6,
                    help="SDR highlight roll-off start, 1.0 == 203 nits (default 0.6; lower = more highlight detail, flatter look)")
    ap.add_argument("--auto-sdr", action="store_true",
                    help="let libultrahdr tone-map the SDR base itself (ignores --exposure/--knee)")
    ap.add_argument("--quality", type=int, default=100,
                    help="JPEG quality of the SDR base and the gain map (0-100)")
    ap.add_argument("--transfer", choices=["auto", "scrgb", "pq", "hlg"],
                    default="auto", help="what the JXL contains (auto: float=scRGB, 16-bit=PQ)")
    ap.add_argument("--peak-nits", type=float, default=0.0,
                    help="target display peak in nits for the gain map, 250-10000 "
                         "(0 = match the gain map's own maximum, recommended)")
    ap.add_argument("--limit-nits", type=float, default=0.0,
                    help="soft-limit the HDR layer to this peak in nits, e.g. your monitor's 1000, "
                         "so phones match what the game showed (0 = keep the capture's full range)")
    args = ap.parse_args()

    try:
        nits, gamut = load_hdr(args.input, args.transfer)
    except ValueError as e:
        sys.exit(str(e))
    encode_uhdr(nits, gamut, args.output, crop=args.crop, crop_x=args.crop_x, crop_y=args.crop_y,
                max_width=args.max_width, exposure=args.exposure, knee=args.knee,
                auto_sdr=args.auto_sdr, quality=args.quality, peak_nits=args.peak_nits,
                limit_nits=args.limit_nits)


if __name__ == "__main__":
    main()
