# Changelog

All notable changes to UltraShot are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/).

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
