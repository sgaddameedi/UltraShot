"""The video editor's state and the calls the page makes, on top of hdrvideo and mediaserver.

One VideoSession lives in the app. It holds the opened recordings with their probes, hands the
player a streaming URL for each, answers frame and keyframe requests from the timeline, builds a
preview proxy when the player cannot decode a file, and runs exports on a worker thread with
progress events. Nothing is persisted: a recording is a reference to a file on disk, and the only
things written are the proxies in the local cache (size-capped) and the exported files.
"""
import base64
import hashlib
import os
import shutil
import threading
import time
import uuid
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor

import hdrvideo as V
from mediaserver import MediaServer

PROXY_DIR = os.path.join(V.LOCALAPPDATA, "UltraShot", "proxies")
PROXY_CACHE_BYTES = 6 * 1024 ** 3     # the proxy cache never grows past this; oldest go first


class VideoSession:
    def __init__(self, app):
        self.app = app
        self.lock = threading.RLock()
        self.videos = OrderedDict()
        self.server = None
        self.ff = V.find_ffmpeg()
        self.pool = ThreadPoolExecutor(max_workers=3, thread_name_prefix="video")
        self.job = None
        self.cancel = threading.Event()

    # ------------------------------------------------------------- helpers
    def _emit(self, name, payload=None):
        self.app.emit(name, payload)

    def _log(self, msg):
        self.app.log(msg)

    def _server(self):
        if self.server is None:
            self.server = MediaServer()
        return self.server

    def _need_ff(self):
        if not self.ff:
            self.ff = V.find_ffmpeg()
        if not self.ff:
            raise RuntimeError("FFmpeg is needed for video. Use \"Get FFmpeg\" in the editor, or install it with winget install Gyan.FFmpeg")
        return self.ff

    def close(self):
        """Stop streaming and drop the worker pool; exports in flight finish on their own thread."""
        if self.server:
            self.server.close()
            self.server = None
        self.pool.shutdown(wait=False, cancel_futures=True)

    def ffmpeg_status(self):
        ff = V.find_ffmpeg()
        self.ff = ff
        return {"found": bool(ff), "path": ff[0] if ff else None, "version": V.ffmpeg_version(ff[0]) if ff else None}

    def ffmpeg_install(self):
        def run():
            try:
                self.ff = V.install_ffmpeg(progress=lambda pct, msg: self._emit("video_progress", {"kind": "ffmpeg", "pct": pct, "msg": msg}), log=self._log)
                self._emit("video_ffmpeg", self.ffmpeg_status())
            except Exception as e:
                self._log(f"FFmpeg install failed: {e}")
                self._emit("video_ffmpeg", {"found": False, "error": str(e)})
        threading.Thread(target=run, daemon=True, name="ffmpeg-install").start()
        return True

    def public(self, v):
        return {k: v.get(k) for k in ("id", "path", "name", "size", "url", "proxy_url", "status", "error", "info", "thumb")}

    def state(self):
        with self.lock:
            return {"videos": [self.public(v) for v in self.videos.values()], "ffmpeg": self.ffmpeg_status(),
                    "job": self.job, "proxy_dir": PROXY_DIR}

    # ------------------------------------------------------------- opening files
    def add_paths(self, paths):
        added = []
        with self.lock:
            have = {v["path"].lower() for v in self.videos.values()}
            for p in paths:
                p = os.path.abspath(p)
                if not os.path.isfile(p) or not p.lower().endswith(V.VIDEO_EXTS) or p.lower() in have:
                    continue
                vid = uuid.uuid4().hex[:10]
                v = dict(id=vid, path=p, name=os.path.basename(p), size=os.path.getsize(p), url=self._server().register(p),
                         proxy_url=None, status="probing", error=None, info=None, thumb=None)
                self.videos[vid] = v
                have.add(p.lower()); added.append(v)
        for v in added:
            self._emit("video_file", self.public(v))
            self.pool.submit(self._probe, v["id"])
        return [v["id"] for v in added]

    def _probe(self, vid):
        v = self.videos.get(vid)
        if not v:
            return
        try:
            ff, fp = self._need_ff()
            v["info"] = V.probe(fp, v["path"])
            self._log(f"opened {v['name']}: {v['info']['summary']}, {v['info']['duration']:.1f} s")
            try:
                v["thumb"] = "data:image/jpeg;base64," + base64.b64encode(V.frame_at(ff, v["path"], min(1.0, v["info"]["duration"] / 2), v["info"], 480)).decode("ascii")
            except Exception as e:
                self._log(f"no thumbnail for {v['name']}: {e}")
            v["status"] = "ready"       # last, so a reader that sees "ready" also sees the probe and the thumbnail
        except Exception as e:
            v["status"], v["error"] = "failed", str(e)
            self._log(f"cannot open {v['name']}: {e}")
        self._emit("video_file", self.public(v))

    def remove(self, vid):
        with self.lock:
            v = self.videos.pop(vid, None)
        if v:
            self._server().unregister(v["path"])
            self._emit("video_removed", vid)
        return True

    # ------------------------------------------------------------- timeline services
    def _get(self, vid):
        v = self.videos.get(vid)
        if not v or not v.get("info"):
            raise RuntimeError("that recording is not open")
        return v

    def frame(self, vid, t, width=640):
        v = self._get(vid); ff, _ = self._need_ff()
        data = V.frame_at(ff, v["path"], float(t), v["info"], int(width))
        return {"t": float(t), "url": "data:image/jpeg;base64," + base64.b64encode(data).decode("ascii")}

    def filmstrip(self, vid, count=12, width=320):
        """Evenly spaced frames across the recording, grabbed in parallel."""
        v = self._get(vid); ff, _ = self._need_ff()
        d = v["info"]["duration"]
        times = [d * (i + 0.5) / count for i in range(int(count))]
        def grab(t):
            try:
                return {"t": t, "url": "data:image/jpeg;base64," + base64.b64encode(V.frame_at(ff, v["path"], t, v["info"], int(width), quality=6)).decode("ascii")}
            except Exception as e:
                return {"t": t, "url": None, "error": str(e)}
        return list(self.pool.map(grab, times))

    def keyframes(self, vid, t, span=6.0):
        v = self._get(vid); _, fp = self._need_ff()
        return V.keyframes_near(fp, v["path"], float(t), float(span), v["info"].get("start", 0.0))

    def snap(self, vid, t, direction="nearest"):
        v = self._get(vid); _, fp = self._need_ff()
        st, ks = V.snap(fp, v["path"], float(t), direction, start=v["info"].get("start", 0.0))
        return {"t": st, "keyframes": ks}

    # ------------------------------------------------------------- proxies
    def proxy(self, vid):
        """Build (or fetch from the cache) a small SDR proxy for a file the player cannot decode."""
        v = self._get(vid)
        key = hashlib.sha1(f"{v['path'].lower()}|{v['size']}|{int(os.path.getmtime(v['path']))}".encode("utf-8", "replace")).hexdigest()[:20]
        os.makedirs(PROXY_DIR, exist_ok=True)
        dst = os.path.join(PROXY_DIR, key + ".mp4")
        if os.path.exists(dst) and os.path.getsize(dst) > 0:
            os.utime(dst, None)
            v["proxy_url"] = self._server().register(dst)
            self._emit("video_file", self.public(v))
            return {"url": v["proxy_url"], "cached": True}
        def run():
            try:
                ff, _ = self._need_ff()
                tmp = dst[:-4] + ".part.mp4"     # keeps the extension FFmpeg picks the muxer from
                V.make_proxy(ff, v["info"], tmp, progress=lambda pct: self._emit("video_progress", {"kind": "proxy", "id": vid, "pct": pct, "msg": "building a preview copy"}), log=self._log)
                os.replace(tmp, dst)
                self._trim_cache()
                v["proxy_url"] = self._server().register(dst)
                self._emit("video_file", self.public(v))
            except Exception as e:
                self._log(f"proxy failed for {v['name']}: {e}")
                self._emit("video_progress", {"kind": "proxy", "id": vid, "pct": 0, "msg": f"preview copy failed: {e}", "error": True})
        threading.Thread(target=run, daemon=True, name="proxy").start()
        return {"url": None, "cached": False}

    def _trim_cache(self):
        try:
            files = [(os.path.getmtime(os.path.join(PROXY_DIR, f)), os.path.join(PROXY_DIR, f)) for f in os.listdir(PROXY_DIR) if f.endswith(".mp4")]
            total = sum(os.path.getsize(p) for _, p in files)
            for _, p in sorted(files):
                if total <= PROXY_CACHE_BYTES:
                    break
                total -= os.path.getsize(p)
                os.remove(p)
                self._log(f"proxy cache: removed {os.path.basename(p)} to stay under {PROXY_CACHE_BYTES // 1024 ** 3} GB")
        except OSError:
            pass

    # ------------------------------------------------------------- export
    def export(self, segments, join, out_dir, name, frame=None):
        """segments: [{id, start, end}]. Snaps each start to its keyframe again, cuts by stream
        copy, joins when asked, then verifies every output against its source."""
        if self.job and self.job.get("running"):
            raise RuntimeError("an export is already running")
        ff, fp = self._need_ff()
        segs = []
        for s in segments:
            v = self._get(s["id"])
            start, _ = V.snap(fp, v["path"], float(s["start"]), "nearest", start=v["info"].get("start", 0.0))
            end = float(s["end"])
            if end <= start:
                raise RuntimeError("a segment ends before it starts")
            segs.append({"info": v["info"], "start": start, "end": end, "vid": v["id"]})
        if join and len(segs) > 1:
            for a, b in zip(segs, segs[1:]):
                if not V.compatible(a["info"], b["info"]):
                    raise RuntimeError(f"{a['info']['name']} and {b['info']['name']} have different streams and cannot be joined without re-encoding")
        out_dir = out_dir or os.path.dirname(segs[0]["info"]["path"])
        frame = frame if isinstance(frame, dict) and frame.get("frame") in V.FRAMES else None
        if frame:
            frame = {"frame": frame["frame"], "cx": min(max(float(frame.get("cx", 0.5)), 0.0), 1.0), "cy": min(max(float(frame.get("cy", 0.5)), 0.0), 1.0),
                     "size": "upload" if frame.get("size") == "upload" else "full"}
        self.job = {"running": True, "pct": 0.0, "msg": "starting", "outputs": [], "verify": [], "error": None, "started": time.time(), "frame": frame}
        self.cancel.clear()
        encoder_used = []
        def log(msg):
            # the reframe says which encoder it ended up with; keep that for the report
            if msg.startswith("reframe ") and " with " in msg:
                encoder_used.append(msg.rsplit(" with ", 1)[1])
            elif msg.endswith("trying the next encoder") and encoder_used:
                encoder_used.pop()
            self._log(msg)
        def run():
            try:
                outs = V.export(ff, fp, segs, bool(join), out_dir, name,
                                progress=lambda pct, msg: self._progress(pct, msg), log=log, frame=frame)
                reports = []
                for i, o in enumerate(outs):
                    src = segs[0]["info"] if join else segs[i]["info"]
                    self._progress(99.0, f"verifying {os.path.basename(o)}")
                    expect = None
                    plan = V.reframe_plan(src, frame["frame"], frame["cx"], frame["cy"], frame["size"]) if frame else None
                    if plan and plan["changes"]:
                        enc = encoder_used[i] if i < len(encoder_used) else (encoder_used[-1] if encoder_used else "")
                        expect = {"codec": "av1" if "AV1" in enc else "hevc", "size": plan["size"]}
                    rep = V.verify(fp, src, o, expect)
                    reports.append({"output": o, "size": os.path.getsize(o), "duration": rep["output"]["duration"], "summary": rep["output"]["summary"],
                                    "rows": rep["rows"], "all_ok": rep["all_ok"],
                                    "reframed": {"frame": frame["frame"], "size": list(plan["size"]), "encoder": enc} if expect else None})
                    self._log(f"verified {os.path.basename(o)}: {'everything matches the source' if rep['all_ok'] else 'differences found'}")
                self.job.update(running=False, pct=100.0, msg="done", outputs=outs, verify=reports)
                self._emit("video_done", self.job)
            except Exception as e:
                self.job.update(running=False, error=str(e), msg="failed")
                self._log(f"export failed: {e}")
                self._emit("video_done", self.job)
        threading.Thread(target=run, daemon=True, name="video-export").start()
        return self.job

    def _progress(self, pct, msg):
        if self.job:
            self.job["pct"], self.job["msg"] = float(pct), msg
            self._emit("video_progress", {"kind": "export", "pct": float(pct), "msg": msg})
