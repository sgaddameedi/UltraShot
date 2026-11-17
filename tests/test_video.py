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


def test_transport_stream_times_are_relative_to_its_start(clip, tmp_path):
    """A transport stream's clock starts at about 1.4 s. The editor's times are relative to the
    stream start, so the player, the keyframes and the cuts all agree, and a cut of a .ts holds
    the same frames as the same cut of the .mp4 it came from."""
    ts = str(tmp_path / "same.ts")
    subprocess.run([FF[0], "-y", "-v", "error", "-i", clip, "-c", "copy", "-f", "mpegts", ts], check=True, creationflags=V.CREATE_NO_WINDOW, timeout=120)
    info = V.probe(FF[1], ts)
    assert info["start"] > 1.0 and info["container"] == "mpegts"
    ks = V.keyframes_near(FF[1], ts, 3.0, 3.0, info["start"])
    assert any(abs(k - 2.0) < 0.02 for k in ks) and any(abs(k - 3.0) < 0.02 for k in ks)
    t, _ = V.snap(FF[1], ts, 2.4, "nearest", start=info["start"]); assert abs(t - 2.0) < 0.02
    out = str(tmp_path / "ts-cut.mp4")
    V.cut(FF[0], info, t, 4.0, out, log=lambda m: None, ffprobe=FF[1])
    assert abs(V.video_length(out) - 2.0) < 0.05
    src = V.probe(FF[1], clip)
    ref = str(tmp_path / "mp4-cut.mp4")
    V.cut(FF[0], src, 2.0, 4.0, ref, log=lambda m: None, ffprobe=FF[1])
    assert raw_frame(out, 0.0) == raw_frame(ref, 0.0) and raw_frame(out, 1.5) == raw_frame(ref, 1.5)


def test_crop_rect_fits_the_frame_and_stays_even():
    assert V.crop_rect(3840, 2160, "9:16") == (1214, 2160, 1312, 0)
    assert V.crop_rect(3840, 2160, "9:16", cx=0.0)[2] == 0
    w, h, x, y = V.crop_rect(3840, 2160, "9:16", cx=1.0)
    assert x + w <= 3840 and x % 2 == 0
    assert V.crop_rect(3840, 2160, "16:9") == (3840, 2160, 0, 0)
    assert V.crop_rect(3840, 2160, "1:1") == (2160, 2160, 840, 0)
    assert V.crop_rect(1080, 1920, "16:9") == (1080, 606, 0, 656)
    info = {"video": {"width": 3840, "height": 2160}}
    plan = V.reframe_plan(info, "9:16", size="upload")
    assert plan["size"] == (1080, 1920) and plan["scale"] and plan["changes"]
    assert V.reframe_plan(info, "9:16")["size"] == (1214, 2160)
    assert not V.reframe_plan(info, "16:9")["changes"]
    assert V.reframe_plan(info, "16:9", size="upload")["size"] == (1920, 1080)


def test_reframe_crops_and_keeps_hdr_metadata(clip, tmp_path):
    info = V.probe(FF[1], clip)
    outs = V.export(FF[0], FF[1], [{"info": info, "start": 1.0, "end": 4.0}], False, str(tmp_path), "",
                    frame={"frame": "9:16", "cx": 0.25, "cy": 0.5, "size": "full"})
    assert len(outs) == 1 and outs[0].endswith("-cut-9x16.mp4")
    assert os.listdir(tmp_path) == [os.path.basename(outs[0])], "the lossless intermediate must not be left behind"
    plan = V.reframe_plan(info, "9:16", 0.25, 0.5, "full")
    rep = V.verify(FF[1], info, outs[0], {"codec": "hevc", "size": plan["size"]})
    assert rep["all_ok"], [r for r in rep["rows"] if not r["ok"]]
    out = rep["output"]
    assert (out["video"]["width"], out["video"]["height"]) == (202, 360) and out["video"]["bit_depth"] == 10
    assert out["hdr"]["kind"] == "PQ" and out["hdr"]["max_cll"] == 1000 and out["hdr"]["max_fall"] == 400 and out["hdr"]["mastering"]
    assert abs(out["duration"] - 3.0) < 0.2 and len(out["audio"]) == 1
    # a frame the recording already has is a plain lossless copy
    same = V.export(FF[0], FF[1], [{"info": info, "start": 1.0, "end": 4.0}], False, str(tmp_path / "same"), "",
                    frame={"frame": "16:9", "cx": 0.5, "cy": 0.5, "size": "full"})
    assert same[0].endswith("-cut.mp4") and V.verify(FF[1], info, same[0])["all_ok"]


def test_cut_is_frame_exact_when_the_stream_starts_late(clip, tmp_path):
    """A recorder that starts its clock a few milliseconds in puts every keyframe just off the
    second, and a seek aimed exactly at one can land on the keyframe before it. The cut must still
    hold exactly the frames between its points, starting on the keyframe."""
    late = str(tmp_path / "late.mp4")
    subprocess.run([FF[0], "-y", "-v", "error", "-i", clip, "-c", "copy", "-output_ts_offset", "0.009", "-movflags", "+faststart", late],
                   check=True, creationflags=V.CREATE_NO_WINDOW, timeout=120)
    info = V.probe(FF[1], late)
    assert abs(info["start"] - 0.009) < 0.002
    t, _ = V.snap(FF[1], late, 2.0, "nearest", start=info["start"])
    assert abs(t - 2.0) < 0.02
    out = str(tmp_path / "late-cut.mp4")
    V.cut(FF[0], info, t, 4.0, out, log=lambda m: None, ffprobe=FF[1])
    n = subprocess.run([FF[1], "-v", "error", "-select_streams", "v:0", "-count_packets", "-show_entries", "stream=nb_read_packets", "-of", "csv=p=0", out],
                       capture_output=True, text=True, creationflags=V.CREATE_NO_WINDOW, timeout=120).stdout.strip().rstrip(",")
    pts = sorted(float(x.rstrip(",")) for x in subprocess.run([FF[1], "-v", "error", "-select_streams", "v:0", "-show_entries", "packet=pts_time", "-of", "csv=p=0", out],
                                                            capture_output=True, text=True, creationflags=V.CREATE_NO_WINDOW, timeout=120).stdout.split())
    inside = [t for t in pts if t < 2.0 - 1e-3]
    assert len(inside) == 60 and max(b - a for a, b in zip(inside, inside[1:])) < 1.5 / 30, "every frame before the out point, with no gap"
    assert len(pts) <= 64, "at most a few reordered frames past the out point"
    a = subprocess.run([FF[1], "-v", "error", "-select_streams", "a:0", "-show_entries", "packet=pts_time,duration_time", "-of", "csv=p=0", out],
                       capture_output=True, text=True, creationflags=V.CREATE_NO_WINDOW, timeout=120).stdout.split()
    a_start, a_end = float(a[0].split(",")[0]), sum(float(x) for x in a[-1].split(","))
    assert -0.1 <= a_start <= 0.03 and abs(a_end - 2.0) < 0.05, (a_start, a_end)   # at most a few audio packets lead the keyframe
    first = V.first_video_pts(FF[1], out)
    assert first is not None and -0.001 <= first <= 0.03, first
    assert abs(V.video_length(out) - 2.0) < 0.05
    assert raw_frame(out, 0.0) == raw_frame(clip, 2.0) and raw_frame(out, 1.5) == raw_frame(clip, 3.5)
