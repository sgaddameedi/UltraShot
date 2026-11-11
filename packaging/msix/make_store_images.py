"""Renders the Store listing images Partner Center asks for into packaging/msix/store-listing:
a 300x300 app logo, a 2400x1200 hero/poster image, and a 1920x1080 "feature" banner.

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


def main():
    os.makedirs(OUT, exist_ok=True)
    logo_tile(300).save(os.path.join(OUT, "store-logo-300x300.png"))
    make_logo.banner(os.path.join(OUT, "store-poster-2400x1200.png"), 2400, 1200)
    make_logo.banner(os.path.join(OUT, "store-banner-1920x1080.png"), 1920, 1080)
    print("wrote", sorted(os.listdir(OUT)))


if __name__ == "__main__":
    main()
