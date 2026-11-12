# Changelog

All notable changes to UltraShot are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added
- In-app result viewer: double-click a converted card to open it in the default viewer (single result)
  or step through every converted capture in a viewer rendered by WebView2, which shows the gain-map
  JPEG in HDR on an HDR display. Switch between the Instagram copy and the full-size file.
- Optional "Limit HDR peak" (Settings → Fine-tuning, `--limit-nits` on the command line): a soft
  roll-off that caps highlights at your display's peak, for captures that carry brighter highlights
  than the display showed. Off by default; the only setting that alters the HDR layer.
- File details in the result viewer: the finished JPEG is read back and reported as it is on disk,
  with the base image's resolution, chroma subsampling, estimated quality and colour profile, the
  gain map's resolution, channels and quality, the full gain-map metadata (content boost, capacity,
  gamma, offsets), the HDR a viewer reconstructs, and which metadata signalling is present. A
  "Copy report" button copies it as text for bug reports.
- Compare in the result viewer: a draggable wipe between the SDR base image and the Ultra HDR
  rendering, and a 1:1 wipe between the original capture and the finished file, rendered with the
  same tone map so the two differ only by what the encoder changed. The source comparison reports
  the PSNR of the base image against the source, the share of pixels off by more than two levels,
  and the mean, 99th-percentile and over-five-percent luminance error of the reconstructed HDR layer.
- Instagram framing the Instagram way: with a crop chosen, the inspector shows the crop window over
  the whole picture and you drag the picture to decide what it keeps, with a grid while dragging.
  The framing is per capture and remembered with the card; the position sliders are gone.
- A Reset button for the SDR base look (exposure and highlight knee).
- Polish: per-capture warmth, contrast, vibrance and shadows sliders and a watermark field in the
  inspector, applied in linear light before the SDR base and the gain map are made. The curves
  fade out above SDR white so the HDR highlights stay exactly as captured, colours move around
  their own luminance, nothing exceeds the capture's own peak, and the source file is untouched.
  An HDR tab in the inspector shows the finished Ultra HDR picture in real HDR while you adjust.
  Polish is remembered with the list, can be applied to every card, and puts a converted card
  back to pending.
- Tiles size themselves to the list: one capture gets a large tile, a few share the width in two or
  three columns, and only a long list falls back to the dense grid. The grid refits whenever the
  window or the panes change.
- The source comparison opens fitted to the window; an "Actual pixels" button or a double-click on
  the picture zooms to 1:1 at that spot, and the image can then be dragged to pan.
- The layout now adapts to the window: panes shrink to the space available and the oldest one closes
  when the window cannot hold them all, the bottom bar wraps on narrow windows, and the viewer's
  controls, compare stage and details panel fit windows down to 960 by 640.
- The file list survives restarts. Cards, their status, statistics and results are written to
  `session.json` beside the settings and come back at the next launch, with thumbnails served from
  an on-disk cache so nothing is decoded again. A card whose outputs have been deleted returns to
  pending, a capture that has gone missing is dropped, and the most recent 500 cards are kept.
  Writes happen off the UI thread at most once a second. "Remember the list" in Settings turns
  it off.
- "Clear finished" removes completed cards from the list.
- Settings and the log open as panes beside the file list, alongside the inspector, instead of
  covering the window.
- Distribution: a winget manifest with automatic submission on release, and MSIX packaging for
  the Microsoft Store (`packaging/msix`, guide in `docs/store.md`). The app detects a packaged run
  and defers start-up and "Open with" to the package manifest.
- Black-and-gold "Halo" identity, landing page on GitHub Pages, 4K HDR gallery.

### Fixed
- imagecodecs 2026.11 renamed the gain-map metadata fields it returns (boostmax, boostmin,
  gainmap_gamma) and made them scalars for single-channel maps; every reader now goes through one
  normaliser, so the encoder, the file details and the tests work with either release.
- The Convert button counted every card, including ones the watch folder had already converted; it now
  counts only files that still need converting and reads "All converted" when nothing is pending.

## [1.1.0] - 2026-11-11

### Added
- JPEG XR input (`.jxr`) from NVIDIA App and Windows Game Bar HDR screenshots, next to ReShade's JPEG XL.
- Watch folder: optional "include subfolders" (NVIDIA App keeps one subfolder per game).
- Start with Windows (Startup shortcut) and single-instance behaviour: a second launch hands its files to the running app.
- Optional "Convert with UltraShot" entry in Explorer's right-click menu for `.jxl` / `.jxr`.
- Window size and position are remembered.
- Standalone `UltraShot.exe` build (`build_exe.bat`, PyInstaller).

### Changed
- Renamed the app to UltraShot. Settings now live in `%APPDATA%\UltraShot\settings.json`.
- Watch folder and start-with-Windows are on by default; the watch folder defaults to `Videos\Captures`.

## [1.0.0] - 2026-11-11

### Added
- First release: drag-and-drop desktop app, live SDR preview with exposure / highlight-knee controls,
  highlights map, Instagram crop and resize, watch folder, tray mode, log drawer.
- Gain map target peak is matched to the gain map's real maximum boost, so phones apply the full HDR
  layer instead of a fraction of it (libultrahdr's default capacity of 10000 nits made the HDR look dim).
