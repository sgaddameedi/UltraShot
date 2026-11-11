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
- "Clear finished" removes completed cards from the list.
- Black-and-gold "Halo" identity, landing page on GitHub Pages, 4K HDR gallery.

### Fixed
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
