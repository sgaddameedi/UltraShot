"""Creates the small sample files in examples/ from a real capture.

    python tools/make_samples.py "path\\to\\capture.jxl" [width]

Writes examples/sample-hdr10.jxl (lossless JPEG XL, downscaled so the repo stays small) and
examples/sample-ultrahdr.jpg (what UltraShot makes of it, Instagram size). Open the .jpg in
Chrome or Edge on an HDR display to see the gain map in action.
"""
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import jxl2uhdr as E  # noqa: E402

ic = E.ic


def main():
    src = sys.argv[1]
    width = int(sys.argv[2]) if len(sys.argv) > 2 else 1280
    out_dir = os.path.join(ROOT, "examples")
    os.makedirs(out_dir, exist_ok=True)

    nits, gamut = E.load_hdr(src)
    small = E.resize_linear(nits, width)
    if gamut == ic.ULTRAHDR.CG.BT_2100:
        # back to PQ 16-bit so the sample looks exactly like an HDR10 capture
        codes = E.nits_to_pq(small)
        img = np.round(np.clip(codes, 0, 1) * 65535).astype(np.uint16)
        name = "sample-hdr10.jxl"
    else:
        img = (small / E.SCRGB_WHITE_NITS).astype(np.float16)
        name = "sample-scrgb.jxl"
    jxl = os.path.join(out_dir, name)
    with open(jxl, "wb") as f:
        f.write(ic.jpegxl_encode(img, lossless=True, effort=7))
    print("wrote", jxl, os.path.getsize(jxl) // 1024, "KB")

    E.encode_uhdr(small, gamut, os.path.join(out_dir, "sample-ultrahdr.jpg"), max_width=width)


if __name__ == "__main__":
    main()
