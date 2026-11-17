"""Lossless trim, cut and join for HDR video, on top of FFmpeg.

Everything here is stream copy: the compressed frames are moved into a new container untouched,
so the picture, the bit depth, the BT.2020 and PQ or HLG tags, the mastering-display and
content-light metadata and any Dolby Vision RPU survive exactly. The price is that a cut can only
land on a keyframe; the functions below find keyframes near any point so the editor can snap to
them and tell the user where they are. Nothing reads a whole file into memory: probing, keyframe
lookups and frame grabs ask FFmpeg for the few seconds around a point, and exports write one new
file. FFmpeg is not bundled; `find_ffmpeg` looks in the usual places and `install_ffmpeg` fetches
a build into the app's local data folder when the user asks for it.
"""
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
import zipfile

VIDEO_EXTS = (".mp4", ".mkv", ".mov", ".m4v", ".ts", ".m2ts", ".mts", ".webm")
LOCALAPPDATA = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
FFMPEG_DIR = os.path.join(LOCALAPPDATA, "UltraShot", "ffmpeg")
FFMPEG_URL = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"
CREATE_NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0

HDR_TRANSFERS = {"smpte2084": "PQ", "arib-std-b67": "HLG", "smpte428": "DCI", "bt2020-10": "BT.2020 10-bit", "bt2020-12": "BT.2020 12-bit"}


# ----------------------------------------------------------------------------- finding FFmpeg

def _candidates():
    here = os.path.dirname(sys.executable if getattr(sys, "frozen", False) else os.path.abspath(__file__))
    yield os.path.join(here, "ffmpeg", "bin")
    yield os.path.join(here, "ffmpeg")
    if os.path.isdir(FFMPEG_DIR):
        for root, dirs, files in os.walk(FFMPEG_DIR):
            if "ffmpeg.exe" in files or "ffmpeg" in files:
                yield root
    for p in os.environ.get("PATH", "").split(os.pathsep):
        if p:
            yield p
    yield os.path.join(LOCALAPPDATA, "Microsoft", "WinGet", "Links")
    yield r"C:\ffmpeg\bin"


def find_ffmpeg():
    """(ffmpeg, ffprobe) paths, or None when neither the app folder, the local data folder nor PATH has them."""
    exe = ".exe" if sys.platform == "win32" else ""
    for d in _candidates():
        f, p = os.path.join(d, "ffmpeg" + exe), os.path.join(d, "ffprobe" + exe)
        if os.path.isfile(f) and os.path.isfile(p):
            return f, p
    # a WinGet install links ffmpeg.exe but may not link ffprobe.exe; follow the link to the package
    links = os.path.join(LOCALAPPDATA, "Microsoft", "WinGet", "Links", "ffmpeg" + exe)
    if os.path.isfile(links):
        try:
            real = os.path.dirname(os.path.realpath(links))
            f, p = os.path.join(real, "ffmpeg" + exe), os.path.join(real, "ffprobe" + exe)
            if os.path.isfile(f) and os.path.isfile(p):
                return f, p
        except OSError:
            pass
    return None


def ffmpeg_version(ffmpeg):
    try:
        out = subprocess.run([ffmpeg, "-version"], capture_output=True, text=True, creationflags=CREATE_NO_WINDOW, timeout=20).stdout
        m = re.search(r"ffmpeg version (\S+)", out)
        return m.group(1) if m else out.split("\n")[0]
    except Exception:
        return "?"


def install_ffmpeg(progress=lambda pct, msg: None, log=print):
    """Download a static FFmpeg build into the app's local data folder and return (ffmpeg, ffprobe).
    The archive's SHA-256 is checked against the one published next to it, and logged."""
    os.makedirs(FFMPEG_DIR, exist_ok=True)
    zpath = os.path.join(FFMPEG_DIR, "ffmpeg-release-essentials.zip")
    log(f"downloading FFmpeg from {FFMPEG_URL}")
    with urllib.request.urlopen(FFMPEG_URL, timeout=60) as r, open(zpath, "wb") as fh:
        total = int(r.headers.get("Content-Length") or 0); done = 0
        while True:
            chunk = r.read(1 << 20)
            if not chunk:
                break
            fh.write(chunk); done += len(chunk)
            progress(done * 100.0 / total if total else 0.0, f"downloading FFmpeg {done / 1e6:.0f} MB")
    sha = hashlib.sha256(open(zpath, "rb").read()).hexdigest()
    try:
        with urllib.request.urlopen(FFMPEG_URL + ".sha256", timeout=30) as r:
            published = r.read().decode("ascii", "replace").split()[0].lower()
        if published != sha:
            os.remove(zpath)
            raise RuntimeError("the downloaded FFmpeg archive does not match its published checksum")
        log(f"FFmpeg archive SHA-256 {sha} matches the published checksum")
    except urllib.error.URLError:
        log(f"FFmpeg archive SHA-256 {sha} (the published checksum could not be fetched)")
    progress(100.0, "extracting FFmpeg")
    with zipfile.ZipFile(zpath) as z:
        for member in z.namelist():
            if member.endswith(("ffmpeg.exe", "ffprobe.exe")) and "/bin/" in member:
                z.extract(member, FFMPEG_DIR)
    os.remove(zpath)
    found = find_ffmpeg()
    if not found:
        raise RuntimeError("FFmpeg was downloaded but ffmpeg.exe was not found in the archive")
    log(f"FFmpeg {ffmpeg_version(found[0])} installed in {os.path.dirname(found[0])}")
    return found


def _run(cmd, timeout=None):
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace",
                       creationflags=CREATE_NO_WINDOW, timeout=timeout)
    if r.returncode != 0:
        raise RuntimeError((r.stderr or r.stdout).strip().split("\n")[-1] or f"exit {r.returncode}")
    return r.stdout


# ----------------------------------------------------------------------------- probing

def probe(ffprobe, path):
    """What the file is: container, duration, the video stream's codec, size, rate, bit depth and
    colour tags, the HDR metadata it carries, and the audio streams."""
    out = _run([ffprobe, "-v", "error", "-print_format", "json", "-show_format", "-show_streams", path], timeout=120)
    j = json.loads(out)
    fmt = j.get("format", {})
    v = next((s for s in j.get("streams", []) if s.get("codec_type") == "video"), None)
    if not v:
        raise RuntimeError("no video stream")
    # r_frame_rate is the stream's own base rate; avg_frame_rate is frames over container duration
    # and drifts on a cut whose audio outlasts its video by a few packets
    num, den = (v.get("r_frame_rate") or v.get("avg_frame_rate") or "0/1").split("/")
    fps = float(num) / float(den) if float(den or 0) else 0.0
    # the declared rates can mislead after a stream copy (a joined file's timebase changes and
    # a cut's audio outlasts its video), so measure the rate from the first packets' timestamps
    measured = _measure_fps(ffprobe, path)
    if measured:
        fps = measured
    side = {s.get("side_data_type", ""): s for s in v.get("side_data_list", [])}
    # HDR static metadata travels as SEI on the frames; the container may or may not repeat it at
    # stream level, so read the first video frame's side data too
    try:
        fr = json.loads(_run([ffprobe, "-v", "error", "-select_streams", "v:0", "-read_intervals", "%+#1", "-show_frames",
                              "-show_entries", "frame=side_data_list", "-print_format", "json", path], timeout=120))
        for f in fr.get("frames", [])[:1]:
            for sd in f.get("side_data_list", []):
                side.setdefault(sd.get("side_data_type", ""), sd)
    except Exception:
        pass
    mdcv = side.get("Mastering display metadata")
    cll = side.get("Content light level metadata")
    dovi = side.get("DOVI configuration record")
    transfer = v.get("color_transfer") or ""
    hdr_kind = HDR_TRANSFERS.get(transfer)
    pix = v.get("pix_fmt") or ""
    m = re.search(r"(\d+)(?:le|be)?$", pix)
    depth = int(m.group(1)) if m and int(m.group(1)) in (10, 12, 16) else 8
    hdr = {
        "kind": ("Dolby Vision" if dovi else hdr_kind) or ("none" if transfer else "untagged"),
        "transfer": transfer, "primaries": v.get("color_primaries") or "", "matrix": v.get("color_space") or "",
        "range": v.get("color_range") or "",
        "max_cll": int(cll["max_content"]) if cll and "max_content" in cll else None,
        "max_fall": int(cll["max_average"]) if cll and "max_average" in cll else None,
        "mastering": {k: mdcv[k] for k in ("red_x", "red_y", "green_x", "green_y", "blue_x", "blue_y", "white_point_x", "white_point_y", "min_luminance", "max_luminance") if k in mdcv} if mdcv else None,
        "dolby_vision": {k: dovi.get(k) for k in ("dv_profile", "dv_level", "rpu_present_flag", "bl_present_flag", "el_present_flag")} if dovi else None,
    }
    audio = [{"index": s.get("index"), "codec": s.get("codec_name"), "channels": s.get("channels"), "sample_rate": s.get("sample_rate"),
              "language": (s.get("tags") or {}).get("language", ""), "bit_rate": int(s.get("bit_rate") or 0)}
             for s in j.get("streams", []) if s.get("codec_type") == "audio"]
    info = {
        "path": path, "name": os.path.basename(path), "size": int(fmt.get("size") or os.path.getsize(path)),
        "container": (fmt.get("format_name") or "").split(",")[0],
        "duration": float(v.get("duration") or fmt.get("duration") or 0.0), "container_duration": float(fmt.get("duration") or 0.0),
        # transport streams start their clock at about 1.4 s; every time the editor shows or cuts at
        # is relative to this, so the player, the keyframes and the cuts agree
        "start": float(v.get("start_time") or fmt.get("start_time") or 0.0),
        "bit_rate": int(fmt.get("bit_rate") or 0),
        "video": {"codec": v.get("codec_name"), "codec_tag": v.get("codec_tag_string"), "profile": v.get("profile"), "width": v.get("width"), "height": v.get("height"),
                  "fps": round(fps, 3), "pix_fmt": pix, "bit_depth": depth, "bit_rate": int(v.get("bit_rate") or 0), "index": v.get("index")},
        "audio": audio, "hdr": hdr,
    }
    info["is_hdr"] = hdr["kind"] not in ("none", "untagged")
    info["summary"] = summary(info)
    return info


def _measure_fps(ffprobe, path, packets=48):
    try:
        out = _run([ffprobe, "-v", "error", "-select_streams", "v:0", "-read_intervals", f"%+#{packets}",
                    "-show_entries", "packet=pts_time", "-of", "csv=p=0", path], timeout=60)
        ts = sorted(float(x.strip().rstrip(",")) for x in out.split() if x.strip().rstrip(",") not in ("", "N/A"))
        gaps = sorted(b - a for a, b in zip(ts, ts[1:]) if b > a)
        if len(gaps) < 4:
            return 0.0
        med = gaps[len(gaps) // 2]
        fps = 1.0 / med
        std = min((23.976, 24.0, 25.0, 29.97, 30.0, 48.0, 50.0, 59.94, 60.0, 90.0, 100.0, 119.88, 120.0), key=lambda x: abs(x - fps))
        return std if abs(fps - std) / std < 0.003 else round(fps, 3)
    except Exception:
        return 0.0


def summary(info):
    v, h = info["video"], info["hdr"]
    codec = {"hevc": "HEVC", "h264": "H.264", "av1": "AV1", "prores": "ProRes", "vp9": "VP9"}.get(v["codec"], (v["codec"] or "?").upper())
    parts = [f"{codec} {v['bit_depth']}-bit"]
    if h["kind"] == "Dolby Vision":
        parts.append(f"Dolby Vision profile {h['dolby_vision']['dv_profile']}")
    elif h["kind"] in ("PQ", "HLG"):
        parts.append(f"HDR10 ({h['kind']}, {h['primaries'] or 'BT.2020'})" if h["kind"] == "PQ" else f"HLG ({h['primaries'] or 'BT.2020'})")
    elif h["kind"] == "untagged":
        parts.append("no colour tags")
    else:
        parts.append("SDR")
    parts.append(f"{v['width']}×{v['height']}")
    if v["fps"]:
        parts.append(f"{v['fps']:g} fps")
    br = v["bit_rate"] or info["bit_rate"]
    if br:
        parts.append(f"{br / 1e6:.0f} Mb/s")
    return " · ".join(parts)


# ----------------------------------------------------------------------------- keyframes

def keyframes_near(ffprobe, path, t, span=6.0, start=0.0):
    """Keyframe times (seconds, relative to the stream start) within `span` seconds around `t`,
    read from packet headers only, so it is fast even on a very large file."""
    a = max(0.0, t - span) + start
    out = _run([ffprobe, "-v", "error", "-select_streams", "v:0", "-read_intervals", f"{a:.3f}%+{2 * span:.3f}",
                "-show_entries", "packet=pts_time,dts_time,flags", "-of", "csv=p=0", path], timeout=120)
    times = []
    for line in out.splitlines():
        cols = line.split(",")
        if len(cols) >= 3 and "K" in cols[2]:
            try:
                times.append(float(cols[0] if cols[0] not in ("N/A", "") else cols[1]) - start)
            except ValueError:
                pass
    return sorted(set(round(x, 4) for x in times if x > -1e-3))


def snap(ffprobe, path, t, direction="nearest", span=6.0, start=0.0):
    """The keyframe time to cut at for a requested time: the nearest, the previous or the next.
    Returns (time, keyframes_seen)."""
    ks = keyframes_near(ffprobe, path, t, span, start)
    if not ks:
        ks = keyframes_near(ffprobe, path, t, span * 4, start)
    if not ks:
        return t, []
    if direction == "prev":
        c = [k for k in ks if k <= t + 1e-3] or ks[:1]
        return c[-1], ks
    if direction == "next":
        c = [k for k in ks if k >= t - 1e-3] or ks[-1:]
        return c[0], ks
    return min(ks, key=lambda k: abs(k - t)), ks


# ----------------------------------------------------------------------------- frames

def tonemap_filter(info, width):
    """A filter chain that gives a plain SDR JPEG of an HDR frame (PQ or HLG) for thumbnails and
    the filmstrip; SDR sources are only scaled."""
    base = f"scale={width}:-2:flags=bicubic"
    if info["hdr"]["kind"] in ("PQ", "HLG", "Dolby Vision"):
        tr = "arib-std-b67" if info["hdr"]["kind"] == "HLG" else "smpte2084"
        return (f"{base},zscale=t=linear:npl=203:tin={tr}:pin=bt2020:min=bt2020nc,format=gbrpf32le,"
                "zscale=p=bt709,tonemap=hable:desat=0,zscale=t=bt709:m=bt709:r=tv,format=yuv420p")
    return base


def frame_at(ffmpeg, path, t, info, width=640, quality=4):
    """One frame at `t` as JPEG bytes, tone-mapped to SDR when the source is HDR."""
    cmd = [ffmpeg, "-v", "error", "-ss", f"{max(0.0, t):.3f}", "-i", path, "-map", "0:v:0", "-frames:v", "1",
           "-vf", tonemap_filter(info, width), "-f", "image2pipe", "-vcodec", "mjpeg", "-q:v", str(quality), "-"]
    r = subprocess.run(cmd, capture_output=True, creationflags=CREATE_NO_WINDOW, timeout=120)
    if r.returncode != 0 or not r.stdout:
        raise RuntimeError(r.stderr.decode("utf-8", "replace").strip().split("\n")[-1] if r.stderr else "no frame")
    return r.stdout


# ----------------------------------------------------------------------------- cutting and joining

def _copy_args(info):
    # no timestamp shifting: the muxer keeps the first keyframe at presentation time zero through an
    # edit list, so a seek by exactly one second lands on exactly the frame it should
    args = ["-map", "0", "-c", "copy", "-map_metadata", "0"]
    if info["container"] in ("mov", "mp4", "m4a", "3gp", "3g2", "mj2") or info["path"].lower().endswith((".mp4", ".mov", ".m4v")):
        # negative composition offsets keep the first keyframe at presentation time zero without an
        # edit list, which the concat demuxer would otherwise drop and shift every part by the B-frame delay
        args += ["-movflags", "+faststart+negative_cts_offsets"]
        if info["hdr"]["kind"] == "Dolby Vision":
            args += ["-strict", "unofficial"]
    return args


def _progress_run(cmd, duration, progress, log):
    """Run FFmpeg with -progress on stdout and report completion as a fraction of `duration`."""
    p = subprocess.Popen(cmd + ["-progress", "pipe:1", "-nostats"], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                         text=True, encoding="utf-8", errors="replace", creationflags=CREATE_NO_WINDOW)
    for line in p.stdout:
        if line.startswith("out_time_us=") and duration > 0:
            try:
                progress(min(99.0, int(line.split("=")[1]) / 1e6 / duration * 100.0))
            except ValueError:
                pass
    err = p.stderr.read(); p.wait()
    if p.returncode != 0:
        raise RuntimeError(err.strip().split("\n")[-1] if err.strip() else f"FFmpeg exit {p.returncode}")


def count_frames(ffprobe, path, start, end, offset=0.0):
    """How many video packets present between two times (keyframe-aligned cut points, relative to
    the stream start). Reads only that interval's packet headers."""
    start, end = start + offset, end + offset
    # the interval starts a second early: on a transport stream ffprobe's seek can land a packet
    # or two past the keyframe, and the packets are filtered by timestamp below anyway
    out = _run([ffprobe, "-v", "error", "-select_streams", "v:0", "-read_intervals", f"{max(0.0, start - 1.0):.3f}%{end + 0.5:.3f}",
                "-show_entries", "packet=pts_time", "-of", "csv=p=0", path], timeout=300)
    n = 0
    for x in out.split():
        x = x.strip().rstrip(",")
        if x and x != "N/A" and start - 1e-3 <= float(x) < end - 1e-3:
            n += 1
    return n


def cut(ffmpeg, info, start, end, dst, progress=lambda pct: None, log=print, ffprobe=None):
    """Stream-copy [start, end) of a file into dst. `start` should be a keyframe time: FFmpeg seeks
    to the keyframe at or before it. The video is limited to exactly the number of frames that sit
    between the two times (counted from the file), which is what makes the cut frame-exact with
    stream copy; the audio is limited by time."""
    fps = info["video"]["fps"] or 30.0
    length = max(1.0 / fps, end - start)
    probe_exe = ffprobe or (find_ffmpeg() or (None, None))[1]
    frames = count_frames(probe_exe, info["path"], start, end, info.get("start", 0.0)) if probe_exe else int(round(length * fps))
    cmd = [ffmpeg, "-y", "-v", "error", "-ss", f"{start:.3f}", "-i", info["path"], "-t", f"{frames / fps:.4f}",
           "-frames:v", str(max(1, frames))] + _copy_args(info) + [dst]
    log(f"cut {os.path.basename(info['path'])} {start:.3f}s to {end:.3f}s -> {os.path.basename(dst)} (stream copy)")
    _progress_run(cmd, length, progress, log)
    return dst


def compatible(a, b):
    """Two probes whose streams can be concatenated without re-encoding."""
    va, vb = a["video"], b["video"]
    return all(va.get(k) == vb.get(k) for k in ("codec", "width", "height", "pix_fmt")) and abs(va["fps"] - vb["fps"]) < 0.01 \
        and [(x["codec"], x["channels"], x["sample_rate"]) for x in a["audio"]] == [(x["codec"], x["channels"], x["sample_rate"]) for x in b["audio"]]


def concat(ffmpeg, infos, parts, dst, progress=lambda pct: None, log=print):
    """Join already-cut parts (same codec parameters) with the concat demuxer, stream copy."""
    for a, b in zip(infos, infos[1:]):
        if not compatible(a, b):
            raise RuntimeError(f"{a['name']} and {b['name']} have different stream parameters and cannot be joined without re-encoding")
    # each entry carries its video length, so the next part starts exactly where the video ends
    # even when the audio packets run a few milliseconds past it
    lst = dst + ".parts.txt"
    lengths = [video_length(p) for p in parts]
    with open(lst, "w", encoding="utf-8") as fh:
        for p, ln in zip(parts, lengths):
            fh.write("file '" + p.replace("\\", "/").replace("'", "'\\''") + "'\n")
            if ln:
                fh.write(f"duration {ln:.6f}\n")
    total = sum(lengths) or sum(probe_duration(p) for p in parts)
    # -copyts: the parts' audio starts a few milliseconds before zero (encoder priming), and without
    # it the concat demuxer would re-base on that and push every video frame late by that amount
    cmd = [ffmpeg, "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", lst, "-copyts"] + _copy_args(infos[0]) + [dst]
    log(f"join {len(parts)} part(s) -> {os.path.basename(dst)} (stream copy)")
    try:
        _progress_run(cmd, total, progress, log)
    finally:
        try:
            os.remove(lst)
        except OSError:
            pass
    return dst


def video_length(path):
    """Exact length of a file's video stream: frames over the measured rate."""
    ff = find_ffmpeg()
    if not ff:
        return 0.0
    try:
        out = _run([ff[1], "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=nb_frames,duration", "-of", "default=nw=1", path], timeout=60)
        kv = dict(line.split("=", 1) for line in out.split() if "=" in line)
        fps = _measure_fps(ff[1], path)
        if kv.get("nb_frames", "").isdigit() and fps:
            return int(kv["nb_frames"]) / fps
        return float(kv.get("duration") or 0.0)
    except Exception:
        return 0.0


def probe_duration(path):
    """Duration without a full probe, for progress arithmetic."""
    ff = find_ffmpeg()
    if not ff:
        return 0.0
    try:
        return float(_run([ff[1], "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path], timeout=60).strip() or 0.0)
    except Exception:
        return 0.0


def export(ffmpeg, ffprobe, segments, join, out_dir, name, progress=lambda pct, msg: None, log=print):
    """segments: [{"info": probe, "start": s, "end": e}] with keyframe-snapped starts.
    join=False writes one file per segment; join=True writes a single file. Returns output paths."""
    if not segments:
        raise RuntimeError("nothing to export")
    os.makedirs(out_dir, exist_ok=True)
    first = segments[0]["info"]
    ext = os.path.splitext(first["path"])[1].lower() or ".mp4"
    outputs = []
    n = len(segments)
    if not join:
        for i, seg in enumerate(segments):
            stem = os.path.splitext(seg["info"]["name"])[0]
            dst = unique_path(os.path.join(out_dir, f"{stem}-cut{'' if n == 1 else '-' + str(i + 1)}{ext}"))
            cut(ffmpeg, seg["info"], seg["start"], seg["end"], dst,
                progress=lambda pct, i=i: progress((i + pct / 100.0) / n * 100.0, f"cutting {i + 1} of {n}"), log=log)
            outputs.append(dst)
        return outputs
    dst = unique_path(os.path.join(out_dir, f"{name or os.path.splitext(first['name'])[0] + '-joined'}{ext}"))
    if n == 1:
        cut(ffmpeg, first, segments[0]["start"], segments[0]["end"], dst, progress=lambda pct: progress(pct, "cutting"), log=log)
        return [dst]
    tmpdir = tempfile.mkdtemp(prefix="ultrashot-join-", dir=out_dir)
    try:
        parts = []
        for i, seg in enumerate(segments):
            part = os.path.join(tmpdir, f"part{i:03d}{ext}")
            cut(ffmpeg, seg["info"], seg["start"], seg["end"], part,
                progress=lambda pct, i=i: progress((i + pct / 100.0) / (n + 1) * 100.0, f"cutting {i + 1} of {n}"), log=log)
            parts.append(part)
        concat(ffmpeg, [s["info"] for s in segments], parts, dst, progress=lambda pct: progress((n + pct / 100.0) / (n + 1) * 100.0, "joining"), log=log)
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
    return [dst]


def unique_path(p):
    if not os.path.exists(p):
        return p
    stem, ext = os.path.splitext(p)
    for i in range(2, 1000):
        q = f"{stem} ({i}){ext}"
        if not os.path.exists(q):
            return q
    return p


# ----------------------------------------------------------------------------- verification

def verify(ffprobe, src_info, dst_path):
    """Probe the result and compare everything that matters for 'nothing was lost': codec, size,
    rate, bit depth, colour tags, HDR metadata and audio. Returns rows of (label, source, output, ok)."""
    d = probe(ffprobe, dst_path)
    s = src_info
    rows = []
    def row(label, a, b, ok=None):
        rows.append({"label": label, "source": "" if a is None else str(a), "output": "" if b is None else str(b), "ok": (a == b) if ok is None else ok})
    row("Video codec", s["video"]["codec"], d["video"]["codec"])
    row("Resolution", f"{s['video']['width']}×{s['video']['height']}", f"{d['video']['width']}×{d['video']['height']}")
    row("Frame rate", f"{s['video']['fps']:g}", f"{d['video']['fps']:g}", abs(s["video"]["fps"] - d["video"]["fps"]) <= 0.002 * max(s["video"]["fps"], d["video"]["fps"], 1))
    row("Pixel format", s["video"]["pix_fmt"], d["video"]["pix_fmt"])
    row("Bit depth", s["video"]["bit_depth"], d["video"]["bit_depth"])
    row("Transfer", s["hdr"]["transfer"] or "untagged", d["hdr"]["transfer"] or "untagged")
    row("Primaries", s["hdr"]["primaries"] or "untagged", d["hdr"]["primaries"] or "untagged")
    row("Matrix", s["hdr"]["matrix"] or "untagged", d["hdr"]["matrix"] or "untagged")
    row("HDR kind", s["hdr"]["kind"], d["hdr"]["kind"])
    if s["hdr"]["max_cll"] is not None or d["hdr"]["max_cll"] is not None:
        row("MaxCLL / MaxFALL", f"{s['hdr']['max_cll']} / {s['hdr']['max_fall']}", f"{d['hdr']['max_cll']} / {d['hdr']['max_fall']}")
    if s["hdr"]["mastering"] or d["hdr"]["mastering"]:
        row("Mastering display", "present" if s["hdr"]["mastering"] else "absent", "present" if d["hdr"]["mastering"] else "absent",
            bool(s["hdr"]["mastering"]) == bool(d["hdr"]["mastering"]))
    if s["hdr"]["dolby_vision"] or d["hdr"]["dolby_vision"]:
        row("Dolby Vision RPU", "present" if s["hdr"]["dolby_vision"] else "absent", "present" if d["hdr"]["dolby_vision"] else "absent",
            bool(s["hdr"]["dolby_vision"]) == bool(d["hdr"]["dolby_vision"]))
    row("Audio streams", ", ".join(f"{a['codec']} {a['channels']}ch" for a in s["audio"]) or "none",
        ", ".join(f"{a['codec']} {a['channels']}ch" for a in d["audio"]) or "none")
    return {"output": d, "rows": rows, "all_ok": all(r["ok"] for r in rows)}


# ----------------------------------------------------------------------------- proxies

def make_proxy(ffmpeg, info, dst, progress=lambda pct: None, log=print, width=1280):
    """A small SDR H.264 copy for preview when the player cannot decode the source. NVENC when
    present, otherwise libx264. Tone-mapped for HDR sources."""
    vf = tonemap_filter(info, width)
    enc = ["-c:v", "h264_nvenc", "-preset", "p4", "-cq", "26"] if "h264_nvenc" in encoders(ffmpeg) else ["-c:v", "libx264", "-preset", "veryfast", "-crf", "23"]
    cmd = [ffmpeg, "-y", "-v", "error", "-i", info["path"], "-map", "0:v:0", "-map", "0:a:0?", "-vf", vf] + enc + \
          ["-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", dst]
    log(f"building a preview proxy for {info['name']} ({width} px wide)")
    _progress_run(cmd, info["duration"], progress, log)
    return dst


_enc_cache = {}


def encoders(ffmpeg):
    if ffmpeg not in _enc_cache:
        try:
            _enc_cache[ffmpeg] = _run([ffmpeg, "-v", "error", "-encoders"], timeout=30)
        except Exception:
            _enc_cache[ffmpeg] = ""
    return _enc_cache[ffmpeg]


# ----------------------------------------------------------------------------- test material

def make_test_clip(ffmpeg, dst, seconds=6, fps=30, gop=30, size="640x360", hdr=True):
    """A synthetic HDR10 (or SDR) HEVC clip with real colour tags and HDR metadata, for tests."""
    x265 = f"keyint={gop}:min-keyint={gop}:scenecut=0:open-gop=0"   # closed GOPs, as recorders write them
    tags = []
    if hdr:
        x265 += ":colorprim=bt2020:transfer=smpte2084:colormatrix=bt2020nc:master-display=G(13250,34500)B(7500,3000)R(34000,16000)WP(15635,16450)L(10000000,1):max-cll=1000,400:hdr10=1:repeat-headers=1"
        tags = ["-color_primaries", "bt2020", "-color_trc", "smpte2084", "-colorspace", "bt2020nc"]
    cmd = [ffmpeg, "-y", "-v", "error", "-f", "lavfi", "-i", f"testsrc2=size={size}:rate={fps}:duration={seconds}",
           "-f", "lavfi", "-i", f"sine=frequency=440:duration={seconds}",
           "-c:v", "libx265", "-pix_fmt", "yuv420p10le" if hdr else "yuv420p", "-x265-params", x265, "-tag:v", "hvc1"] + tags + \
          ["-c:a", "aac", "-b:a", "96k", "-movflags", "+faststart", dst]
    _run(cmd, timeout=300)
    return dst
