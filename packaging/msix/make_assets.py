"""Renders the Store / MSIX logo assets into packaging/msix/Assets from the app icon drawing.

    python packaging/msix/make_assets.py

Square tiles get the icon on a transparent background (Windows draws the tile colour);
target-size icons (taskbar, Start, file associations) are the plain icon.
"""
import os
import sys

from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
import make_icon  # noqa: E402

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Assets")


def tile(w, h, icon_frac=0.5):
    """Icon centred on a transparent canvas (tile backgrounds come from the OS)."""
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    size = int(min(w, h) * icon_frac)
    icon = make_icon.draw(size)
    img.alpha_composite(icon, ((w - size) // 2, (h - size) // 2))
    return img


def main():
    os.makedirs(OUT, exist_ok=True)
    plan = {
        # name: (width, height, icon fraction)
        "Square44x44Logo.png": (44, 44, 1.0), "Square44x44Logo.scale-200.png": (88, 88, 1.0),
        "Square150x150Logo.png": (150, 150, 0.6), "Square150x150Logo.scale-200.png": (300, 300, 0.6),
        "Wide310x150Logo.png": (310, 150, 0.6), "Wide310x150Logo.scale-200.png": (620, 300, 0.6),
        "SmallTile.png": (71, 71, 0.7), "SmallTile.scale-200.png": (142, 142, 0.7),
        "LargeTile.png": (310, 310, 0.55), "LargeTile.scale-200.png": (620, 620, 0.55),
        "StoreLogo.png": (50, 50, 1.0), "StoreLogo.scale-200.png": (100, 100, 1.0),
        "SplashScreen.png": (620, 300, 0.45), "SplashScreen.scale-200.png": (1240, 600, 0.45),
    }
    for name, (w, h, frac) in plan.items():
        tile(w, h, frac).save(os.path.join(OUT, name))
    for ts in (16, 20, 24, 30, 32, 36, 40, 48, 64, 256):
        icon = make_icon.draw(ts)
        icon.save(os.path.join(OUT, f"Square44x44Logo.targetsize-{ts}.png"))
        icon.save(os.path.join(OUT, f"Square44x44Logo.targetsize-{ts}_altform-unplated.png"))
    print("wrote", len(os.listdir(OUT)), "assets to", OUT)


if __name__ == "__main__":
    main()
