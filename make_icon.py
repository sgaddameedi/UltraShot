"""Draws UltraShot's icon: ui/ultrashot.png (256px, tray/window) and ui/ultrashot.ico (exe)."""
import math
import os

from PIL import Image, ImageDraw, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
OUT_PNG = os.path.join(HERE, "ui", "ultrashot.png")
OUT_ICO = os.path.join(HERE, "ui", "ultrashot.ico")


def draw(size):
    s = size * 4  # supersample
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    r = s * 0.22
    # background: rounded square with a diagonal blue -> violet gradient
    grad = Image.new("RGBA", (s, s))
    gd = ImageDraw.Draw(grad)
    for y in range(s):
        for x in range(0, s, 8):
            t = (x + y) / (2 * s)
            c = (int(79 + (179 - 79) * t), int(140 + (92 - 140) * t), int(255 + (255 - 255) * t), 255)
            gd.line([(x, y), (x + 8, y)], fill=c)
    mask = Image.new("L", (s, s), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, s - 1, s - 1), radius=int(r), fill=255)
    img.paste(grad, (0, 0), mask)
    # glow
    glow = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    ImageDraw.Draw(glow).ellipse((s * 0.28, s * 0.28, s * 0.72, s * 0.72), fill=(255, 230, 160, 160))
    glow = glow.filter(ImageFilter.GaussianBlur(s * 0.08))
    img.alpha_composite(glow)
    # sun: core + 8 rays
    cx = cy = s / 2
    core = s * 0.16
    d = ImageDraw.Draw(img)
    for i in range(8):
        a = i * math.pi / 4
        x0, y0 = cx + math.cos(a) * s * 0.27, cy + math.sin(a) * s * 0.27
        x1, y1 = cx + math.cos(a) * s * 0.36, cy + math.sin(a) * s * 0.36
        d.line([(x0, y0), (x1, y1)], fill=(255, 255, 255, 255), width=int(s * 0.055))
    d.ellipse((cx - core, cy - core, cx + core, cy + core), fill=(255, 255, 255, 255))
    d.ellipse((cx - core * 0.5, cy - core * 0.5, cx + core * 0.5, cy + core * 0.5), fill=(255, 214, 102, 255))
    return img.resize((size, size), Image.LANCZOS)


if __name__ == "__main__":
    os.makedirs(os.path.dirname(OUT_PNG), exist_ok=True)
    big = draw(256)
    big.save(OUT_PNG)
    big.save(OUT_ICO, sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    print("wrote", OUT_PNG, OUT_ICO)
