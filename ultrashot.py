#!/usr/bin/env python3
"""UltraShot - turns HDR game screenshots (ReShade .jxl, NVIDIA / Game Bar .jxr) into
Ultra HDR JPEGs (gain map) that Instagram, phones and Chrome/Edge show in HDR.

Run:
    pythonw ultrashot.py                  (or double-click UltraShot.bat / UltraShot.exe)
    ultrashot.py a.jxl b.jxr              (converts those files; a running instance picks them up)
    ultrashot.py --tray                   (start hidden in the tray; used by "start with Windows")

Needs jxl2uhdr.py and the ui/ folder next to this file, plus:
    pip install pywebview pystray imagecodecs numpy pillow
"""
import base64
import io
import json
import os
import queue
import socket
import subprocess
import sys
import threading
import time
import traceback
import uuid
from collections import OrderedDict

import numpy as np
from PIL import Image
import webview

FROZEN = getattr(sys, "frozen", False)
HERE = sys._MEIPASS if FROZEN else os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import jxl2uhdr  # noqa: E402

APP_NAME = "UltraShot"
APP_ID = "UltraShot"
VERSION = "1.1.0"
UI_DIR = os.path.join(HERE, "ui")
ICON_PNG = os.path.join(UI_DIR, "ultrashot.png")
APPDATA = os.environ.get("APPDATA") or os.path.expanduser("~")
SETTINGS_DIR = os.path.join(APPDATA, APP_ID)
SETTINGS_FILE = os.path.join(SETTINGS_DIR, "settings.json")
OLD_SETTINGS_FILE = os.path.join(APPDATA, "JXL Ultra HDR", "settings.json")
STARTUP_DIR = os.path.join(APPDATA, r"Microsoft\Windows\Start Menu\Programs\Startup")
STARTUP_LNK = os.path.join(STARTUP_DIR, "UltraShot.lnk")
SINGLE_INSTANCE_PORT = 47811
EXTS = (".jxl", ".jxr")
PREVIEW_W = 1280
THUMB_W = 520
CACHE_SIZE = 8


def default_capture_dir():
    home = os.path.expanduser("~")
    for p in (os.path.join(home, "Videos", "Captures"),            # Windows Game Bar / ReShade default
              os.path.join(home, "Pictures", "Screenshots"),
              os.path.join(home, "Videos", "NVIDIA")):
        if os.path.isdir(p):
            return p
    return os.path.join(home, "Pictures")


DEFAULTS = dict(
    theme="dark", notifications=True,
    make_full=True, full_dir="4K HDR",
    make_ig=True, ig_dir="Insta", ig_width=1440, ig_crop="none", crop_x=50, crop_y=50,
    save_mode="beside", save_dir="", keep_date=True, overwrite=False, suffix="",
    watch=True, watch_dir="", watch_subfolders=True, watch_existing=False, settle=3.0, interval=2.0,
    tray=True, startup=True, explorer_menu=False,
    exposure=0.0, knee=0.6, auto_sdr=False, quality=100, peak_nits=0, transfer="auto",
    win_w=1280, win_h=840, win_x=-1, win_y=-1,
)


# ----------------------------------------------------------------------------- helpers

def is_hdr_image(p):
    return p.lower().endswith(EXTS)


def collect_images(paths):
    out, seen = [], set()
    for p in paths:
        if os.path.isdir(p):
            try:
                cands = [os.path.join(p, f) for f in sorted(os.listdir(p)) if is_hdr_image(f)]
            except OSError:
                cands = []
        elif is_hdr_image(p) and os.path.isfile(p):
            cands = [p]
        else:
            cands = []
        for c in cands:
            c = os.path.abspath(c)
            if c.lower() not in seen:
                seen.add(c.lower())
                out.append(c)
    return out


def luminance(nits, gamut):
    w = jxl2uhdr.LUMA_2020 if gamut == jxl2uhdr.ic.ULTRAHDR.CG.BT_2100 else jxl2uhdr.LUMA_709
    return nits @ w


def jpeg_data_url(rgb, quality=86):
    im = Image.fromarray(np.ascontiguousarray(rgb[..., :3]), "RGB")
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=quality, subsampling=0)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode("ascii")


def load_settings():
    s = dict(DEFAULTS)
    first_run = not os.path.exists(SETTINGS_FILE)
    src = SETTINGS_FILE if not first_run else (OLD_SETTINGS_FILE if os.path.exists(OLD_SETTINGS_FILE) else None)
    if src:
        try:
            with open(src, "r", encoding="utf-8") as f:
                data = json.load(f)
            for k, v in data.items():
                if k in DEFAULTS and v is not None:
                    s[k] = bool(v) if isinstance(DEFAULTS[k], bool) else type(DEFAULTS[k])(v)
        except Exception:
            pass
    if not s["watch_dir"] or not os.path.isdir(s["watch_dir"]):
        s["watch_dir"] = default_capture_dir()
    return s, first_run


def save_settings(s):
    os.makedirs(SETTINGS_DIR, exist_ok=True)
    tmp = SETTINGS_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(s, f, indent=2)
    os.replace(tmp, SETTINGS_FILE)


def launcher():
    """(target, arguments-prefix) that starts this app."""
    if FROZEN:
        return sys.executable, ""
    pyw = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
    if not os.path.exists(pyw):
        pyw = sys.executable
    return pyw, f'"{os.path.abspath(__file__)}" '


def run_hidden(args):
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    return subprocess.run(args, capture_output=True, text=True, creationflags=flags, timeout=30)


def set_startup(enabled):
    """Startup-folder shortcut that opens UltraShot hidden in the tray."""
    if enabled:
        target, prefix = launcher()
        os.makedirs(STARTUP_DIR, exist_ok=True)
        ps = (f"$s=(New-Object -ComObject WScript.Shell).CreateShortcut('{STARTUP_LNK}');"
              f"$s.TargetPath='{target}';$s.Arguments='{prefix}--tray';"
              f"$s.WorkingDirectory='{os.path.dirname(target)}';"
              f"$s.IconLocation='{sys.executable if FROZEN else ICON_PNG.replace('.png', '.ico')}';"
              f"$s.Description='{APP_NAME}';$s.Save()")
        r = run_hidden(["powershell", "-NoProfile", "-NonInteractive", "-Command", ps])
        if r.returncode != 0:
            raise RuntimeError(r.stderr.strip() or "could not create the Startup shortcut")
    else:
        try:
            os.remove(STARTUP_LNK)
        except FileNotFoundError:
            pass


def set_explorer_menu(enabled):
    """Right-click 'Convert with UltraShot' on .jxl / .jxr files (current user only)."""
    import winreg
    target, prefix = launcher()
    for ext in EXTS:
        key = rf"Software\Classes\SystemFileAssociations\{ext}\shell\UltraShot"
        if enabled:
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, key) as k:
                winreg.SetValueEx(k, "", 0, winreg.REG_SZ, f"Convert with {APP_NAME}")
                winreg.SetValueEx(k, "Icon", 0, winreg.REG_SZ,
                                  f'"{sys.executable}",0' if FROZEN else ICON_PNG.replace(".png", ".ico"))
                winreg.SetValueEx(k, "MultiSelectModel", 0, winreg.REG_SZ, "Player")
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, key + r"\command") as k:
                winreg.SetValueEx(k, "", 0, winreg.REG_SZ, f'"{target}" {prefix}"%1"')
        else:
            for sub in (key + r"\command", key):
                try:
                    winreg.DeleteKey(winreg.HKEY_CURRENT_USER, sub)
                except FileNotFoundError:
                    pass


# ----------------------------------------------------------------------------- single instance

def send_to_running_instance(paths, show=True):
    """True if another UltraShot is running and took over the request."""
    try:
        with socket.create_connection(("127.0.0.1", SINGLE_INSTANCE_PORT), timeout=1.5) as c:
            c.sendall(json.dumps({"app": APP_ID, "paths": paths, "show": show}).encode("utf-8") + b"\n")
            return c.recv(16).startswith(b"ok")
    except OSError:
        return False


class InstanceServer(threading.Thread):
    def __init__(self, app):
        super().__init__(daemon=True, name="instance")
        self.app = app
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 0)
        self.sock.bind(("127.0.0.1", SINGLE_INSTANCE_PORT))
        self.sock.listen(4)

    def run(self):
        while True:
            try:
                conn, _ = self.sock.accept()
                with conn:
                    conn.settimeout(3)
                    data = b""
                    while not data.endswith(b"\n") and len(data) < 1_000_000:
                        chunk = conn.recv(65536)
                        if not chunk:
                            break
                        data += chunk
                    msg = json.loads(data.decode("utf-8") or "{}")
                    if msg.get("app") == APP_ID:
                        conn.sendall(b"ok")
                        self.app.handle_external(msg.get("paths") or [], msg.get("show", True))
            except Exception:
                pass


# ----------------------------------------------------------------------------- app core

class App:
    def __init__(self):
        self.settings, self.first_run = load_settings()
        self.files = OrderedDict()
        self.lock = threading.RLock()
        self.window = None
        self.tray = None
        self.quitting = False
        self.watching = False
        self._visible = True
        self._watch_stop = threading.Event()
        self.cache = OrderedDict()
        self.convert_q = queue.Queue()
        self.thumb_q = queue.Queue()
        self.pending_external = []
        threading.Thread(target=self._convert_loop, daemon=True, name="convert").start()
        threading.Thread(target=self._thumb_loop, daemon=True, name="thumbs").start()

    # ------------------------------------------------------------- bridge to the page
    def emit(self, name, payload=None):
        if not self.window:
            return
        try:
            self.window.evaluate_js(f"window.app && app.on({json.dumps(name)}, {json.dumps(payload)})")
        except Exception:
            pass

    def log(self, msg):
        self.emit("log", {"t": time.strftime("%H:%M:%S"), "msg": str(msg)})

    def toast(self, msg, kind="info"):
        self.emit("toast", {"msg": msg, "kind": kind})

    def notify(self, title, msg):
        if self.tray and not self._visible and self.settings["notifications"]:
            try:
                self.tray.notify(msg, title)
                return
            except Exception:
                pass
        self.toast(msg, "ok")

    def public(self, f):
        return {k: f.get(k) for k in ("id", "name", "path", "size", "status", "stats", "thumb",
                                      "outputs", "error", "added")}

    def state(self):
        with self.lock:
            return {"settings": self.settings, "files": [self.public(f) for f in self.files.values()],
                    "watching": self.watching, "version": VERSION, "codec": jxl2uhdr.ic.__version__,
                    "frozen": FROZEN, "first_run": self.first_run}

    # ------------------------------------------------------------- files
    def add_paths(self, paths, auto_convert=False):
        added = []
        with self.lock:
            existing = {f["path"].lower() for f in self.files.values()}
            for p in collect_images(paths):
                if p.lower() in existing:
                    continue
                fid = uuid.uuid4().hex[:10]
                try:
                    size = os.path.getsize(p)
                except OSError:
                    size = 0
                f = dict(id=fid, name=os.path.basename(p), path=p, size=size, status="queued",
                         stats=None, thumb=None, outputs=[], error=None, added=time.time())
                self.files[fid] = f
                existing.add(p.lower())
                added.append(f)
        for f in added:
            self.emit("file", self.public(f))
            self.thumb_q.put(f["id"])
            if auto_convert:
                self.convert_q.put(f["id"])
        return [f["id"] for f in added]

    def handle_external(self, paths, show):
        """Files from a second launch / Explorer 'Convert with UltraShot'."""
        if show:
            self.show_window()
        if paths:
            ids = self.add_paths(paths, auto_convert=True)
            if ids:
                self.log(f"{len(ids)} file(s) received from Explorer")

    def remove(self, fid):
        with self.lock:
            f = self.files.pop(fid, None)
        if f:
            self.emit("removed", fid)

    def clear(self):
        with self.lock:
            keep = {fid: f for fid, f in self.files.items() if f["status"] == "working"}
            self.files = OrderedDict(keep)
        self.emit("cleared", list(keep.keys()))

    def clear_done(self):
        """Drop finished cards (converted or skipped), keep everything still pending."""
        with self.lock:
            keep = {fid: f for fid, f in self.files.items() if f["status"] not in ("done", "skipped")}
            self.files = OrderedDict(keep)
        self.emit("cleared", list(keep.keys()))

    def convert(self, ids=None):
        with self.lock:
            targets = [self.files[i] for i in (ids or list(self.files.keys())) if i in self.files]
            for f in targets:
                if f["status"] == "working":
                    continue
                f["status"], f["error"] = "queued", None
                self.convert_q.put(f["id"])
        for f in targets:
            self.emit("file", self.public(f))
        return len(targets)

    # ------------------------------------------------------------- preview cache
    def _load_small(self, path):
        mtime = os.path.getmtime(path)
        hit = self.cache.get(path)
        if hit and hit[3] == mtime:
            self.cache.move_to_end(path)
            return hit[:3]
        nits, gamut = jxl2uhdr.load_hdr(path, self.settings["transfer"], log=lambda m: None)
        h, w = nits.shape[:2]
        lum = luminance(nits, gamut)
        stats = dict(w=w, h=h, peak=float(nits.max()), mean=float(nits.mean()),
                     p99=float(np.percentile(lum, 99.5)),
                     above_sdr=float((lum > jxl2uhdr.SDR_WHITE_NITS).mean() * 100.0),
                     above_1k=float((lum > 1000.0).mean() * 100.0),
                     transfer=("scRGB (BT.709)" if gamut == jxl2uhdr.ic.ULTRAHDR.CG.BT_709 else "PQ (BT.2100)")
                     + (" · JXR" if path.lower().endswith(".jxr") else " · JXL"))
        small = jxl2uhdr.resize_linear(nits, PREVIEW_W)
        self.cache[path] = (small, gamut, stats, mtime)
        while len(self.cache) > CACHE_SIZE:
            self.cache.popitem(last=False)
        return small, gamut, stats

    def render(self, small, gamut, width, exposure, knee, auto_sdr=False, crop="none", cx=50, cy=50, heat=False):
        nits = small
        if crop and crop != "none":
            nits = jxl2uhdr.crop_aspect(nits, crop, float(cx), float(cy))
        if nits.shape[1] > width:
            nits = jxl2uhdr.resize_linear(nits, width)
        if auto_sdr:
            rgb = jxl2uhdr.make_sdr(nits, gamut, 0.0, 1.0)[..., :3]
        else:
            rgb = jxl2uhdr.make_sdr(nits, gamut, float(exposure), float(knee))[..., :3]
        if heat:
            lum = luminance(nits, gamut)
            rgbf = rgb.astype(np.float32) * 0.45
            over = (lum > jxl2uhdr.SDR_WHITE_NITS)[..., None]
            hot = (lum > 600.0)[..., None]
            rgbf = np.where(over, rgbf * 0.5 + np.array([255, 150, 20], np.float32) * 0.6, rgbf)
            rgbf = np.where(hot, rgbf * 0.3 + np.array([255, 60, 220], np.float32) * 0.8, rgbf)
            rgb = np.clip(rgbf, 0, 255).astype(np.uint8)
        return jpeg_data_url(rgb), nits.shape[1], nits.shape[0]

    def _thumb_loop(self):
        while True:
            fid = self.thumb_q.get()
            with self.lock:
                f = self.files.get(fid)
            if not f:
                continue
            try:
                small, gamut, stats = self._load_small(f["path"])
                thumb, _, _ = self.render(small, gamut, THUMB_W, self.settings["exposure"],
                                          self.settings["knee"], self.settings["auto_sdr"])
                f["stats"], f["thumb"] = stats, thumb
            except Exception as e:
                f["status"], f["error"] = "failed", f"{type(e).__name__}: {e}"
                self.log(f"cannot read {f['name']}: {e}")
            self.emit("file", self.public(f))

    def preview(self, fid, opts):
        with self.lock:
            f = self.files.get(fid)
        if not f:
            return None
        small, gamut, stats = self._load_small(f["path"])
        s = self.settings
        o = dict(exposure=s["exposure"], knee=s["knee"], auto_sdr=s["auto_sdr"], crop="none",
                 cx=s["crop_x"], cy=s["crop_y"], heat=False, width=PREVIEW_W)
        o.update({k: v for k, v in (opts or {}).items() if v is not None})
        url, w, h = self.render(small, gamut, int(o["width"]), o["exposure"], o["knee"], o["auto_sdr"],
                                o["crop"], o["cx"], o["cy"], o["heat"])
        return {"url": url, "w": w, "h": h, "stats": stats}

    def refresh_thumbs(self):
        with self.lock:
            ids = [f["id"] for f in self.files.values() if f["status"] != "failed"]
        for i in ids:
            self.thumb_q.put(i)

    # ------------------------------------------------------------- conversion
    def output_paths(self, f):
        s = self.settings
        base = s["save_dir"] if (s["save_mode"] == "folder" and s["save_dir"]) else os.path.dirname(f["path"])
        stem = os.path.splitext(f["name"])[0] + (s["suffix"] or "")
        targets = []
        if s["make_full"]:
            targets.append(("full", os.path.join(base, s["full_dir"] or "4K HDR", stem + ".jpg"), {}))
        if s["make_ig"]:
            crop = "" if s["ig_crop"] in ("", "none") else s["ig_crop"]
            targets.append(("ig", os.path.join(base, s["ig_dir"] or "Insta", stem + ".jpg"),
                            dict(crop=crop, crop_x=float(s["crop_x"]), crop_y=float(s["crop_y"]),
                                 max_width=int(s["ig_width"]))))
        return targets

    def _convert_file(self, f):
        s = self.settings
        targets = self.output_paths(f)
        if not targets:
            raise RuntimeError("no outputs enabled (Settings → Output)")
        todo = [t for t in targets if s["overwrite"] or not os.path.exists(t[1])]
        if not todo:
            self.log(f"skip {f['name']}: outputs already exist")
            return [t[1] for t in targets], False
        t0 = time.time()
        nits, gamut = jxl2uhdr.load_hdr(f["path"], s["transfer"], log=self.log)
        written = []
        for kind, out, extra in todo:
            os.makedirs(os.path.dirname(out), exist_ok=True)
            jxl2uhdr.encode_uhdr(nits, gamut, out, exposure=float(s["exposure"]), knee=float(s["knee"]),
                                 auto_sdr=bool(s["auto_sdr"]), quality=int(s["quality"]),
                                 peak_nits=float(s["peak_nits"]), log=self.log, **extra)
            if s["keep_date"]:
                try:
                    st = os.stat(f["path"])
                    os.utime(out, (st.st_atime, st.st_mtime))
                except OSError:
                    pass
            written.append(out)
        self.log(f"done {f['name']} in {time.time() - t0:.1f}s")
        return written, True

    def _convert_loop(self):
        while True:
            fid = self.convert_q.get()
            with self.lock:
                f = self.files.get(fid)
                if not f or f["status"] != "queued":
                    continue
                f["status"] = "working"
            self.emit("file", self.public(f))
            try:
                outputs, did = self._convert_file(f)
                f["outputs"] = outputs
                f["status"] = "done" if did else "skipped"
            except Exception as e:
                f["status"], f["error"] = "failed", f"{type(e).__name__}: {e}"
                self.log(f"FAILED {f['name']}:\n{traceback.format_exc()}")
            self.emit("file", self.public(f))
            if self.convert_q.empty():
                self.emit("idle")
                if f["status"] == "done":
                    self.notify(APP_NAME, f"{f['name']} is ready")
                elif f["status"] == "failed":
                    self.notify(APP_NAME, f"{f['name']} failed: {f['error']}")

    # ------------------------------------------------------------- watch folder
    def set_watch(self, on):
        on = bool(on)
        if on == self.watching:
            return self.watching
        if on:
            folder = self.settings["watch_dir"]
            if not os.path.isdir(folder):
                self.toast(f"Watch folder does not exist: {folder}", "err")
                self.settings["watch"] = False
                save_settings(self.settings)
                self.emit("settings", self.settings)
                return False
            self._watch_stop.clear()
            threading.Thread(target=self._watch_loop, args=(folder,), daemon=True, name="watch").start()
            self.watching = True
        else:
            self._watch_stop.set()
            self.watching = False
        self.settings["watch"] = on
        save_settings(self.settings)
        self.emit("watch", {"on": self.watching, "dir": self.settings["watch_dir"]})
        if self.tray:
            try:
                self.tray.update_menu()
            except Exception:
                pass
        return self.watching

    def _watch_candidates(self, folder):
        """Capture files in the watch folder (and, if enabled, two levels of subfolders),
        skipping the output subfolders."""
        s = self.settings
        skip = {s["full_dir"].lower(), s["ig_dir"].lower()}
        out = []
        depth_limit = 2 if s["watch_subfolders"] else 0
        for root, dirs, files in os.walk(folder):
            depth = 0 if root == folder else os.path.relpath(root, folder).count(os.sep) + 1
            if depth >= depth_limit:
                dirs[:] = []
            else:
                dirs[:] = [d for d in dirs if d.lower() not in skip and not d.startswith(".")]
            out.extend(os.path.join(root, f) for f in files if is_hdr_image(f))
        return sorted(out)

    def _watch_loop(self, folder):
        seen, done = {}, set()
        if not self.settings["watch_existing"]:
            try:
                done.update(self._watch_candidates(folder))
            except OSError:
                pass
        self.log(f"watching {folder}" + (" + subfolders" if self.settings["watch_subfolders"] else "")
                 + ("" if self.settings["watch_existing"] else f" (ignoring {len(done)} existing capture(s))"))
        stop = self._watch_stop
        while not stop.is_set():
            try:
                for path in self._watch_candidates(folder):
                    if path in done:
                        continue
                    try:
                        size = os.path.getsize(path)
                    except OSError:
                        continue
                    now = time.time()
                    last, since = seen.get(path, (None, now))
                    if size != last or size == 0:
                        seen[path] = (size, now)
                        continue
                    if now - since < float(self.settings["settle"]):
                        continue
                    try:
                        with open(path, "rb"):
                            pass
                    except OSError:
                        continue
                    done.add(path)
                    seen.pop(path, None)
                    self.log(f"new capture: {os.path.relpath(path, folder)}")
                    self.add_paths([path], auto_convert=True)
            except Exception:
                self.log(f"watch error:\n{traceback.format_exc()}")
            stop.wait(float(self.settings["interval"]))
        self.log("watch stopped")

    # ------------------------------------------------------------- settings
    def set_settings(self, patch):
        patch = patch or {}
        look_changed = False
        with self.lock:
            for k, v in patch.items():
                if k not in DEFAULTS:
                    continue
                d = DEFAULTS[k]
                try:
                    v = bool(v) if isinstance(d, bool) else type(d)(v)
                except (TypeError, ValueError):
                    continue
                if k in ("exposure", "knee", "auto_sdr", "transfer") and self.settings[k] != v:
                    look_changed = True
                self.settings[k] = v
            save_settings(self.settings)
        if "startup" in patch:
            try:
                set_startup(self.settings["startup"])
            except Exception as e:
                self.toast(f"Could not change the startup shortcut: {e}", "err")
        if "explorer_menu" in patch:
            try:
                set_explorer_menu(self.settings["explorer_menu"])
            except Exception as e:
                self.toast(f"Could not change the Explorer menu: {e}", "err")
        if "watch" in patch:
            self.set_watch(self.settings["watch"])
        if ("watch_dir" in patch or "watch_subfolders" in patch) and self.watching:
            self.set_watch(False)
            self.set_watch(True)
        if "transfer" in patch:
            self.cache.clear()
        if look_changed:
            self.refresh_thumbs()
        return self.settings

    def apply_integrations(self):
        """Keep the Startup shortcut / Explorer entries pointing at this copy of the app."""
        for key, fn in (("startup", set_startup), ("explorer_menu", set_explorer_menu)):
            if self.settings[key]:
                try:
                    fn(True)
                except Exception as e:
                    self.log(f"could not refresh {key}: {e}")

    # ------------------------------------------------------------- window / tray
    def on_drop(self, e):
        files = (e or {}).get("dataTransfer", {}).get("files", []) or []
        paths = [f.get("pywebviewFullPath") for f in files if f.get("pywebviewFullPath")]
        if paths:
            if not self.add_paths(paths):
                self.toast("Nothing new: only .jxl and .jxr files are converted", "warn")
        else:
            self.toast("Drop .jxl or .jxr files, or folders", "warn")

    def on_closing(self):
        self.save_geometry()
        if self.quitting or not self.settings["tray"] or not self.tray:
            self.shutdown()
            return True
        self.hide_window()
        if self.settings["notifications"]:
            try:
                self.tray.notify("Still running in the tray. Right-click the icon to quit.", APP_NAME)
            except Exception:
                pass
        return False

    def save_geometry(self):
        try:
            w, h, x, y = self.window.width, self.window.height, self.window.x, self.window.y
            if w > 300 and h > 300 and x > -10000 and y > -10000:
                self.settings.update(win_w=w, win_h=h, win_x=x, win_y=y)
                save_settings(self.settings)
        except Exception:
            pass

    def hide_window(self):
        self._visible = False
        try:
            self.window.hide()
        except Exception:
            pass

    def show_window(self):
        self._visible = True
        try:
            self.window.show()
            self.window.restore()
        except Exception:
            pass

    def shutdown(self):
        self.quitting = True
        self._watch_stop.set()
        if self.tray:
            try:
                self.tray.stop()
            except Exception:
                pass

    def quit(self):
        self.save_geometry()
        self.shutdown()
        try:
            self.window.destroy()
        except Exception:
            pass

    def make_tray(self):
        try:
            import pystray
        except ImportError:
            return
        try:
            img = Image.open(ICON_PNG).convert("RGBA")
        except Exception:
            img = Image.new("RGBA", (64, 64), (79, 140, 255, 255))
        menu = pystray.Menu(
            pystray.MenuItem(f"Open {APP_NAME}", lambda *a: self.show_window(), default=True),
            pystray.MenuItem("Watch folder", lambda *a: self.set_watch(not self.watching),
                             checked=lambda item: self.watching),
            pystray.MenuItem("Open watch folder", lambda *a: os.startfile(self.settings["watch_dir"])),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Quit", lambda *a: self.quit()),
        )
        self.tray = pystray.Icon(APP_ID, img, APP_NAME, menu)
        try:
            self.tray.run_detached()
        except Exception:
            self.tray = None


# ----------------------------------------------------------------------------- JS API

class Api:
    def __init__(self, app: App):
        self._app = app

    def _dialog(self, folder=False):
        fd = getattr(webview, "FileDialog", None)
        if folder:
            return fd.FOLDER if fd else webview.FOLDER_DIALOG
        return fd.OPEN if fd else webview.OPEN_DIALOG

    def state(self):
        return self._app.state()

    def pick_files(self):
        res = self._app.window.create_file_dialog(
            self._dialog(), allow_multiple=True, directory=self._app.settings["watch_dir"],
            file_types=("HDR screenshots (*.jxl;*.jxr)", "JPEG XL (*.jxl)", "JPEG XR (*.jxr)", "All files (*.*)"))
        return self._app.add_paths(list(res or []))

    def pick_folder(self):
        res = self._app.window.create_file_dialog(self._dialog(True), directory=self._app.settings["watch_dir"])
        return self._app.add_paths(list(res or []))

    def choose_dir(self, key):
        start = self._app.settings.get(key) or self._app.settings["watch_dir"]
        res = self._app.window.create_file_dialog(self._dialog(True),
                                                  directory=start if os.path.isdir(start) else "")
        if res:
            self._app.set_settings({key: res[0]})
            return res[0]
        return None

    def add_paths(self, paths):
        return self._app.add_paths(paths or [])

    def remove(self, fid):
        self._app.remove(fid)

    def clear(self):
        self._app.clear()

    def clear_done(self):
        self._app.clear_done()

    def convert(self, ids=None):
        return self._app.convert(ids)

    def preview(self, fid, opts=None):
        try:
            return self._app.preview(fid, opts)
        except Exception as e:
            return {"error": f"{type(e).__name__}: {e}"}

    def set_settings(self, patch):
        return self._app.set_settings(patch)

    def set_watch(self, on):
        return self._app.set_watch(on)

    def open_path(self, path):
        if path and os.path.exists(path):
            os.startfile(path)
            return True
        return False

    def reveal(self, path):
        if path and os.path.exists(path):
            subprocess.Popen(["explorer", "/select,", os.path.normpath(path)])
            return True
        return False

    def output_image(self, fid, which="ig"):
        """The finished Ultra HDR JPEG of a card as a data URL for the in-app viewer.
        which: 'ig' (the Instagram copy, small and quick) or 'full' (the full-size file)."""
        app = self._app
        f = app.files.get(fid)
        outs = [o for o in (f or {}).get("outputs", []) if os.path.exists(o)]
        if not outs:
            return None
        s = app.settings
        want = (s["ig_dir"] if which == "ig" else s["full_dir"]).lower()
        pick = next((o for o in outs if os.path.basename(os.path.dirname(o)).lower() == want), outs[0])
        with open(pick, "rb") as fh:
            data = fh.read()
        kind = "full" if os.path.basename(os.path.dirname(pick)).lower() == s["full_dir"].lower() else "ig"
        return {"url": "data:image/jpeg;base64," + base64.b64encode(data).decode("ascii"),
                "path": pick, "size": len(data), "which": kind,
                "has_full": any(os.path.basename(os.path.dirname(o)).lower() == s["full_dir"].lower() for o in outs),
                "has_ig": any(os.path.basename(os.path.dirname(o)).lower() == s["ig_dir"].lower() for o in outs)}

    def output_dir(self, fid=None):
        app = self._app
        f = app.files.get(fid) if fid else None
        if f and f.get("outputs"):
            return os.path.dirname(f["outputs"][0])
        if f:
            t = app.output_paths(f)
            return os.path.dirname(t[0][1]) if t else os.path.dirname(f["path"])
        s = app.settings
        return s["save_dir"] if (s["save_mode"] == "folder" and s["save_dir"]) else s["watch_dir"]

    def hide(self):
        self._app.hide_window()

    def minimize(self):
        self._app.window.minimize()

    def quit(self):
        self._app.quit()


# ----------------------------------------------------------------------------- main

def main():
    args = sys.argv[1:]
    start_hidden = "--tray" in args
    initial = collect_images([a for a in args if not a.startswith("--")])

    # hand over to an instance that is already running (e.g. in the tray)
    if "--new-instance" not in args and send_to_running_instance(initial, show=not start_hidden):
        return

    app = App()
    try:
        server = InstanceServer(app)
        server.start()
    except OSError:
        pass
    api = Api(app)
    s = app.settings
    kw = dict(width=int(s["win_w"]), height=int(s["win_h"]))
    if s["win_x"] >= 0 and s["win_y"] >= 0:
        kw.update(x=int(s["win_x"]), y=int(s["win_y"]))
    window = webview.create_window(APP_NAME, os.path.join(UI_DIR, "index.html"), js_api=api,
                                   min_size=(960, 640), background_color="#0e1014",
                                   hidden=start_hidden, text_select=False, **kw)
    app.window = window
    app._visible = not start_hidden
    window.events.closing += app.on_closing

    def on_loaded():
        window.dom.document.events.drop += app.on_drop
        if initial:
            app.add_paths(initial, auto_convert=True)
        if s["watch"]:
            app.set_watch(True)
        if app.first_run:
            save_settings(s)
            app.toast(f"Watching {s['watch_dir']} — new captures convert automatically", "ok")
        threading.Thread(target=app.apply_integrations, daemon=True).start()

    window.events.loaded += on_loaded
    app.make_tray()
    webview.start(private_mode=False, storage_path=SETTINGS_DIR, debug="--debug" in args)
    app.shutdown()


if __name__ == "__main__":
    main()
