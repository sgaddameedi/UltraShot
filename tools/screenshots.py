"""Regenerates docs/screenshots/*.png from the real UI.

    python tools/screenshots.py [capture1.jxl capture2.jxr ...]

Opens UltraShot with the given captures (default: the files in examples/), drives the page through
pywebview and grabs the window with PrintWindow, so the images match what users see. Nothing is
saved to the real settings and no watch folder / startup integration is touched.
"""
import ctypes
import os
import sys
import threading
import time
from ctypes import wintypes

from PIL import Image
import webview

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import ultrashot as U  # noqa: E402

OUT = os.path.join(ROOT, "docs", "screenshots")
W, H = 1280, 840


def grab_window(title, path):
    user32, gdi32 = ctypes.windll.user32, ctypes.windll.gdi32
    hwnd = user32.FindWindowW(None, title)
    if not hwnd:
        raise RuntimeError(f"window '{title}' not found")
    rect = wintypes.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(rect))
    w, h = rect.right - rect.left, rect.bottom - rect.top
    hdc = user32.GetWindowDC(hwnd)
    mem = gdi32.CreateCompatibleDC(hdc)
    bmp = gdi32.CreateCompatibleBitmap(hdc, w, h)
    gdi32.SelectObject(mem, bmp)
    user32.PrintWindow(hwnd, mem, 2)  # PW_RENDERFULLCONTENT: works for WebView2, even if covered

    class BMI(ctypes.Structure):
        _fields_ = [("biSize", wintypes.DWORD), ("biWidth", wintypes.LONG), ("biHeight", wintypes.LONG),
                    ("biPlanes", wintypes.WORD), ("biBitCount", wintypes.WORD), ("biCompression", wintypes.DWORD),
                    ("biSizeImage", wintypes.DWORD), ("biXPelsPerMeter", wintypes.LONG),
                    ("biYPelsPerMeter", wintypes.LONG), ("biClrUsed", wintypes.DWORD), ("biClrImportant", wintypes.DWORD)]
    bmi = BMI(ctypes.sizeof(BMI), w, -h, 1, 32, 0, 0, 0, 0, 0, 0)
    buf = ctypes.create_string_buffer(w * h * 4)
    gdi32.GetDIBits(mem, bmp, 0, h, buf, ctypes.byref(bmi), 0)
    img = Image.frombuffer("RGBA", (w, h), buf.raw, "raw", "BGRA", 0, 1).convert("RGB")
    gdi32.DeleteObject(bmp)
    gdi32.DeleteDC(mem)
    user32.ReleaseDC(hwnd, hdc)
    img.save(path)
    print("saved", path, img.size)


def main():
    files = [a for a in sys.argv[1:] if os.path.exists(a)]
    if not files:
        ex = os.path.join(ROOT, "examples")
        files = [os.path.join(ex, f) for f in sorted(os.listdir(ex)) if f.lower().endswith(U.EXTS)]
    os.makedirs(OUT, exist_ok=True)
    ctypes.windll.shcore.SetProcessDpiAwareness(1)

    app = U.App()
    app.settings.update(watch=False, startup=False, explorer_menu=False, tray=False, theme="dark",
                        ig_crop="4:5", exposure=0.0, knee=0.6, auto_sdr=False)
    U.save_settings = lambda s: None            # never persist the demo settings
    app.apply_integrations = lambda: None
    api = U.Api(app)
    title = U.APP_NAME + " "   # trailing space: never confused with an UltraShot already running
    window = webview.create_window(title, os.path.join(U.UI_DIR, "index.html"), js_api=api,
                                   width=W, height=H, background_color="#0e1014", text_select=False)
    app.window = window

    def js(code):
        window.evaluate_js(code)

    def shot(name):
        grab_window(title, os.path.join(OUT, name))

    def flow():
        time.sleep(2.0)
        app.add_paths(files)
        t = time.time()
        while time.time() - t < 120 and any(f["thumb"] is None and f["status"] != "failed" for f in app.files.values()):
            time.sleep(0.3)
        time.sleep(1.0)
        shot("main.png")
        js("document.querySelector('.card').click()")
        time.sleep(3.0)
        shot("inspector.png")
        js("document.querySelector('#inspTarget button[data-v=ig]').click()")
        time.sleep(3.0)
        shot("instagram-crop.png")
        js("document.querySelector('#inspTarget button[data-v=heat]').click()")
        time.sleep(3.0)
        shot("highlights-map.png")
        js("closeInspector(); document.querySelector('#chipLook').click()")
        time.sleep(0.8)
        shot("sdr-look-menu.png")
        js("document.querySelector('#popover').classList.add('hidden'); openSettings()")
        time.sleep(1.0)
        shot("settings.png")
        window.destroy()

    window.events.loaded += lambda: threading.Thread(target=flow, daemon=True).start()
    webview.start(private_mode=True)


if __name__ == "__main__":
    main()
