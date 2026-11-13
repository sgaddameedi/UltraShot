"""Store listing slides: eye-catching 1920x1080 screenshots for the Microsoft Store.

Each slide shows one feature large, on a frameless capture of the real app, with a headline. The
app is fed the 4K gallery pictures (turned back into scRGB JPEG XL captures in a scratch folder, so
the repository stays as it is) because they are the most vibrant HDR content the project has.

    python tools/store_slides.py            -> packaging/msix/store-listing/slides/01-*.png ...
"""
import ctypes
import os
import shutil
import sys
import tempfile
import threading
import time

import numpy as np
from PIL import Image, ImageDraw, ImageFilter
import webview

# keep the window in SDR composition while capturing (see SDR_CAPTURE in ultrashot.py)
os.environ["ULTRASHOT_SDR_CAPTURE"] = "1"

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))
import jxl2uhdr  # noqa: E402
import ultrashot as U  # noqa: E402
import make_logo  # noqa: E402
from screenshots import grab_window  # noqa: E402

OUT = os.path.join(ROOT, "packaging", "msix", "store-listing", "slides")
W, H = 1920, 1080
GALLERY = os.path.join(ROOT, "examples", "gallery")
# order matters: the first becomes the hero of the viewer slides
# colourful but not blown out: the sunsets put a fifth of the frame above SDR white and clip in SDR
PICKS = ["phantom-blade-zero-lion-dance", "phantom-blade-zero-lantern-stairs", "phantom-blade-zero-village-dusk",
         "phantom-blade-zero-mountain-village", "crimson-desert-storm-sky", "crimson-desert-red-sunset"]

SLIDES = [  # file, headline, subline
    ("01-drop", "Drop. Convert. Share in HDR.", "ReShade .jxl and NVIDIA / Game Bar .jxr captures become Ultra HDR JPEGs that stay HDR on Instagram, phones and the web."),
    ("02-viewer", "Your captures, in real HDR.", "The built-in viewer shows the finished files in HDR on an HDR display, exactly as a phone will."),
    ("03-compare", "SDR on the left. HDR on the right.", "Wipe between what SDR screens see and what HDR screens see. The same file, no compromise on either."),
    ("04-polish", "Polish without touching the HDR.", "Warmth, contrast, vibrance, shadows and a watermark, applied in linear light. Highlights stay exactly as captured."),
    ("05-frame", "Frame it the Instagram way.", "Drag the picture inside the crop window. Each capture keeps its own framing, ready to post without editing."),
    ("06-details", "Every tag, read back from the file.", "Gain map metadata, peak brightness, chroma, colour profile and signalling, so you know what you are posting."),
    ("07-highlights", "See where the HDR lives.", "The highlights map marks every pixel above SDR white, and every one above 600 nits."),
    ("08-settings", "Set it once. It watches your folder.", "Converts new captures as you play, runs from the tray, starts with Windows."),
]


def make_sources(folder):
    """Turn the chosen gallery pictures back into scRGB float JPEG XL captures."""
    paths = []
    for stem in PICKS:
        out = os.path.join(folder, stem + ".jxl")
        if not os.path.exists(out):
            data = open(os.path.join(GALLERY, stem + ".jpg"), "rb").read()
            hdr = U.ic.ultrahdr_decode(data, dtype=np.float16)[..., :3].astype(np.float32)   # 1.0 == 203 nits
            scrgb = (hdr * (U.SDR_WHITE_NITS / 80.0)).astype(np.float16)                     # scRGB: 1.0 == 80 nits
            open(out, "wb").write(U.ic.jpegxl_encode(scrgb, distance=0.3, effort=4))
            print("source", stem)
        paths.append(out)
    return paths


def rounded(img, r):
    mask = Image.new("L", img.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, img.width - 1, img.height - 1), r, fill=255)
    img = img.convert("RGBA"); img.putalpha(mask)
    return img


def compose(shot_path, headline, subline, out):
    compose_image(Image.open(shot_path).convert("RGB"), headline, subline).save(out, optimize=True)
    print("slide", os.path.basename(out))


_AURORA = None


def compose_image(shot, headline, subline):
    """One slide as an image: headline, subline and the app capture on the aurora background."""
    global _AURORA
    if _AURORA is None:
        _AURORA = make_logo.aurora(W, H).convert("RGBA")
    canvas = _AURORA.copy()
    d = ImageDraw.Draw(canvas)
    f1 = make_logo.font(make_logo.FONT_BOLD, 58)
    f2 = make_logo.font(make_logo.FONT_REG, 25)
    d.text((110, 68), headline, font=f1, fill=(246, 243, 236))
    # subline wrapped to the width
    words, lines, cur = subline.split(), [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if d.textbbox((0, 0), t, font=f2)[2] > 1500: lines.append(cur); cur = w
        else: cur = t
    lines.append(cur)
    for i, ln in enumerate(lines): d.text((112, 150 + i * 34), ln, font=f2, fill=(190, 184, 172))
    sw = 1640; sh = round(shot.height * sw / shot.width)
    shot = rounded(shot.resize((sw, sh), Image.LANCZOS), 20)
    shadow = Image.new("RGBA", (sw + 160, sh + 160), (0, 0, 0, 0))
    ImageDraw.Draw(shadow).rounded_rectangle((80, 100, sw + 80, sh + 100), 20, fill=(0, 0, 0, 170))
    shadow = shadow.filter(ImageFilter.GaussianBlur(40))
    x, y = 140, 250
    canvas.alpha_composite(shadow, (x - 80, y - 80))
    canvas.alpha_composite(shot, (x, y))
    return canvas.convert("RGB")


def main():
    os.makedirs(OUT, exist_ok=True)
    scratch = os.path.join(tempfile.gettempdir(), "ultrashot-store-slides")
    os.makedirs(scratch, exist_ok=True)
    # a clean list every run: no remembered cards, no thumbnails, no sources from an earlier pick
    for name in ("session.json", "thumbs"):
        path = os.path.join(scratch, name)
        shutil.rmtree(path, ignore_errors=True) if os.path.isdir(path) else (os.remove(path) if os.path.exists(path) else None)
    for name in os.listdir(scratch):
        if name.endswith(".jxl") and name[:-4] not in PICKS:
            os.remove(os.path.join(scratch, name))
    sources = make_sources(scratch)
    shots = os.path.join(scratch, "shots"); shutil.rmtree(shots, ignore_errors=True); os.makedirs(shots)
    outdir = os.path.join(scratch, "out"); shutil.rmtree(outdir, ignore_errors=True); os.makedirs(outdir)
    ctypes.windll.shcore.SetProcessDpiAwareness(1)

    U.SESSION_FILE = os.path.join(scratch, "session.json"); U.THUMB_DIR = os.path.join(scratch, "thumbs")
    app = U.App()
    app.settings.update(watch=False, startup=False, explorer_menu=False, tray=False, theme="dark", save_mode="folder",
                        save_dir=outdir, overwrite=True, make_full=True, make_ig=True, ig_crop="4:5", exposure=0.0, knee=0.6,
                        auto_sdr=False, limit_nits=0, pane_order=[], pane_widths={}, tile_sort="added_asc")
    U.save_settings = lambda s: None
    app.apply_integrations = lambda: None
    api = U.Api(app)
    title = U.APP_NAME + "        "
    window = webview.create_window(title, os.path.join(U.UI_DIR, "index.html"), js_api=api, width=W, height=H,
                                   frameless=True, background_color="#09090b", text_select=False)
    app.window = window
    js = window.evaluate_js
    shot = lambda name: grab_window(title, os.path.join(shots, name + ".png"))

    def wait(cond, limit=300):
        t = time.time()
        while time.time() - t < limit and not cond(): time.sleep(0.3)

    def flow():
        time.sleep(2.5)
        ids = app.add_paths(sources)
        wait(lambda: all(app.files[i]["thumb"] is not None for i in ids))
        time.sleep(1.0)
        shot("01-drop")
        # convert the hero and one more so the viewer, compare and details have real files
        app.convert(ids[:2]); wait(lambda: all(app.files[i]["status"] not in ("queued", "working") for i in ids[:2]))
        js(f"openLightbox('{ids[0]}')"); time.sleep(2)
        js("document.querySelector('#lbWhich button[data-v=full]').click()"); time.sleep(5)
        shot("02-viewer")
        js("document.querySelector('#lbCompareBtn').click()"); time.sleep(9)
        js("setWipe(46)"); time.sleep(0.6)
        shot("03-compare")
        js("setCompare(false); document.querySelector('#lbInfo').click()"); time.sleep(6)
        shot("06-details")
        js("closeLightbox()"); time.sleep(0.8)
        # polish with the HDR tab
        js(f"select('{ids[2]}')"); time.sleep(2.5)
        api.set_edit(ids[2], {"warmth": 22, "contrast": 18, "vibrance": 28, "shadows": 10, "watermark": "@yourhandle"}, False)
        time.sleep(1.5)
        js("document.querySelector('#inspTarget button[data-v=hdr]').click()"); time.sleep(6)
        shot("04-polish")
        # Instagram framing with the thirds grid showing
        js(f"select('{ids[1]}')"); time.sleep(2)
        js("document.querySelector('#inspTarget button[data-v=ig]').click()"); time.sleep(4)
        js("document.querySelector('#inspPreview').classList.add('dragging')"); time.sleep(0.5)
        shot("05-frame")
        js("document.querySelector('#inspPreview').classList.remove('dragging'); document.querySelector('#inspTarget button[data-v=heat]').click()"); time.sleep(4)
        shot("07-highlights")
        js("closeInspector(); openSettings()"); time.sleep(1.5)
        shot("08-settings")
        window.destroy()

    window.events.loaded += lambda: threading.Thread(target=flow, daemon=True).start()
    webview.start(private_mode=True)

    for name, headline, subline in SLIDES:
        src = os.path.join(shots, name + ".png")
        if os.path.exists(src):
            compose(src, headline, subline, os.path.join(OUT, name + ".png"))
    print("wrote", sorted(os.listdir(OUT)))


if __name__ == "__main__":
    main()
