"""Store trailer: a short silent 1080p MP4 for the Microsoft Store listing, plus its thumbnail.

Runs after tools/store_slides.py (it reuses that script's app captures in the scratch folder) and
records two live sequences from the real app: the Polish sliders sweeping with the preview
following, and the Instagram frame being dragged. Everything is composed on the slide background
with the slide headlines, and FFmpeg encodes it as H.264 with a silent audio track, which is what
Partner Center expects.

    python tools/store_trailer.py   -> packaging/msix/store-listing/trailer.mp4 and trailer-thumbnail.png
"""
import ctypes
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time

from PIL import Image, ImageDraw
import webview

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))
os.environ["ULTRASHOT_SDR_CAPTURE"] = "1"
import ultrashot as U  # noqa: E402
import make_logo  # noqa: E402
from screenshots import grab_window  # noqa: E402
from store_slides import compose_image, make_sources, SLIDES, W, H  # noqa: E402

OUT_DIR = os.path.join(ROOT, "packaging", "msix", "store-listing")
FPS = 30
HEAD = {k: (h, s) for k, h, s in SLIDES}


def ffmpeg():
    for c in ("ffmpeg", r"C:\ffmpeg\bin\ffmpeg.exe"):
        if shutil.which(c) or os.path.exists(c):
            return c
    raise SystemExit("FFmpeg is needed: winget install Gyan.FFmpeg")


class Reel:
    """Collects output frames on disk, with crossfades between segments."""
    def __init__(self, folder):
        self.folder = folder; self.n = 0; self.last = None
        shutil.rmtree(folder, ignore_errors=True); os.makedirs(folder)

    def push(self, img):
        img.save(os.path.join(self.folder, f"{self.n:05d}.png"), compress_level=1)
        self.n += 1; self.last = img

    def hold(self, img, seconds):
        for _ in range(round(seconds * FPS)): self.push(img)

    def fade_to(self, img, seconds=0.45):
        if self.last is None: return
        k = round(seconds * FPS)
        for i in range(1, k + 1): self.push(Image.blend(self.last, img, i / k))

    def push_in(self, img, seconds, zoom=0.04):
        """A slow push into a still, as a video editor would."""
        k = round(seconds * FPS)
        for i in range(k):
            z = 1 + zoom * i / max(1, k - 1)
            cw, ch = round(W / z), round(H / z)
            x, y = (W - cw) // 2, (H - ch) // 2
            self.push(img.crop((x, y, x + cw, y + ch)).resize((W, H), Image.BILINEAR))

    def sequence(self, frames, seconds):
        """Live frames captured at an uneven rate, spread evenly over the time."""
        k = round(seconds * FPS)
        for i in range(k):
            self.push(frames[min(len(frames) - 1, i * len(frames) // k)])


def card(title, lines, logo=True):
    img = make_logo.aurora(W, H).convert("RGBA")
    d = ImageDraw.Draw(img)
    if logo:
        import make_icon
        icon = make_icon.draw(150); img.alpha_composite(icon, ((W - 150) // 2, 300))
    f1 = make_logo.font(make_logo.FONT_BOLD, 76); f2 = make_logo.font(make_logo.FONT_REG, 30)
    w = d.textbbox((0, 0), title, font=f1)[2]; d.text(((W - w) // 2, 490), title, font=f1, fill=(246, 243, 236))
    for i, ln in enumerate(lines):
        w = d.textbbox((0, 0), ln, font=f2)[2]; d.text(((W - w) // 2, 600 + i * 44), ln, font=f2, fill=(255, 193, 77) if i == 0 else (190, 184, 172))
    return img.convert("RGB")


def main():
    scratch = os.path.join(tempfile.gettempdir(), "ultrashot-store-slides")
    shots = os.path.join(scratch, "shots")
    if not os.path.isdir(shots) or not os.path.exists(os.path.join(shots, "02-viewer.png")):
        raise SystemExit("run tools/store_slides.py first")
    live = os.path.join(scratch, "live"); shutil.rmtree(live, ignore_errors=True); os.makedirs(live)
    sources = make_sources(scratch)
    ctypes.windll.shcore.SetProcessDpiAwareness(1)

    # ---- record the live sequences from the real app
    for name in ("session.json",):
        p = os.path.join(scratch, name)
        if os.path.exists(p): os.remove(p)
    U.SESSION_FILE = os.path.join(scratch, "session.json"); U.THUMB_DIR = os.path.join(scratch, "thumbs")
    app = U.App()
    app.settings.update(watch=False, startup=False, explorer_menu=False, tray=False, theme="dark", save_mode="folder",
                        save_dir=os.path.join(scratch, "out"), overwrite=True, ig_crop="4:5", exposure=0.0, knee=0.6,
                        auto_sdr=False, pane_order=[], pane_widths={}, tile_sort="added_asc")
    U.save_settings = lambda s: None
    app.apply_integrations = lambda: None
    api = U.Api(app)
    title = U.APP_NAME + "          "
    window = webview.create_window(title, os.path.join(U.UI_DIR, "index.html"), js_api=api, width=W, height=H,
                                   frameless=True, background_color="#09090b", text_select=False)
    app.window = window
    js = window.evaluate_js
    seqs = {"drop": [], "polish": [], "frame": []}

    def grab(seq):
        p = os.path.join(live, f"{seq}-{len(seqs[seq]):04d}.png"); grab_window(title, p); seqs[seq].append(p)

    def flow():
        time.sleep(2.5)
        # the grid filling up as thumbnails arrive
        ids = app.add_paths(sources)
        t = time.time()
        while time.time() - t < 14:
            grab("drop")
            if all(app.files[i]["thumb"] is not None for i in ids) and time.time() - t > 2: break
            time.sleep(0.12)
        for _ in range(6): grab("drop"); time.sleep(0.12)
        # polish sliders sweeping, preview following
        js(f"select('{ids[2]}')"); time.sleep(2.5)
        steps = [(w, c, v) for w, c, v in zip(range(0, 36, 3), range(0, 24, 2), range(0, 48, 4))]
        for w, c, v in steps:
            js(f"S.edit = Object.assign(polishOf(S.files.get(S.selected)), {{warmth:{w}, contrast:{c}, vibrance:{v}}}); renderPolish(); requestPreview();")
            time.sleep(0.32); grab("polish")
        api.set_edit(ids[2], {"warmth": 33, "contrast": 22, "vibrance": 44}, False); time.sleep(1.0); grab("polish")
        # the Instagram frame being dragged across the picture
        js(f"select('{ids[1]}')"); time.sleep(2)
        js("document.querySelector('#inspTarget button[data-v=ig]').click()"); time.sleep(3.5)
        js("document.querySelector('#inspPreview').classList.add('dragging')")
        for i in range(26):
            fx = 15 + i * 2.7
            js(f"document.querySelector('#inspPreview').style.setProperty('--fx', '{fx:.1f}%')"); time.sleep(0.05); grab("frame")
        js("document.querySelector('#inspPreview').classList.remove('dragging')"); time.sleep(0.3); grab("frame")
        window.destroy()

    window.events.loaded += lambda: threading.Thread(target=flow, daemon=True).start()
    webview.start(private_mode=True)
    print({k: len(v) for k, v in seqs.items()}, "live frames")

    # ---- assemble
    load = lambda p: Image.open(p).convert("RGB")
    slide = lambda name: compose_image(load(os.path.join(shots, name + ".png")), *HEAD[name])
    liveframes = lambda seq, name: [compose_image(load(p), *HEAD[name]) for p in seqs[seq]]
    reel = Reel(os.path.join(scratch, "frames"))
    black = Image.new("RGB", (W, H), (9, 9, 11))
    opener = card("UltraShot", ["HDR screenshots, shared in HDR.", "ReShade .jxl and NVIDIA / Game Bar .jxr captures become Ultra HDR JPEGs."])
    reel.push(black); reel.fade_to(opener, 0.8); reel.hold(opener, 2.2)
    drop = liveframes("drop", "01-drop"); reel.fade_to(drop[0]); reel.sequence(drop, 5.0); reel.hold(drop[-1], 1.0)
    s2 = slide("02-viewer"); reel.fade_to(s2); reel.push_in(s2, 4.5)
    s3 = slide("03-compare"); reel.fade_to(s3); reel.push_in(s3, 4.5)
    pol = liveframes("polish", "04-polish"); reel.fade_to(pol[0]); reel.hold(pol[0], 0.6); reel.sequence(pol, 5.0); reel.hold(pol[-1], 1.2)
    fr = liveframes("frame", "05-frame"); reel.fade_to(fr[0]); reel.hold(fr[0], 0.5); reel.sequence(fr, 4.0); reel.hold(fr[-1], 1.0)
    s6 = slide("06-details"); reel.fade_to(s6); reel.push_in(s6, 4.0)
    s7 = slide("07-highlights"); reel.fade_to(s7); reel.push_in(s7, 3.5)
    closer = card("UltraShot", ["Free and open source.", "sgaddameedi.github.io/UltraShot"])
    reel.fade_to(closer, 0.6); reel.hold(closer, 3.0); reel.fade_to(black, 0.8)
    print(reel.n, "frames,", round(reel.n / FPS, 1), "s")

    out = os.path.join(OUT_DIR, "trailer.mp4")
    subprocess.run([ffmpeg(), "-y", "-loglevel", "error", "-framerate", str(FPS), "-i", os.path.join(reel.folder, "%05d.png"),
                    "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo", "-shortest",
                    "-c:v", "libx264", "-preset", "slow", "-crf", "17", "-pix_fmt", "yuv420p", "-profile:v", "high", "-level", "4.1",
                    "-c:a", "aac", "-b:a", "64k", "-movflags", "+faststart", out], check=True)
    s2.save(os.path.join(OUT_DIR, "trailer-thumbnail.png"), optimize=True)
    print("wrote", out, f"({os.path.getsize(out) / 1e6:.1f} MB) and trailer-thumbnail.png")


if __name__ == "__main__":
    main()
