"""Store trailer: a short silent 1080p MP4 for the Microsoft Store listing, plus its thumbnail.

The app runs frameless at 3840x2160 with WebView2 forced to a device scale of 2, so every capture
is the 1920x1080 interface at twice the resolution. A virtual camera then moves over the composed
slide on eased keyframes with sub-pixel accuracy: zooming into the inspector while the Polish
sliders move, into the crop window while the Instagram frame is dragged, into the compare metrics
and the file details, and into the settings page, before easing back out. Nothing is cropped to
whole pixels and nothing is scaled up past the captured resolution, so the result is smooth and
sharp. FFmpeg encodes it as H.264 with a silent audio track, which is what Partner Center expects.

    python tools/store_trailer.py   -> packaging/msix/store-listing/trailer.mp4 and trailer-thumbnail.png
"""
import ctypes
import math
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time

from PIL import Image, ImageDraw, ImageFilter
import webview

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))
os.environ["ULTRASHOT_SDR_CAPTURE"] = "1"                               # keep the window in SDR composition
os.environ["WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS"] = "--force-device-scale-factor=2"
import ultrashot as U  # noqa: E402
import make_logo  # noqa: E402
import make_icon  # noqa: E402
from screenshots import grab_window  # noqa: E402
from store_slides import make_sources  # noqa: E402

OUT_DIR = os.path.join(ROOT, "packaging", "msix", "store-listing")
FPS = 30
W, H = 1920, 1080          # output
S = 2                      # capture scale
CW, CH = W * S, H * S      # composition canvas, at capture scale
SHOT_W = 1640 * S          # the app capture's width on the canvas
SHOT_X, SHOT_Y = 140 * S, 250 * S

# ---------------------------------------------------------------- composition at 2x


def rounded(img, r):
    mask = Image.new("L", img.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, img.width - 1, img.height - 1), r, fill=255)
    img = img.convert("RGBA"); img.putalpha(mask)
    return img


_bg_cache = {}


def background(headline, subline):
    """The slide background with its text, at canvas scale, cached per headline."""
    key = (headline, subline)
    if key not in _bg_cache:
        c = make_logo.aurora(CW, CH).convert("RGBA")
        d = ImageDraw.Draw(c)
        f1 = make_logo.font(make_logo.FONT_BOLD, 58 * S); f2 = make_logo.font(make_logo.FONT_REG, 25 * S)
        d.text((110 * S, 68 * S), headline, font=f1, fill=(246, 243, 236))
        words, lines, cur = subline.split(), [], ""
        for w in words:
            t = (cur + " " + w).strip()
            if d.textbbox((0, 0), t, font=f2)[2] > 1500 * S: lines.append(cur); cur = w
            else: cur = t
        lines.append(cur)
        for i, ln in enumerate(lines): d.text((112 * S, (150 + i * 34) * S), ln, font=f2, fill=(190, 184, 172))
        # the shadow under the app capture is part of the background
        sh = round(1041 / 1904 * SHOT_W)
        shadow = Image.new("RGBA", (SHOT_W + 160 * S, sh + 160 * S), (0, 0, 0, 0))
        ImageDraw.Draw(shadow).rounded_rectangle((80 * S, 100 * S, SHOT_W + 80 * S, sh + 100 * S), 20 * S, fill=(0, 0, 0, 170))
        shadow = shadow.filter(ImageFilter.GaussianBlur(40 * S))
        c.alpha_composite(shadow, (SHOT_X - 80 * S, SHOT_Y - 80 * S))
        _bg_cache[key] = c
    return _bg_cache[key]


_shot_cache = {}


def composed(shot_path, headline, subline):
    """The full canvas for one captured app frame, at canvas scale (cached per capture)."""
    key = (shot_path, headline)
    if key not in _shot_cache:
        shot = Image.open(shot_path).convert("RGB")
        sh = round(shot.height * SHOT_W / shot.width)
        shot = rounded(shot.resize((SHOT_W, sh), Image.LANCZOS), 20 * S)
        c = background(headline, subline).copy()
        c.alpha_composite(shot, (SHOT_X, SHOT_Y))
        _shot_cache[key] = c.convert("RGB")
        if len(_shot_cache) > 12: _shot_cache.pop(next(iter(_shot_cache)))
    return _shot_cache[key]


def card(title, lines):
    img = make_logo.aurora(CW, CH).convert("RGBA")
    d = ImageDraw.Draw(img)
    icon = make_icon.draw(150 * S); img.alpha_composite(icon, ((CW - icon.width) // 2, 300 * S))
    f1 = make_logo.font(make_logo.FONT_BOLD, 76 * S); f2 = make_logo.font(make_logo.FONT_REG, 30 * S)
    w = d.textbbox((0, 0), title, font=f1)[2]; d.text(((CW - w) // 2, 490 * S), title, font=f1, fill=(246, 243, 236))
    for i, ln in enumerate(lines):
        w = d.textbbox((0, 0), ln, font=f2)[2]
        d.text(((CW - w) // 2, (600 + i * 44) * S), ln, font=f2, fill=(255, 193, 77) if i == 0 else (190, 184, 172))
    return img.convert("RGB")


# ---------------------------------------------------------------- the camera and the reel

FULL = (0, 0, W, H)      # camera rectangles are in output pixels over the 1920x1080 slide


def ease(t):
    return 0.5 - 0.5 * math.cos(math.pi * max(0.0, min(1.0, t)))


def lerp_rect(a, b, t):
    return tuple(a[i] + (b[i] - a[i]) * t for i in range(4))


def app_rect(x, y, w, h):
    """A rectangle given in the app's own 1920x1080 interface pixels, as a camera rectangle
    (the app capture sits scaled to 1640 wide at 140,250 on the slide), padded a little and kept
    at 16:9."""
    k = 1640 / 1920
    cx, cy = 140 + (x + w / 2) * k, 250 + (y + h / 2) * k
    rw, rh = w * k * 1.12, h * k * 1.12
    if rw / rh < 16 / 9: rw = rh * 16 / 9
    else: rh = rw * 9 / 16
    rw, rh = min(rw, W), min(rh, H)
    rx, ry = max(0, min(W - rw, cx - rw / 2)), max(0, min(H - rh, cy - rh / 2))
    return (rx, ry, rw, rh)


class Reel:
    def __init__(self, folder):
        self.folder = folder; self.n = 0; self.last = None
        shutil.rmtree(folder, ignore_errors=True); os.makedirs(folder)

    @staticmethod
    def _canvas(item):
        return composed(item[0], *item[1]) if isinstance(item, tuple) else item

    def _render(self, canvas, rect):
        canvas = self._canvas(canvas)
        x, y, w, h = rect
        # sub-pixel crop through an affine transform, then LANCZOS down to the output size
        sx = w * S / W
        box = (x * S, y * S, (x + w) * S, (y + h) * S)
        if abs(sx - 1.0) < 1e-6 and abs(box[0] - round(box[0])) < 1e-6:
            return canvas.crop(tuple(round(v) for v in box)).resize((W, H), Image.LANCZOS)
        # transform maps output pixel (u,v) -> canvas (x*S + u*sx, y*S + v*sx); render at 2x then down-sample for quality
        mid = canvas.transform((W * 2, H * 2), Image.AFFINE, (sx / 2, 0, box[0], 0, sx / 2, box[1]), resample=Image.BICUBIC)
        return mid.resize((W, H), Image.LANCZOS)

    def push(self, canvas, rect=FULL):
        img = canvas if (not isinstance(canvas, tuple) and canvas.size == (W, H)) else self._render(canvas, rect)
        img.save(os.path.join(self.folder, f"{self.n:05d}.png"), compress_level=1)
        self.n += 1; self.last = img

    def hold(self, canvas, seconds, rect=FULL):
        frame = self._render(canvas, rect)
        for _ in range(round(seconds * FPS)): self.push(frame)

    def fade_to(self, canvas, seconds=0.45, rect=FULL):
        target = self._render(canvas, rect)
        k = round(seconds * FPS)
        for i in range(1, k + 1): self.push(Image.blend(self.last, target, i / k))

    def move(self, canvases, seconds, rect_from, rect_to, hold_end=0.0):
        """Camera eases from one rectangle to another while the frames (a list, spread evenly, or a
        single canvas) play."""
        k = round(seconds * FPS)
        for i in range(k):
            t = ease(i / max(1, k - 1))
            c = canvases[min(len(canvases) - 1, i * len(canvases) // k)] if isinstance(canvases, list) else canvases
            self.push(c, lerp_rect(rect_from, rect_to, t))
        if hold_end:
            c = canvases[-1] if isinstance(canvases, list) else canvases
            self.hold(c, hold_end, rect_to)

    def play(self, canvases, seconds, rect=FULL):
        self.move(canvases, seconds, rect, rect)


def ffmpeg():
    for c in ("ffmpeg", r"C:\ffmpeg\bin\ffmpeg.exe"):
        if shutil.which(c) or os.path.exists(c):
            return c
    raise SystemExit("FFmpeg is needed: winget install Gyan.FFmpeg")


# ---------------------------------------------------------------- record

def record(scratch, sources):
    live = os.path.join(scratch, "live"); shutil.rmtree(live, ignore_errors=True); os.makedirs(live)
    for name in ("session.json",):
        p = os.path.join(scratch, name)
        if os.path.exists(p): os.remove(p)
    shutil.rmtree(os.path.join(scratch, "thumbs"), ignore_errors=True)
    U.SESSION_FILE = os.path.join(scratch, "session.json"); U.THUMB_DIR = os.path.join(scratch, "thumbs")
    app = U.App()
    app.settings.update(watch=False, startup=False, explorer_menu=False, tray=False, theme="dark", save_mode="folder",
                        save_dir=os.path.join(scratch, "out"), overwrite=True, make_full=True, make_ig=True, ig_crop="4:5",
                        exposure=0.0, knee=0.6, auto_sdr=False, pane_order=[], pane_widths={}, tile_sort="added_asc", notifications=False)
    U.save_settings = lambda s: None
    app.apply_integrations = lambda: None
    api = U.Api(app)
    title = U.APP_NAME + "           "
    window = webview.create_window(title, os.path.join(U.UI_DIR, "index.html"), js_api=api, width=CW, height=CH,
                                   frameless=True, background_color="#09090b", text_select=False)
    app.window = window
    js = window.evaluate_js
    seqs = {}

    def grab(seq):
        seqs.setdefault(seq, [])
        p = os.path.join(live, f"{seq}-{len(seqs[seq]):04d}.png"); grab_window(title, p); seqs[seq].append(p)

    def burst(seq, seconds, every=0.1):
        t = time.time()
        while time.time() - t < seconds: grab(seq); time.sleep(every)

    def wait_idle(ids, limit=300):
        t = time.time()
        while time.time() - t < limit and any(app.files[i]["status"] in ("queued", "working") for i in ids): time.sleep(0.2)

    def flow():
        time.sleep(3)
        print("device pixel ratio:", js("window.devicePixelRatio"), "inner:", js("innerWidth + 'x' + innerHeight"))
        ids = app.add_paths(sources)
        t = time.time()
        while time.time() - t < 20:
            grab("drop")
            if all(app.files[i]["thumb"] is not None for i in ids) and time.time() - t > 2: break
            time.sleep(0.1)
        burst("drop", 0.8)
        # open the inspector on the village at dusk and polish it
        js(f"select('{ids[2]}')"); burst("open", 1.2, 0.06)
        time.sleep(1.5); grab("open")
        for w, c, v, sh in [(0, 0, 0, 0), (6, 3, 7, 2), (12, 6, 14, 4), (18, 9, 21, 6), (24, 12, 28, 8), (30, 15, 35, 10), (33, 18, 40, 12), (33, 18, 44, 12)]:
            js(f"S.edit = Object.assign(polishOf(S.files.get(S.selected)), {{warmth:{w}, contrast:{c}, vibrance:{v}, shadows:{sh}}}); renderPolish(); requestPreview();")
            time.sleep(0.35); grab("polish")
        api.set_edit(ids[2], {"warmth": 33, "contrast": 18, "vibrance": 44, "shadows": 12, "watermark": "@yourhandle"}, False)
        time.sleep(1.2); grab("polish")
        js("document.querySelector('#inspTarget button[data-v=hdr]').click()"); time.sleep(5); grab("polish")
        # frame the lantern stairs for Instagram
        js(f"select('{ids[1]}')"); time.sleep(2)
        js("document.querySelector('#inspTarget button[data-v=ig]').click()"); time.sleep(3.5); grab("frame")
        js("document.querySelector('#inspPreview').classList.add('dragging')")
        for i in range(28):
            fx = 50 + 36 * math.sin(i / 27 * math.pi * 1.0 - math.pi / 2) if i < 14 else 14 + (i - 14) * 5.1
            js(f"document.querySelector('#inspPreview').style.setProperty('--fx', '{fx:.1f}%')"); time.sleep(0.05); grab("frame")
        js("document.querySelector('#inspPreview').classList.remove('dragging')")
        api.set_edit(ids[1], {"crop_x": 85, "crop_y": 50}, False); time.sleep(0.6); grab("frame")
        # convert everything and watch the progress
        js("closeInspector()"); time.sleep(0.6); grab("convert")
        js("convertAll()")
        t = time.time()
        while time.time() - t < 240 and any(app.files[i]["status"] in ("queued", "working") for i in ids):
            grab("convert"); time.sleep(0.4)
        time.sleep(1.0); burst("convert", 1.0, 0.2)
        # open the result, compare, read the report
        js(f"openLightbox('{ids[0]}')"); time.sleep(2)
        js("document.querySelector('#lbWhich button[data-v=full]').click()"); time.sleep(5); grab("view")
        js("document.querySelector('#lbCompareBtn').click()"); time.sleep(8); grab("compare")
        for p in range(50, 22, -4): js(f"setWipe({p})"); time.sleep(0.05); grab("compare")
        for p in range(22, 74, 4): js(f"setWipe({p})"); time.sleep(0.05); grab("compare")
        js("LB.cmpMode='source'; loadCompare()"); time.sleep(16); grab("compare2")
        for p in range(50, 26, -4): js(f"setWipe({p})"); time.sleep(0.05); grab("compare2")
        js("setCompare(false); document.querySelector('#lbInfo').click()"); time.sleep(6); grab("details")
        for y in range(0, 1300, 60):
            js(f"document.querySelector('#lbInfoBody').scrollTop = {y}"); time.sleep(0.04); grab("details")
        js("closeLightbox(); openSettings()"); time.sleep(1.5); grab("settings")
        for y in range(0, 900, 45):
            js(f"document.querySelector('#settings').scrollTop = {y}"); time.sleep(0.04); grab("settings")
        window.destroy()

    window.events.loaded += lambda: threading.Thread(target=flow, daemon=True).start()
    webview.start(private_mode=True)
    return seqs


# ---------------------------------------------------------------- assemble

def main():
    scratch = os.path.join(tempfile.gettempdir(), "ultrashot-store-slides")
    os.makedirs(scratch, exist_ok=True)
    sources = make_sources(scratch)
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
    seqs = record(scratch, sources)
    print({k: len(v) for k, v in seqs.items()}, "live frames")

    T = {
        "drop": ("Drop. Convert. Share in HDR.", "ReShade .jxl and NVIDIA / Game Bar .jxr captures become Ultra HDR JPEGs that keep the HDR on any screen."),
        "polish": ("Polish without touching the HDR.", "Warmth, contrast, vibrance, shadows and a watermark, applied in linear light. Highlights stay exactly as captured."),
        "frame": ("Frame it the Instagram way.", "Drag the picture inside the crop window. Each capture keeps its own framing."),
        "convert": ("One click. Every capture.", "Full-size and Instagram copies, written next to the originals or into one folder."),
        "view": ("Your captures, in real HDR.", "The built-in viewer shows the finished files in HDR on an HDR display."),
        "compare": ("Compare what every screen will see.", "Wipe between the SDR base and the HDR rendering, or between the capture and the finished file."),
        "details": ("Read the report.", "Every tag in the finished JPEG: gain map metadata, peak brightness, chroma, colour profile and signalling."),
        "settings": ("Set it once.", "A watch folder converts new captures as you play. Runs from the tray, starts with Windows."),
    }
    C = lambda seq, head: [(p, T[head]) for p in seqs[seq]]      # noqa: E731  (composed lazily)
    reel = Reel(os.path.join(scratch, "frames"))

    # camera targets, in the app's own interface pixels (1920x1080 layout)
    INSPECTOR = app_rect(1420, 100, 490, 980)
    POLISH = app_rect(1420, 560, 490, 420)
    PREVIEW = app_rect(1420, 100, 490, 620)
    CONVERT_BTN = app_rect(1330, 1000, 580, 72)
    GRID = app_rect(0, 320, 1420, 760)
    METRICS = app_rect(40, 940, 1840, 120)
    DETAILS = app_rect(1380, 300, 540, 780)
    SETTINGS = app_rect(680, 100, 1240, 980)

    black = Image.new("RGB", (W, H), (9, 9, 11))
    opener = card("UltraShot", ["HDR screenshots, shared in HDR.", "ReShade .jxl and NVIDIA / Game Bar .jxr captures become Ultra HDR JPEGs."])
    reel.push(black); reel.fade_to(opener, 0.8); reel.hold(opener, 2.2)

    drop = C("drop", "drop")
    reel.fade_to(drop[0]); reel.play(drop, 4.5); reel.hold(drop[-1], 0.6)

    opn = C("open", "polish")
    reel.fade_to(opn[0], 0.3); reel.move(opn, 1.6, FULL, INSPECTOR)
    pol = C("polish", "polish")
    reel.move(pol[:-2], 4.5, INSPECTOR, POLISH)                 # the sliders moving, camera settling on them
    reel.move([pol[-2]], 1.0, POLISH, PREVIEW); reel.hold(pol[-1], 1.4, PREVIEW)   # the HDR tab

    fr = C("frame", "frame")
    reel.fade_to(fr[0], 0.35, PREVIEW); reel.hold(fr[0], 0.5, PREVIEW)
    reel.play(fr[1:], 3.6, PREVIEW); reel.hold(fr[-1], 0.6, PREVIEW)

    cv = C("convert", "convert")
    reel.move([cv[0]], 1.2, PREVIEW, FULL)
    reel.move(cv, 5.0, FULL, GRID, hold_end=0.8)

    vw = C("view", "view")
    reel.fade_to(vw[0], 0.45); reel.move(vw, 3.0, FULL, FULL)

    cp = C("compare", "compare")
    reel.fade_to(cp[0], 0.35); reel.play(cp, 4.0)
    cp2 = C("compare2", "compare")
    reel.fade_to(cp2[0], 0.35); reel.move(cp2, 3.0, FULL, METRICS, hold_end=1.2)

    dt = C("details", "details")
    reel.fade_to(dt[0], 0.35); reel.move(dt, 5.0, FULL, DETAILS, hold_end=0.6)

    st = C("settings", "settings")
    reel.fade_to(st[0], 0.35); reel.move(st, 4.0, FULL, SETTINGS, hold_end=0.6)

    closer = card("UltraShot", ["Free and open source.", "sgaddameedi.github.io/UltraShot"])
    reel.fade_to(closer, 0.6); reel.hold(closer, 2.6); reel.fade_to(black, 0.8)
    print(reel.n, "frames,", round(reel.n / FPS, 1), "s")

    out = os.path.join(OUT_DIR, "trailer.mp4")
    subprocess.run([ffmpeg(), "-y", "-loglevel", "error", "-framerate", str(FPS), "-i", os.path.join(reel.folder, "%05d.png"),
                    "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo", "-shortest",
                    "-c:v", "libx264", "-preset", "slow", "-crf", "17", "-pix_fmt", "yuv420p", "-profile:v", "high", "-level", "4.1",
                    "-c:a", "aac", "-b:a", "64k", "-movflags", "+faststart", out], check=True)
    reel._render(vw[0], FULL).save(os.path.join(OUT_DIR, "trailer-thumbnail.png"), optimize=True)
    print("wrote", out, f"({os.path.getsize(out) / 1e6:.1f} MB) and trailer-thumbnail.png")


if __name__ == "__main__":
    main()
