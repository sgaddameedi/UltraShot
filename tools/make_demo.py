"""Builds the assets behind the interactive demo on the landing page (docs/demo/).

For every Ultra HDR JPEG in examples/gallery it writes:
  <name>-heat.jpg   a 1920-wide highlights map, the same rendering the app's inspector shows:
                    the SDR base dimmed, orange where the scene exceeds SDR white (203 nits),
                    pink where it exceeds 600 nits
  <name>-lum.png    a 640-wide 8-bit luminance map in PQ code values, so the page can report the
                    brightness under the pointer in nits (the page inverts the PQ curve)
  <name>-thumb.jpg  a 320-wide SDR thumbnail for the picker strip
and docs/demo/meta.json with everything the app's File details panel would list, read back from
the gallery file itself, plus the captions used on the page.

    python tools/make_demo.py
"""
import json
import os
import sys

import numpy as np
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import jxl2uhdr  # noqa: E402
import ultrashot as U  # noqa: E402

GALLERY = os.path.join(ROOT, "examples", "gallery")
OUT = os.path.join(ROOT, "docs", "demo")
RAW = "https://raw.githubusercontent.com/sgaddameedi/UltraShot/main/examples/gallery/"

# Display order, title, game, capture tool. The first entry opens by default.
PICTURES = [
    ("phantom-blade-zero-lake-sunset", "Sunset over the lake", "Phantom Blade Zero", "Windows Game Bar"),
    ("phantom-blade-zero-sunset-figures", "Figures against the sunset", "Phantom Blade Zero", "ReShade"),
    ("phantom-blade-zero-lantern-stairs", "Lantern stairs", "Phantom Blade Zero", "ReShade"),
    ("phantom-blade-zero-mountain-village", "Mountain village", "Phantom Blade Zero", "ReShade"),
    ("phantom-blade-zero-village-dusk", "Village at dusk", "Phantom Blade Zero", "ReShade"),
    ("phantom-blade-zero-lion-dance", "Lion dance", "Phantom Blade Zero", "ReShade"),
    ("phantom-blade-zero-golden-field", "Golden field", "Phantom Blade Zero", "ReShade"),
    ("crimson-desert-red-sunset", "Red sunset over the mountains", "Crimson Desert", "NVIDIA App"),
    ("crimson-desert-storm-sky", "Storm sky over the tower", "Crimson Desert", "NVIDIA App"),
]


def heat_map(base_rgb, lum, width):
    """The inspector's highlights map, at a reduced width."""
    rgbf = base_rgb.astype(np.float32) * 0.45
    over = (lum > jxl2uhdr.SDR_WHITE_NITS)[..., None]
    hot = (lum > 600.0)[..., None]
    rgbf = np.where(over, rgbf * 0.5 + np.array([255, 150, 20], np.float32) * 0.6, rgbf)
    rgbf = np.where(hot, rgbf * 0.3 + np.array([255, 60, 220], np.float32) * 0.8, rgbf)
    im = Image.fromarray(np.clip(rgbf, 0, 255).astype(np.uint8), "RGB")
    return im.resize((width, round(im.height * width / im.width)), Image.LANCZOS)


def main():
    os.makedirs(OUT, exist_ok=True)
    entries = []
    for stem, title, game, tool in PICTURES:
        path = os.path.join(GALLERY, stem + ".jpg")
        print("reading", stem)
        info = U.inspect_ultrahdr(path)
        data = open(path, "rb").read()
        base_bytes, _, _ = U.ic.ultrahdr_decode_jpeg(data)
        base = np.asarray(Image.open(__import__("io").BytesIO(base_bytes)).convert("RGB"))
        hdr = U.ic.ultrahdr_decode(data, dtype=np.float16)[..., :3].astype(np.float32) * U.SDR_WHITE_NITS
        lum = hdr @ jxl2uhdr.LUMA_709
        heat_map(base, lum, 1920).save(os.path.join(OUT, stem + "-heat.jpg"), quality=84, optimize=True)
        Image.fromarray(base, "RGB").resize((320, round(base.shape[0] * 320 / base.shape[1])), Image.LANCZOS) \
            .save(os.path.join(OUT, stem + "-thumb.jpg"), quality=80, optimize=True)
        pq = np.clip(jxl2uhdr.nits_to_pq(np.maximum(lum, 0.0)), 0, 1)
        lum_im = Image.fromarray((pq * 255.0 + 0.5).astype(np.uint8), "L")
        lum_im.resize((640, round(lum_im.height * 640 / lum_im.width)), Image.BOX).save(os.path.join(OUT, stem + "-lum.png"), optimize=True)
        h = info["hdr"]
        entries.append({
            "id": stem, "title": title, "game": game, "tool": tool,
            "file": RAW + stem + ".jpg", "heat": "demo/" + stem + "-heat.jpg", "lum": "demo/" + stem + "-lum.png",
            "thumb": "demo/" + stem + "-thumb.jpg",
            "width": info["base"]["width"], "height": info["base"]["height"], "size_bytes": info["file"]["size_bytes"],
            "signalling": info["signalling"], "base": info["base"], "gainmap": info["gainmap"],
            "metadata": info["metadata"],
            "hdr": {k: round(float(v), 3) for k, v in h.items()},
        })
        print(f"  {info['base']['width']}x{info['base']['height']}  peak {h['peak_nits']:.0f} nits  "
              f"{h['above_sdr_percent']:.1f}% above SDR white")
    with open(os.path.join(OUT, "meta.json"), "w", encoding="utf-8") as fh:
        json.dump(entries, fh, indent=1)
    print("wrote", len(entries), "entries to", OUT)


if __name__ == "__main__":
    main()
