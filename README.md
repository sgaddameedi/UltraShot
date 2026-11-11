<p align="center">
  <img src="docs/banner.png" alt="UltraShot" width="100%">
</p>

<p align="center">
  <a href="https://github.com/sgaddameedi/UltraShot/releases/latest"><img alt="Release" src="https://img.shields.io/github/v/release/sgaddameedi/UltraShot?style=flat-square&color=4f8cff"></a>
  <a href="LICENSE"><img alt="MIT" src="https://img.shields.io/badge/license-MIT-b35cff?style=flat-square"></a>
  <img alt="Windows" src="https://img.shields.io/badge/platform-Windows%2010%2F11-0078d4?style=flat-square">
  <img alt="Python" src="https://img.shields.io/badge/python-3.11%2B-3776ab?style=flat-square">
  <a href="https://github.com/sgaddameedi/UltraShot/actions/workflows/ci.yml"><img alt="CI" src="https://img.shields.io/github/actions/workflow/status/sgaddameedi/UltraShot/ci.yml?style=flat-square&label=tests"></a>
</p>

<p align="center">
  <b>Drop an HDR game screenshot. Get a JPEG that stays HDR on Instagram, Threads, Google Photos, Chrome and every phone, and still looks right everywhere else.</b>
</p>

---

## Why UltraShot exists

HDR games look incredible. Sharing a screenshot of one does not.

A ReShade, NVIDIA App or Game Bar HDR capture lands on your disk as a `.jxl` or `.jxr` file that
almost nothing can open, let alone post. The usual escape hatch is to tone-map it to an ordinary
JPEG, which throws the HDR away. Upload a true HDR format instead (AVIF, HEIC, a PNG with a PQ
curve) and most social platforms either refuse it, flatten it, or run it through their compression
pipeline and hand back something dull and banded.

There is a format that survives all of that: **Ultra HDR JPEG**. It is a normal JPEG with a second,
small image inside, the *gain map*, that tells an HDR display how much brighter each pixel should
be. SDR screens and old apps show the base JPEG. HDR phones, Chrome, Edge, Android, Google Photos,
Instagram and Threads apply the gain map and show the real thing. Because it is "just a JPEG", it
passes through upload pipelines that would strip or re-encode anything exotic.

UltraShot is the missing piece between the capture tools and that format. It was built for one
person's Instagram feed and grew into a small, careful converter with a proper desktop app around
it:

- **The HDR layer is never touched.** Scene brightness in, scene brightness out. Exposure and look
  controls only shape the SDR fallback image.
- **The gain map is encoded so phones apply all of it.** The reference encoder's defaults make a
  1000-nit phone apply only about a third of the gain map; UltraShot matches the gain map's
  capacity to its real range, which was the difference between "slightly brighter" and HDR.
- **Nothing is left to the upload step.** Instagram's own crop and resize strip the gain map, so
  UltraShot crops and resizes for you first, at full quality, with 4:4:4 chroma.

## What it does

| | |
| --- | --- |
| **Inputs** | ReShade `.jxl` (scRGB float or HDR10 PQ / HLG), NVIDIA App and Windows Game Bar `.jxr` (scRGB) |
| **Outputs** | Ultra HDR JPEG with ISO 21496-1 *and* Adobe/Android XMP gain-map metadata, full size and an Instagram-ready copy |
| **Workflow** | Drag and drop, a watch folder that converts every new capture as it lands, tray mode, start with Windows, "Convert with UltraShot" in Explorer |
| **Preview** | Live SDR-base preview with exposure and highlight-knee sliders, Instagram crop with position control, a highlights map that shows exactly which pixels are brighter than SDR white |
| **Quality** | Full-resolution multi-channel gain map, quality 100, 4:4:4 chroma, capture date preserved |
| **Engine** | Google's [libultrahdr](https://github.com/google/libultrahdr) through [imagecodecs](https://github.com/cgohlke/imagecodecs); also usable from the command line without the GUI |

## Screenshots

<p align="center"><img src="docs/screenshots/main.png" width="90%" alt="Main window with converted captures"></p>

<table>
  <tr>
    <td><img src="docs/screenshots/inspector.png" alt="Inspector with live SDR preview"></td>
    <td><img src="docs/screenshots/highlights-map.png" alt="Highlights map"></td>
  </tr>
  <tr>
    <td align="center"><sub>Live SDR preview with exposure / knee</sub></td>
    <td align="center"><sub>Highlights map: orange above SDR white, pink above 600 nits</sub></td>
  </tr>
  <tr>
    <td><img src="docs/screenshots/instagram-crop.png" alt="Instagram crop"></td>
    <td><img src="docs/screenshots/settings.png" alt="Settings"></td>
  </tr>
  <tr>
    <td align="center"><sub>Instagram 4:5 crop with position control</sub></td>
    <td align="center"><sub>Settings</sub></td>
  </tr>
</table>

## Quick start

### Download

1. Grab `UltraShot-<version>-windows-x64.zip` from the
   [latest release](https://github.com/sgaddameedi/UltraShot/releases/latest) and unzip it anywhere.
2. Run `UltraShot.exe`. Windows 10/11 with Edge WebView2 (already on every up-to-date install) is
   all it needs.
3. Drop a capture on the window, or just take one: by default UltraShot watches
   `Videos\Captures` and converts new screenshots automatically, and it starts with Windows in the
   tray. Both can be changed in Settings.

Outputs land next to the capture:

```
Videos\Captures\
├── Screenshot.jxl
├── 4K HDR\Screenshot.jpg     full size
└── Insta\Screenshot.jpg      1440 px wide, optionally cropped
```

### Run from source

```bash
git clone https://github.com/sgaddameedi/UltraShot.git
cd UltraShot
pip install -r requirements.txt
python ultrashot.py
```

## Using it

**Capture in HDR first.** See [docs/capture.md](docs/capture.md) for ReShade, NVIDIA App and Game
Bar settings. If the game was not running in HDR, UltraShot will tell you the file is SDR.

**Convert.** Drop files or folders anywhere on the window, click the drop zone, or use the watch
folder. Each card shows the capture's peak brightness, how much of the frame is brighter than SDR
white, and the conversion status. Double-click a finished card to reveal the output in Explorer.

**Check the look.** Click a card to open the inspector. The preview is the SDR base image, the
version SDR screens and thumbnails will show. Move *Exposure* if dark scenes come out too dark,
and *Highlight knee* to trade a flatter image for more highlight detail. These never affect the HDR
layer. The *Highlights map* shows which pixels will actually get brighter on an HDR display.

**Instagram.** Enable the Instagram output (on by default), pick a crop such as 4:5 and position it
in the inspector. Then follow [docs/instagram.md](docs/instagram.md): upload from a desktop
browser, choose "original" aspect, no filters. The short version is that anything Instagram does to
the image on upload removes the gain map, so let UltraShot do all of it beforehand.

**Background use.** Closing the window keeps UltraShot in the tray; the tray menu toggles the watch
folder and opens it. *Start with Windows* adds a Startup shortcut. *Convert with UltraShot* adds a
right-click entry for `.jxl` / `.jxr` in Explorer. A second launch, from Explorer or a shortcut,
hands its files to the running instance.

## Supported inputs and outputs

| Source | Format | Notes |
| --- | --- | --- |
| ReShade 6.x "HDR" screenshot | `.jxl`, float16 scRGB (BT.709, 1.0 = 80 nits) or 16-bit PQ / HLG (BT.2100) | Lossless, best quality source |
| NVIDIA App / GeForce Experience (Alt+F1 in an HDR game) | `.jxr`, float scRGB | One subfolder per game; enable *Include subfolders* |
| Windows Game Bar (Win+Alt+PrtScn in an HDR game) | `.jxr`, float scRGB | Saved to `Videos\Captures` |

Output is always an Ultra HDR JPEG: a base JPEG (sRGB for scRGB sources, BT.2100 with embedded
ICC profile for PQ sources) plus a full-resolution multi-channel gain map, with both ISO 21496-1 and
`hdrgm` XMP signalling so older Android and Adobe readers find it too.

## How it works

1. **Decode to linear light.** JXL and JXR are decoded with `imagecodecs`. scRGB values are
   multiplied by 80 nits; PQ and HLG code values go through the ST 2084 / BT.2100 curves. The result
   is absolute luminance in nits, which is the last time the HDR data is modified except for
   cropping and Lanczos resizing (done in linear light).
2. **Tone-map the SDR base.** A soft shoulder leaves everything below the knee untouched and rolls
   highlights off toward white, pulling saturated colours toward their luminance instead of clipping
   a channel. This is the image non-HDR viewers see.
3. **Encode with libultrahdr.** The linear image (scaled so 1.0 = 203 nits, the SDR reference white)
   and the SDR base go to Google's encoder, which computes the gain map and writes the JPEG.
4. **Fix the capacity.** libultrahdr sets `HDRCapacityMax` from a target display peak that defaults
   to 10000 nits. The gain map is applied in proportion to `log(display headroom) / log(capacity)`,
   so a phone with 4x headroom would apply roughly 35 % of it. UltraShot re-encodes with the peak
   matched to the gain map's real maximum, and the phone applies 100 %.
5. **Add XMP signalling** and verify by decoding the file again; the log shows the peak that an HDR
   viewer will reconstruct.

Read more in [docs/how-it-works.md](docs/how-it-works.md).

## Command line

The engine works without the GUI:

```bash
python jxl2uhdr.py capture.jxl out.jpg                       # full size
python jxl2uhdr.py capture.jxr insta.jpg --max-width 1440 --crop 4:5 --exposure 0.3
python tools/watch_cli.py "D:\Captures" --ig-crop 4:5       # headless watch folder
```

Run `python jxl2uhdr.py -h` for every option, including `--knee`, `--auto-sdr`, `--quality`,
`--transfer` and `--peak-nits`.

## Settings

Everything is in **Settings** (the sliders icon) and stored in `%APPDATA%\UltraShot\settings.json`.
The full reference is in [docs/settings.md](docs/settings.md). The defaults are deliberately
opinionated: both outputs on, 1440 px Instagram copy, watch `Videos\Captures` including subfolders,
start with Windows, keep running in the tray.

## Building the exe

```bash
pip install -r requirements-dev.txt
build_exe.bat
```

produces `dist\UltraShot\UltraShot.exe` (about 100 MB unpacked: Python, NumPy, the codec library
and the WebView2 bridge). Tagged pushes build and publish it automatically through GitHub Actions.

## FAQ and troubleshooting

**The result looks the same as SDR on my phone.** Check that you are viewing it in an app that
supports gain maps (Google Photos, Chrome, Instagram, Threads, Samsung Gallery) and that the phone's
display is in a mode that allows HDR. Messaging apps usually re-encode and strip it.

**Instagram shows it dim or in SDR.** You cropped, resized or filtered in Instagram's upload flow,
or uploaded from an iPhone. See [docs/instagram.md](docs/instagram.md).

**"input looks like an SDR screenshot".** The file is 8-bit. The game was not running in HDR, or the
capture tool saved an SDR copy. Check the HDR toggle in Windows and in the game.

**Colours look washed out in the SDR preview of an HDR10 game.** Lower the knee or raise exposure;
HDR10 games often sit much darker than 203 nits on average. The HDR layer is unaffected either way.

**Dark scenes.** The cards show "subtle HDR" when under 0.5 % of pixels exceed SDR white. That is
the scene, not a conversion problem; the highlights that do exist are still carried in full.

More in [docs/troubleshooting.md](docs/troubleshooting.md).

## Roadmap

- HDR preview inside the app
- AVIF / HDR PNG outputs for platforms that prefer them
- OpenEXR and Radiance HDR input
- macOS and Linux shells for the GUI (the engine already runs there)

## Contributing

Issues with a sample capture and the viewer you used are the most useful thing you can send.
Pull requests are welcome; see [CONTRIBUTING.md](CONTRIBUTING.md) for the development setup, the
code layout and the one rule that matters (the HDR layer stays untouched).

## Acknowledgements

- [libultrahdr](https://github.com/google/libultrahdr) by Google, the gain-map encoder.
- [imagecodecs](https://github.com/cgohlke/imagecodecs) by Christoph Gohlke, which wraps it and
  the JPEG XL / XR decoders in one wheel.
- [pywebview](https://pywebview.flowrl.com/) and [pystray](https://github.com/moses-palmer/pystray)
  for the desktop shell.
- [hdrshot](https://github.com/snaketech-tu/hdrshot) for showing what a friendly HDR screenshot
  tool can look like.
- Greg Benz's [HDR photography guides](https://gregbenzphotography.com/hdr-photos/) for the
  practical knowledge of what social platforms do to gain-map files.

## License

[MIT](LICENSE) © 2026 sgaddameedi
