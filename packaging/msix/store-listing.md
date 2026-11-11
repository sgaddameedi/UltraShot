# UltraShot: Microsoft Store listing

Everything below is ready to paste into Partner Center, section by section, in the order the
submission presents them. Image files are in `packaging\msix\store-listing\` after running
`python packaging/msix/make_store_images.py` and the screenshot command from `docs/store.md`.

## Pricing and availability

- Base price: **Free**
- Markets: **All markets**
- Discoverability: **Make this product available and discoverable in the Store**
- Schedule: publish as soon as it passes certification

## Properties

- Category: **Photo & video**
- Subcategory: leave empty
- Privacy policy URL: `https://github.com/sgaddameedi/UltraShot/blob/main/docs/privacy.md`
- Website: `https://sgaddameedi.github.io/UltraShot/`
- Support contact info: `https://github.com/sgaddameedi/UltraShot/issues`
- Game settings, display mode, accessibility: leave unchecked
- System requirements, minimum: OS **Windows 10 version 1809 (build 17763) or later**, architecture **x64**, memory **2 GB**, DirectX **not required**, video memory **not required**
- System requirements, recommended: memory **8 GB**, and add a note that an HDR display is needed to see the HDR result in the built-in viewer (the conversion itself works on any display)

## Age ratings

Answer **No** to every question in the IARC questionnaire (no violence, no user interaction, no
sharing of personal information, no purchases, no location). The result is an all-ages rating.

## Packages

- Upload `dist\UltraShot.msix`
- Device family availability: tick **Windows 10/11 desktop** only
- The *runFullTrust* warning is expected; its justification goes under Submission options

## Store listing, English (United States)

### Description

UltraShot turns HDR game screenshots into pictures you can actually share. Games running in HDR produce captures that look spectacular on the display they were taken on and then fall apart the moment they leave it: ReShade writes JPEG XL files, the NVIDIA App and the Windows Game Bar write JPEG XR, and neither format is understood by Instagram, Threads, Google Photos, messaging apps or most browsers. The usual fix is to convert to an ordinary JPEG, which throws the HDR away and leaves a flat, washed-out image of a moment that was anything but.

UltraShot converts those captures into Ultra HDR JPEGs. An Ultra HDR file is a normal JPEG with a gain map embedded in it, the format Android, Chrome, Edge and Instagram already support. A screen without HDR shows a carefully tone-mapped SDR image, and an HDR screen reconstructs the full brightness of the original capture, highlight for highlight. The file is a single .jpg, it uploads anywhere a JPEG uploads, and Instagram keeps the HDR layer intact instead of flattening it.

The HDR data is never altered. UltraShot reads the capture at its full precision, measures its real peak brightness and writes gain-map metadata that matches it exactly, so phones apply the complete HDR layer rather than a fraction of it. You control the SDR side with a live preview: exposure and a highlight knee shape how the picture looks on ordinary screens, a highlights map shows where the HDR lives, and an Instagram-sized copy with a chosen crop is produced alongside the full-resolution file so nothing has to change at upload time.

A watch folder converts new captures automatically as you play, the app lives in the system tray and can start with Windows, and the built-in viewer shows the finished files in HDR on an HDR display. Compare lets you wipe between the SDR base and the HDR rendering, or between the original capture and the finished file at actual pixels, with measured error figures, so you can see for yourself that nothing was lost. A details panel reads the finished JPEG back from disk and lists everything it contains, from chroma subsampling and the colour profile to the gain-map metadata and the peak brightness a phone will reconstruct.

UltraShot runs entirely on your PC. It makes no network connections, collects no data and needs no account. It is free and open source under the MIT licence; the code, documentation and a gallery of 4K HDR examples are at github.com/sgaddameedi/UltraShot.

Supported input: JPEG XL (.jxl) from ReShade, including scRGB float and PQ 16-bit captures; JPEG XR (.jxr) from the NVIDIA App and the Windows Game Bar. Output: Ultra HDR JPEG with an ISO 21496-1 and Adobe gain map, quality 100, 4:4:4 chroma.

### What's new in this version

UltraShot 1.1 adds JPEG XR input for NVIDIA App and Game Bar captures, a watch folder that can include subfolders, start with Windows, a result viewer that shows converted files in HDR with a side-by-side compare and a file-details panel, an optional limit on HDR peak brightness for captures brighter than your display, and a file list that survives restarts. Settings and the log open as panes beside the file list.

### Product features

One per line, each under 200 characters:

- Converts ReShade JPEG XL and NVIDIA App / Game Bar JPEG XR HDR screenshots into Ultra HDR JPEGs
- Output stays HDR on Instagram, Threads, Google Photos, Chrome, Edge and Android phones
- The HDR data is never altered; the gain map is matched to the capture's real peak brightness
- Live preview of the SDR base image with exposure and highlight-knee controls
- Highlights map shows which pixels exceed SDR white and which exceed 1000 nits
- Instagram-ready copy with 4:5, 1:1, 16:9, 9:16 or 1.91:1 crop and adjustable framing
- Watch folder converts new captures automatically while you play
- Built-in viewer shows results in HDR, with a wipe between SDR and HDR or source and output
- File details panel reads the finished JPEG back and lists every tag and the gain-map metadata
- Runs from the system tray and can start with Windows
- Works entirely offline, collects no data, needs no account
- Free and open source under the MIT licence

### Screenshots

Desktop, 1920×1080, from `packaging\msix\store-listing\screenshots\`. Upload in this order with these captions:

1. `main.png`: Drop HDR captures on the window, or let the watch folder pick them up as you play
2. `inspector.png`: A live preview of the SDR base image with exposure and highlight-knee controls
3. `compare.png`: Compare the original capture with the finished file at actual pixels, with measured error
4. `highlights-map.png`: The highlights map shows where the HDR lives: orange above SDR white, pink above 1000 nits
5. `instagram-crop.png`: An Instagram copy with a 4:5 crop and position controls, carrying the full gain map
6. `file-details.png`: Every tag in the finished JPEG, read back from disk, down to the gain-map metadata
7. `panes-side-by-side.png`: Inspector and settings open side by side next to the file list
8. `settings.png`: Output, saving, watch folder and fine-tuning settings

### Store logos and additional art

All from `packaging\msix\store-listing\`, one file for every slot Partner Center offers. The three
tile icons and the 16:9 image matter most: the tile icons are what Windows shows in the Store
app and the Start menu, and the 16:9 image is the large header on the product page.

| Partner Center slot | Size | File |
| --- | --- | --- |
| App tile icon 1:1 | 300×300 | `store-logo-300x300.png` |
| App tile icon 1:1 | 150×150 | `store-logo-150x150.png` |
| App tile icon 1:1 | 71×71 | `store-logo-71x71.png` |
| Box art 1:1 | 1080×1080 | `store-box-1080x1080.png` |
| Poster art 2:3 | 720×1080 | `store-poster-720x1080.png` |
| Poster art 9:16 | 1080×1920 | `store-poster-1080x1920.png` |
| Super hero art 16:9 (4K) | 3840×2160 | `store-hero-3840x2160.png` |
| Super hero art 16:9 (HD), if 4K is refused | 1920×1080 | `store-banner-1920x1080.png` |
| Promotional art 2:1 | 2400×1200 | `store-poster-2400x1200.png` |

Partner Center accepts either size where it lists two; upload the 4K hero art, which the Store
scales down for smaller placements. Slots the dashboard does not show can be ignored.

### Additional information

- Short title: `UltraShot`
- Sort title: `UltraShot`
- Voice title: `Ultra Shot`
- Short description (under 500 characters): HDR game screenshots, shared in HDR. UltraShot converts ReShade and NVIDIA / Game Bar captures into Ultra HDR JPEGs that stay HDR on Instagram, Threads, Google Photos, Chrome and Android phones, and look right everywhere else. Free, open source, fully offline.
- Search terms (up to seven, each under 30 characters): `HDR screenshot`, `Ultra HDR`, `gain map`, `Instagram HDR`, `ReShade JXL`, `JXR converter`, `HDR to JPEG`
- Copyright and trademark info: `© 2026 Sharath Gaddameedi. Released under the MIT licence.`
- Additional licence terms: `MIT licence: https://github.com/sgaddameedi/UltraShot/blob/main/LICENSE`
- Developed by: `Sharath Gaddameedi`

## Submission options

- Publishing hold options: **Publish this submission as soon as it passes certification**
- Restricted capabilities justification (runFullTrust):

  > UltraShot is a packaged Win32 desktop application (Python runtime with a WebView2 window). Full trust is required to run the native image codecs, read the user's screenshot folder that the app watches, write converted files next to the originals, and place an icon in the system tray. The app makes no network connections and collects no data.

- Notes for certification:

  > No account or sign-in is needed. To test a conversion, download the sample HDR capture at https://github.com/sgaddameedi/UltraShot/raw/main/examples/sample-hdr10.jxl and drop it on the window; the converted JPEG appears in a "4K HDR" folder next to the original and an Instagram copy in "Insta". The watch folder defaults to Videos\Captures and only reacts to files created after the app starts. An HDR display is required only to see the HDR result in the built-in viewer; the conversion works on any display.
