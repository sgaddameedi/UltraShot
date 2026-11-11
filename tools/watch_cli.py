#!/usr/bin/env python3
"""Console watcher: convert every new HDR screenshot in a folder without the GUI.

    python tools/watch_cli.py "C:\\Users\\you\\Videos\\Captures" [--ig-width 1440] [--ig-crop 4:5]
                               [--exposure 0] [--knee 0.6] [--existing] [--settle 3] [--interval 2]

Outputs go to <folder>/4K HDR/ and <folder>/Insta/, exactly like the app. Handy on a headless
machine or inside another script. Stop with Ctrl+C.
"""
import argparse
import os
import sys
import time
import traceback

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import jxl2uhdr  # noqa: E402

EXTS = (".jxl", ".jxr")


def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def convert(path, folder, args):
    stem = os.path.splitext(os.path.basename(path))[0] + ".jpg"
    p4k = os.path.join(folder, args.out_4k, stem)
    pig = os.path.join(folder, args.out_ig, stem)
    todo_4k, todo_ig = not os.path.exists(p4k), not os.path.exists(pig)
    if not (todo_4k or todo_ig):
        return
    t0 = time.time()
    nits, gamut = jxl2uhdr.load_hdr(path, log=log)
    common = dict(exposure=args.exposure, knee=args.knee, auto_sdr=args.auto_sdr, quality=100, log=log)
    if todo_4k:
        os.makedirs(os.path.dirname(p4k), exist_ok=True)
        jxl2uhdr.encode_uhdr(nits, gamut, p4k, **common)
    if todo_ig:
        os.makedirs(os.path.dirname(pig), exist_ok=True)
        jxl2uhdr.encode_uhdr(nits, gamut, pig, crop=args.ig_crop, max_width=args.ig_width, **common)
    log(f"done {os.path.basename(path)} in {time.time() - t0:.1f}s")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("folder", nargs="?", default=os.getcwd())
    ap.add_argument("--out-4k", default="4K HDR")
    ap.add_argument("--out-ig", default="Insta")
    ap.add_argument("--ig-width", type=int, default=1440)
    ap.add_argument("--ig-crop", default="")
    ap.add_argument("--exposure", type=float, default=0.0)
    ap.add_argument("--knee", type=float, default=0.6)
    ap.add_argument("--auto-sdr", action="store_true")
    ap.add_argument("--existing", action="store_true")
    ap.add_argument("--interval", type=float, default=2.0)
    ap.add_argument("--settle", type=float, default=3.0)
    args = ap.parse_args()

    folder = os.path.abspath(args.folder)
    if not os.path.isdir(folder):
        sys.exit(f"not a folder: {folder}")
    log(f"watching {folder}")
    seen, done = {}, set()
    if not args.existing:
        done.update(f for f in os.listdir(folder) if f.lower().endswith(EXTS))
        log(f"ignoring {len(done)} existing capture(s); use --existing to convert them")
    while True:
        try:
            for name in sorted(os.listdir(folder)):
                if not name.lower().endswith(EXTS) or name in done:
                    continue
                path = os.path.join(folder, name)
                try:
                    size = os.path.getsize(path)
                except OSError:
                    continue
                now = time.time()
                last, since = seen.get(name, (None, now))
                if size != last or size == 0:
                    seen[name] = (size, now)
                    continue
                if now - since < args.settle:
                    continue
                try:
                    with open(path, "rb"):
                        pass
                except OSError:
                    continue
                try:
                    convert(path, folder, args)
                except Exception:
                    log(f"FAILED {name}:\n{traceback.format_exc()}")
                done.add(name)
                seen.pop(name, None)
        except KeyboardInterrupt:
            log("stopped")
            return
        except Exception:
            log(f"watch error:\n{traceback.format_exc()}")
        time.sleep(args.interval)


if __name__ == "__main__":
    main()
