"""Lossless video editing: cuts land on keyframes, nothing is re-encoded, and every HDR tag and
metadata block survives a trim and a join. Skipped when FFmpeg is not installed."""
import hashlib
import os
import subprocess

import pytest

import hdrvideo as V

FF = V.find_ffmpeg()
pytestmark = pytest.mark.skipif(FF is None, reason="FFmpeg is not installed")


@pytest.fixture(scope="module")
def clip(tmp_path_factory):
    d = tmp_path_factory.mktemp("video")
    p = str(d / "hdr10.mp4")
    V.make_test_clip(FF[0], p, seconds=6, fps=30, gop=30)
    return p


def raw_frame(path, t):
    """The decoded 10-bit frame at t, as bytes, for bit-exact comparison."""
    r = subprocess.run([FF[0], "-v", "error", "-ss", f"{t:.3f}", "-i", path, "-frames:v", "1", "-f", "rawvideo", "-pix_fmt", "yuv420p10le", "-"],
                       capture_output=True, creationflags=V.CREATE_NO_WINDOW, timeout=120)
    assert r.returncode == 0 and r.stdout, r.stderr
    return hashlib.sha1(r.stdout).hexdigest()


def test_probe_reports_hdr10(clip):
    info = V.probe(FF[1], clip)
    assert info["video"]["codec"] == "hevc" and info["video"]["bit_depth"] == 10
    assert info["hdr"]["kind"] == "PQ" and info["hdr"]["primaries"] == "bt2020"
    assert info["hdr"]["max_cll"] == 1000 and info["hdr"]["max_fall"] == 400
    assert info["hdr"]["mastering"] and info["is_hdr"]
    assert "HDR10" in info["summary"] and "HEVC 10-bit" in info["summary"]
    assert abs(info["duration"] - 6.0) < 0.2 and len(info["audio"]) == 1


def test_keyframes_are_found_and_snapped(clip):
    ks = V.keyframes_near(FF[1], clip, 3.0, span=3.0)
    assert any(abs(k - 2.0) < 0.02 for k in ks) and any(abs(k - 3.0) < 0.02 for k in ks)
    t, _ = V.snap(FF[1], clip, 2.4, "nearest"); assert abs(t - 2.0) < 0.02
    t, _ = V.snap(FF[1], clip, 2.4, "next"); assert abs(t - 3.0) < 0.02
    t, _ = V.snap(FF[1], clip, 2.4, "prev"); assert abs(t - 2.0) < 0.02


def test_frame_grab_is_an_sdr_jpeg(clip):
    info = V.probe(FF[1], clip)
    data = V.frame_at(FF[0], clip, 1.5, info, width=320)
    assert data[:3] == b"\xff\xd8\xff" and len(data) > 2000


def test_cut_is_lossless_and_keeps_hdr_metadata(clip, tmp_path):
    info = V.probe(FF[1], clip)
    start, _ = V.snap(FF[1], clip, 2.0)
    out = str(tmp_path / "cut.mp4")
    V.cut(FF[0], info, start, 4.0, out, log=lambda m: None)
    v = V.verify(FF[1], info, out)
    assert v["all_ok"], [r for r in v["rows"] if not r["ok"]]
    assert abs(v["output"]["duration"] - 2.0) < 0.15
    # bit-exact: the first frame of the cut is the source's frame at the keyframe
    assert raw_frame(out, 0.0) == raw_frame(clip, 2.0)
    assert raw_frame(out, 1.0) == raw_frame(clip, 3.0)


def test_join_keeps_everything(clip, tmp_path):
    info = V.probe(FF[1], clip)
    segs = [{"info": info, "start": 1.0, "end": 2.0}, {"info": info, "start": 4.0, "end": 5.0}]
    outs = V.export(FF[0], FF[1], segs, True, str(tmp_path), "joined", progress=lambda p, m: None, log=lambda m: None)
    assert len(outs) == 1 and os.path.exists(outs[0])
    v = V.verify(FF[1], info, outs[0])
    assert v["all_ok"], [r for r in v["rows"] if not r["ok"]]
    assert abs(v["output"]["duration"] - 2.0) < 0.15
    assert raw_frame(outs[0], 0.0) == raw_frame(clip, 1.0)
    assert raw_frame(outs[0], 1.0) == raw_frame(clip, 4.0)


def test_separate_exports(clip, tmp_path):
    info = V.probe(FF[1], clip)
    segs = [{"info": info, "start": 0.0, "end": 1.0}, {"info": info, "start": 3.0, "end": 4.0}]
    outs = V.export(FF[0], FF[1], segs, False, str(tmp_path), "", progress=lambda p, m: None, log=lambda m: None)
    assert len(outs) == 2 and all(os.path.exists(o) for o in outs)
    assert all(V.verify(FF[1], info, o)["all_ok"] for o in outs)


def test_sdr_clip_is_reported_as_sdr(tmp_path):
    p = str(tmp_path / "sdr.mp4")
    V.make_test_clip(FF[0], p, seconds=2, hdr=False)
    info = V.probe(FF[1], p)
    assert not info["is_hdr"] and info["video"]["bit_depth"] == 8
