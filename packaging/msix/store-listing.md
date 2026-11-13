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

UltraShot 1.2 adds a Polish section with warmth, contrast, vibrance and shadow sliders and a watermark, applied in a way that leaves the HDR highlights exactly as captured, with an HDR preview that shows the finished picture in real HDR while you adjust. Instagram framing now works the way Instagram's own editor does: drag the picture inside the crop window, per capture. The viewer gains a compare mode that wipes between the SDR base and the HDR rendering or between the capture and the finished file at actual pixels, with error figures, and a file details panel that reads every tag back from the finished JPEG. The list survives restarts, tiles size themselves to the list, there is search, filter and sort, a right-click menu on every card, Convert again for replacing earlier outputs, and panes that can be rearranged and resized.

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

Desktop, 1920×1080, from `packaging\msix\store-listing\slides\`, produced by
`python tools/store_slides.py`. Each slide shows one feature large on a frameless capture of the
app running on the 4K gallery pictures, with its own headline, so the Store page reads as a tour
rather than a row of small windows. Upload in this order; the caption field can stay empty since
the headline is in the picture, or carry the short line given here:

1. `01-drop.png`: Drop ReShade and NVIDIA / Game Bar captures, or let the watch folder pick them up
2. `02-viewer.png`: The built-in viewer shows the finished files in real HDR on an HDR display
3. `03-compare.png`: Wipe between what SDR screens see and what HDR screens see
4. `04-polish.png`: Warmth, contrast, vibrance, shadows and a watermark, with the HDR left intact
5. `05-frame.png`: Frame the Instagram copy by dragging the picture inside the crop window
6. `06-details.png`: Every tag in the finished JPEG, read back from the file
7. `07-highlights.png`: The highlights map shows where the HDR lives
8. `08-settings.png`: Watch folder, tray, start with Windows and the output settings

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
- Short description. The Store shows only the first line or two of this field on tiles and in search
  results, so the core function must come first and each version must read as a complete thought.
  Primary, 213 characters:

  > Converts HDR game screenshots from ReShade, the NVIDIA App and Game Bar into Ultra HDR JPEGs: ordinary JPEGs with a gain map that stay HDR on Instagram, Google Photos, Chrome and phones, and look right on any screen.

  If that is clipped where you look at it, 162 characters:

  > Converts ReShade and NVIDIA / Game Bar HDR screenshots into Ultra HDR JPEGs that stay HDR on Instagram, Google Photos, Chrome and phones, and look right everywhere.

  And for a single tile line, 95 characters:

  > Turn HDR game screenshots into Ultra HDR JPEGs that stay HDR on Instagram, phones and the web.

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
