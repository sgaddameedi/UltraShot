"""Draws UltraShot's icon: ui/ultrashot.png (256px, tray/window) and ui/ultrashot.ico (exe).

The mark is "Halo": three concentric rings on black, growing brighter toward the centre, with the
outer ring lit along one arc in the gold-to-orange gradient, and a white core. docs/logo.svg is the
vector version of the same drawing.
"""
import math
import os

from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
OUT_PNG = os.path.join(HERE, "ui", "ultrashot.png")
OUT_ICO = os.path.join(HERE, "ui", "ultrashot.ico")

BLACK = (6, 6, 8, 255)
RING_OUTER = (44, 44, 50, 255)
RING_MID = (96, 96, 104, 255)
GOLD = (255, 209, 102)
ORANGE = (255, 122, 0)
WHITE = (255, 255, 255, 255)


def lerp(a, b, t):
    return tuple(int(round(a[i] + (b[i] - a[i]) * t)) for i in range(3)) + (255,)


def gradient_arc(d, bbox, start, end, width, c0, c1, steps=None):
    """Arc from start to end degrees (PIL convention: 0 = 3 o'clock, clockwise) whose colour runs
    from c0 to c1, with round caps."""
    steps = steps or max(8, int(abs(end - start)))
    x0, y0, x1, y1 = bbox
    cx, cy, r = (x0 + x1) / 2, (y0 + y1) / 2, (x1 - x0) / 2

    def colour_at(ang):
        # linear gradient across the icon: c0 at top-left, c1 at bottom-right (same as logo.svg)
        a = math.radians(ang)
        return lerp(c0, c1, (math.cos(a) + math.sin(a)) / 2.0 + 0.5)

    for i in range(steps):
        a0 = start + (end - start) * i / steps
        a1 = start + (end - start) * (i + 1) / steps
        d.arc(bbox, a0, a1 + 0.6, fill=colour_at((a0 + a1) / 2), width=width)
    if abs(end - start) < 360:
        for ang in (start, end):
            px, py = cx + math.cos(math.radians(ang)) * r, cy + math.sin(math.radians(ang)) * r
            d.ellipse((px - width / 2, py - width / 2, px + width / 2, py + width / 2), fill=colour_at(ang))


def draw(size):
    s = size * 4  # supersample, then downscale
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((0, 0, s - 1, s - 1), radius=int(s * 0.23), fill=BLACK)
    cx = cy = s / 2

    def box(r):
        return (cx - r, cy - r, cx + r, cy + r)

    w = int(s * 0.048)
    d.ellipse(box(s * 0.345), outline=RING_OUTER, width=w)
    d.ellipse(box(s * 0.235), outline=RING_MID, width=w)
    gradient_arc(d, box(s * 0.128), 0, 360, int(s * 0.056), GOLD, ORANGE, steps=90)
    gradient_arc(d, box(s * 0.345), 270, 360, w, GOLD, ORANGE, steps=60)
    d.ellipse(box(s * 0.05), fill=WHITE)
    return img.resize((size, size), Image.LANCZOS)


if __name__ == "__main__":
    os.makedirs(os.path.dirname(OUT_PNG), exist_ok=True)
    big = draw(256)
    big.save(OUT_PNG)
    big.save(OUT_ICO, sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    print("wrote", OUT_PNG, OUT_ICO)
