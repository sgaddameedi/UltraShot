"""The editor's session layer and the local media server, driven the way the page drives them:
open a recording, read frames and keyframes, stream it with range requests, export and verify.
Skipped when FFmpeg is not installed."""
import os
import threading
import time
import urllib.request

import pytest

import hdrvideo as V
import videoedit
from mediaserver import MediaServer

FF = V.find_ffmpeg()
pytestmark = pytest.mark.skipif(FF is None, reason="FFmpeg is not installed")


class FakeApp:
    """Collects the events and log lines the real App would push to the page."""
    def __init__(self):
        self.events, self.lines = [], []
        self.lock = threading.Lock()

    def emit(self, name, payload=None):
        with self.lock:
            self.events.append((name, payload))

    def log(self, msg):
        self.lines.append(msg)

    def named(self, name):
        with self.lock:
            return [p for n, p in self.events if n == name]


@pytest.fixture(scope="module")
def clip(tmp_path_factory):
    d = tmp_path_factory.mktemp("videoedit")
    p = str(d / "hdr10.mp4")
    V.make_test_clip(FF[0], p, seconds=6, fps=30, gop=30)
    return p


@pytest.fixture
def session(tmp_path, monkeypatch):
    monkeypatch.setattr(videoedit, "PROXY_DIR", str(tmp_path / "proxies"))
    app = FakeApp()
    s = videoedit.VideoSession(app)
    yield s, app
    if s.server:
        s.server.close()


def wait(cond, timeout=60):
    t = time.time()
    while time.time() - t < timeout:
        if cond():
            return True
        time.sleep(0.1)
    return False


def test_open_probes_and_thumbnails(session, clip):
    s, app = session
    ids = s.add_paths([clip, clip, "not-a-video.txt"])
    assert len(ids) == 1, "duplicates and non-video files are ignored"
    assert wait(lambda: s.videos[ids[0]]["status"] in ("ready", "failed"))
    v = s.videos[ids[0]]
    assert v["status"] == "ready", v["error"]
    assert v["info"]["hdr"]["kind"] == "PQ" and v["thumb"].startswith("data:image/jpeg;base64,")
    assert v["url"].startswith("http://127.0.0.1:")
    files = app.named("video_file")
    assert files[0]["status"] == "probing" and files[-1]["status"] == "ready"
    st = s.state()
    assert st["videos"][0]["id"] == ids[0] and st["ffmpeg"]["found"]


def test_timeline_services(session, clip):
    s, _ = session
    vid = s.add_paths([clip])[0]
    assert wait(lambda: s.videos[vid]["status"] == "ready")
    fr = s.frame(vid, 1.5, 320)
    assert fr["url"].startswith("data:image/jpeg;base64,") and fr["t"] == 1.5
    strip = s.filmstrip(vid, 4, 160)
    assert len(strip) == 4 and all(f["url"] for f in strip) and strip[0]["t"] < strip[-1]["t"]
    snap = s.snap(vid, 2.4, "nearest")
    assert abs(snap["t"] - 2.0) < 0.02 and any(abs(k - 3.0) < 0.02 for k in snap["keyframes"])
    assert any(abs(k - 1.0) < 0.02 for k in s.keyframes(vid, 1.0, 2.0))


def test_media_server_streams_with_ranges(session, clip):
    s, _ = session
    vid = s.add_paths([clip])[0]
    url = s.videos[vid]["url"]
    size = os.path.getsize(clip)
    req = urllib.request.Request(url, headers={"Range": "bytes=10-19"})
    with urllib.request.urlopen(req, timeout=10) as r:
        assert r.status == 206 and r.headers["Content-Range"] == f"bytes 10-19/{size}" and len(r.read()) == 10
    with urllib.request.urlopen(urllib.request.Request(url, method="HEAD"), timeout=10) as r:
        assert r.status == 200 and int(r.headers["Content-Length"]) == size and r.headers["Accept-Ranges"] == "bytes"
    with open(clip, "rb") as fh:
        fh.seek(10)
        expect = fh.read(10)
    with urllib.request.urlopen(req, timeout=10) as r:
        assert r.read() == expect
    s.remove(vid)
    with pytest.raises(urllib.error.HTTPError) as e:
        urllib.request.urlopen(url, timeout=10)
    assert e.value.code == 404, "a removed recording is no longer reachable"
    bogus = url.rsplit("/", 1)[0] + "/nope"
    with pytest.raises(urllib.error.HTTPError) as e:
        urllib.request.urlopen(bogus, timeout=10)
    assert e.value.code == 404


def test_export_cuts_joins_and_verifies(session, clip, tmp_path):
    s, app = session
    vid = s.add_paths([clip])[0]
    assert wait(lambda: s.videos[vid]["status"] == "ready")
    out = str(tmp_path / "out")
    job = s.export([{"id": vid, "start": 1.0, "end": 2.0}, {"id": vid, "start": 4.0, "end": 5.0}], True, out, "joined")
    assert job["running"]
    with pytest.raises(RuntimeError):
        s.export([{"id": vid, "start": 0.0, "end": 1.0}], False, out, "")
    assert wait(lambda: not s.job["running"], 180)
    assert s.job["error"] is None, s.job["error"]
    assert [os.path.basename(o) for o in s.job["outputs"]] == ["joined.mp4"]
    rep = s.job["verify"][0]
    assert rep["all_ok"], [r for r in rep["rows"] if not r["ok"]]
    assert abs(rep["duration"] - 2.0) < 0.1
    done = app.named("video_done")
    assert done and done[-1]["outputs"] == s.job["outputs"]
    assert any(p["kind"] == "export" for p in app.named("video_progress"))
    # separate files, next to the source when no folder is given
    job = s.export([{"id": vid, "start": 0.0, "end": 1.0}, {"id": vid, "start": 3.0, "end": 4.0}], False, "", "")
    assert wait(lambda: not s.job["running"], 180) and s.job["error"] is None
    assert len(s.job["outputs"]) == 2 and all(os.path.dirname(o) == os.path.dirname(clip) for o in s.job["outputs"])
    for o in s.job["outputs"]:
        os.remove(o)


def test_export_rejects_bad_segments(session, clip, tmp_path):
    s, _ = session
    vid = s.add_paths([clip])[0]
    assert wait(lambda: s.videos[vid]["status"] == "ready")
    with pytest.raises(RuntimeError):
        s.export([{"id": vid, "start": 3.0, "end": 2.0}], False, str(tmp_path), "")
    with pytest.raises(RuntimeError):
        s.export([{"id": "missing", "start": 0.0, "end": 1.0}], False, str(tmp_path), "")


def test_proxy_is_built_once_and_cached(session, clip, tmp_path):
    s, app = session
    vid = s.add_paths([clip])[0]
    assert wait(lambda: s.videos[vid]["status"] == "ready")
    first = s.proxy(vid)
    assert first == {"url": None, "cached": False}
    assert wait(lambda: s.videos[vid]["proxy_url"] is not None, 180)
    again = s.proxy(vid)
    assert again["cached"] and again["url"] == s.videos[vid]["proxy_url"]
    files = os.listdir(videoedit.PROXY_DIR)
    assert len(files) == 1 and files[0].endswith(".mp4")
    info = V.probe(FF[1], os.path.join(videoedit.PROXY_DIR, files[0]))
    assert info["video"]["codec"] == "h264" and info["video"]["bit_depth"] == 8


def test_media_server_registers_each_path_once():
    srv = MediaServer()
    try:
        a = srv.register(__file__)
        assert srv.register(__file__) == a
        srv.unregister(__file__)
        assert srv.register(__file__) != a
    finally:
        srv.close()


def test_export_reframes_when_asked(session, clip, tmp_path):
    s, app = session
    vid = s.add_paths([clip])[0]
    assert wait(lambda: s.videos[vid]["status"] == "ready")
    out = str(tmp_path / "framed")
    job = s.export([{"id": vid, "start": 1.0, "end": 3.0}], False, out, "", {"frame": "9:16", "cx": 0.8, "cy": 0.5, "size": "upload"})
    assert job["frame"] == {"frame": "9:16", "cx": 0.8, "cy": 0.5, "size": "upload"}
    assert wait(lambda: not s.job["running"], 300) and s.job["error"] is None, s.job["error"]
    assert [os.path.basename(o) for o in s.job["outputs"]] == ["hdr10-cut-9x16.mp4"] and os.listdir(out) == ["hdr10-cut-9x16.mp4"]
    rep = s.job["verify"][0]
    assert rep["all_ok"], [r for r in rep["rows"] if not r["ok"]]
    assert rep["reframed"]["frame"] == "9:16" and rep["reframed"]["size"] == [202, 360] and rep["reframed"]["encoder"]
    assert any(r["label"] == "Resolution" and r["output"] == "202×360" and r["ok"] for r in rep["rows"])
    # an unknown frame is ignored rather than failing the export
    job = s.export([{"id": vid, "start": 1.0, "end": 2.0}], False, out, "", {"frame": "3:2"})
    assert job["frame"] is None and wait(lambda: not s.job["running"], 180) and s.job["verify"][0]["reframed"] is None
