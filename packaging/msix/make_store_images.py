"""Renders every Store listing image Partner Center can ask for into packaging/msix/store-listing:

  app tile icons 1:1      store-logo-300x300.png, -150x150, -71x71
  box art 1:1             store-box-1080x1080.png
  poster art 2:3          store-poster-720x1080.png
  poster art 9:16         store-poster-1080x1920.png
  super hero art 16:9     store-hero-3840x2160.png and store-banner-1920x1080.png
  promotional art 2:1     store-poster-2400x1200.png

    python packaging/msix/make_store_images.py
"""
import os
import sys

from PIL import Image, ImageDraw

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))
import make_icon  # noqa: E402
import make_logo  # noqa: E402

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "store-listing")


def logo_tile(size):
    img = make_logo.aurora(size, size).convert("RGBA")
    icon = make_icon.draw(int(size * 0.72))
    img.alpha_composite(icon, ((size - icon.width) // 2, (size - icon.height) // 2))
    return img.convert("RGB")


def poster(path, w, h):
    """Stacked layout for square and portrait slots: icon, name, tagline, centred."""
    img = make_logo.aurora(w, h).convert("RGBA")
    short = min(w, h)
    icon = make_icon.draw(int(short * 0.40))
    d = ImageDraw.Draw(img)
    f1 = make_logo.font(make_logo.FONT_BOLD, int(short * 0.125))
    f2 = make_logo.font(make_logo.FONT_REG, int(short * 0.046))
    f3 = make_logo.font(make_logo.FONT_REG, int(short * 0.036))
    tw = d.textbbox((0, 0), "UltraShot", font=f1)[2]
    gap = int(short * 0.06)
    block = icon.height + gap + int(short * 0.125) + int(short * 0.03) + int(short * 0.046) + int(short * 0.02) + int(short * 0.036)
    y = (h - block) // 2
    img.alpha_composite(icon, ((w - icon.width) // 2, y))
    y += icon.height + gap
    d.text(((w - tw) // 2, y), "UltraShot", font=f1, fill=(246, 243, 236))
    y += int(short * 0.125) + int(short * 0.03)
    t2 = "HDR screenshots, shared in HDR."
    d.text(((w - d.textbbox((0, 0), t2, font=f2)[2]) // 2, y), t2, font=f2, fill=(255, 193, 77))
    y += int(short * 0.046) + int(short * 0.02)
    t3 = "ReShade .jxl  ·  NVIDIA / Game Bar .jxr  →  Ultra HDR JPEG"
    d.text(((w - d.textbbox((0, 0), t3, font=f3)[2]) // 2, y), t3, font=f3, fill=(150, 142, 128))
    img.convert("RGB").save(path, optimize=True)
    print("wrote", path)


def main():
    os.makedirs(OUT, exist_ok=True)
    for s in (300, 150, 71):
        logo_tile(s).save(os.path.join(OUT, f"store-logo-{s}x{s}.png"))
    poster(os.path.join(OUT, "store-box-1080x1080.png"), 1080, 1080)
    poster(os.path.join(OUT, "store-poster-720x1080.png"), 720, 1080)
    poster(os.path.join(OUT, "store-poster-1080x1920.png"), 1080, 1920)
    make_logo.banner(os.path.join(OUT, "store-hero-3840x2160.png"), 3840, 2160)
    make_logo.banner(os.path.join(OUT, "store-banner-1920x1080.png"), 1920, 1080)
    make_logo.banner(os.path.join(OUT, "store-poster-2400x1200.png"), 2400, 1200)
    print("wrote", sorted(os.listdir(OUT)))


if __name__ == "__main__":
    main()
