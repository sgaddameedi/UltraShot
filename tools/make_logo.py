"""Renders docs/banner.png (README hero, 1600x500) and docs/social-preview.png (1280x640) from the
app icon and the Segoe UI font. docs/logo.svg is hand-written and is the canonical logo."""
import os
import sys

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import make_icon  # noqa: E402

FONT_BOLD = r"C:\Windows\Fonts\segoeuib.ttf"
FONT_REG = r"C:\Windows\Fonts\segoeui.ttf"


def font(path, size):
    try:
        return ImageFont.truetype(path, size)
    except OSError:
        return ImageFont.load_default()


def aurora(w, h):
    bg = Image.new("RGB", (w, h), (6, 6, 8))
    glow = Image.new("RGB", (w, h), (6, 6, 8))
    d = ImageDraw.Draw(glow)
    d.ellipse((-w * 0.1, -h * 0.4, w * 0.45, h * 0.9), fill=(70, 48, 8))
    d.ellipse((w * 0.55, -h * 0.5, w * 1.1, h * 0.7), fill=(92, 42, 0))
    d.ellipse((w * 0.3, h * 0.6, w * 0.8, h * 1.5), fill=(42, 30, 6))
    glow = glow.filter(ImageFilter.GaussianBlur(w * 0.09))
    return Image.blend(bg, glow, 0.75)


def banner(path, w, h, tagline=True):
    """Icon on the left, name and tagline on the right. The block is about 1.9 times the reference
    height wide plus the left margin, so on canvases squarer than 2.3:1 (16:9 hero art, the 2:1
    social preview) everything is sized from the width instead of the height and nothing runs off."""
    img = aurora(w, h).convert("RGBA")
    s = min(h, w / 2.3)                       # the height of an equivalent 2.3:1 canvas
    icon = make_icon.draw(int(s * 0.42))
    ix, iy = int(w * 0.09), (h - icon.height) // 2 - (int(s * 0.03) if tagline else 0)
    img.alpha_composite(icon, (ix, iy))
    d = ImageDraw.Draw(img)
    tx = ix + icon.width + int(s * 0.09)
    f1 = font(FONT_BOLD, int(s * 0.26))
    d.text((tx, iy - int(s * 0.02)), "UltraShot", font=f1, fill=(246, 243, 236))
    if tagline:
        f2 = font(FONT_REG, int(s * 0.075))
        d.text((tx + 4, iy + int(s * 0.30)), "HDR screenshots, shared in HDR.", font=f2, fill=(255, 193, 77))
        f3 = font(FONT_REG, int(s * 0.055))
        d.text((tx + 4, iy + int(s * 0.41)), "ReShade .jxl  ·  NVIDIA / Game Bar .jxr   →   Ultra HDR JPEG",
               font=f3, fill=(150, 142, 128))
    img.convert("RGB").save(path, optimize=True)
    print("wrote", path)


if __name__ == "__main__":
    docs = os.path.join(ROOT, "docs")
    os.makedirs(docs, exist_ok=True)
    banner(os.path.join(docs, "banner.png"), 1600, 500)
    banner(os.path.join(docs, "social-preview.png"), 1280, 640)
    make_icon.draw(512).save(os.path.join(docs, "logo.png"))
    print("wrote", os.path.join(docs, "logo.png"))
