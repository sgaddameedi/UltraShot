# Settings reference

Settings live in `%APPDATA%\UltraShot\settings.json` and are written whenever you change something.
Delete the file to reset everything.

## General

| Setting | Default | What it does |
| --- | --- | --- |
| Theme | Dark | Dark, light or follow Windows |
| Notifications | On | Tray balloon when a conversion finishes while the window is hidden |

## Output

| Setting | Default | What it does |
| --- | --- | --- |
| Full size | On | Full-resolution Ultra HDR JPEG into the *4K HDR* subfolder |
| Instagram | On | Downscaled copy into the *Insta* subfolder |
| Width | 1440 px | Width of the Instagram copy. Instagram stores 1440 px; anything wider is resized by Instagram, which strips the gain map |
| Crop | Original | Aspect ratio of the Instagram copy. Position it in the inspector |
| Subfolder names | `4K HDR`, `Insta` | Free text |

## Saving

| Setting | Default | What it does |
| --- | --- | --- |
| Save to | Next to each original | Or one fixed folder for everything |
| Keep the capture date | On | Outputs get the capture's modified time, so galleries sort them with the original |
| Overwrite existing outputs | Off | Off: a capture whose outputs exist is skipped (safe to re-run on a folder) |
| File name suffix | none | e.g. `_hdr` |

## Watch folder

| Setting | Default | What it does |
| --- | --- | --- |
| Convert new captures automatically | On | Polls the folder and converts each new `.jxl` / `.jxr` once its size has been stable for the settle time and it is no longer locked by the capture tool |
| Folder | `Videos\Captures` | Falls back to `Pictures\Screenshots`, then `Videos\NVIDIA` |
| Include subfolders | On | Two levels deep; the output subfolders are skipped |
| Also convert files already there | Off | Off: only captures made after watching starts |
| Stable for | 3 s | Raise it if your capture tool writes slowly |

## Background

| Setting | Default | What it does |
| --- | --- | --- |
| Keep running in the tray | On | Closing the window hides it; quit from the tray menu |
| Start with Windows | On | Shortcut in your Startup folder that launches UltraShot hidden with `--tray` |
| "Convert with UltraShot" in Explorer | Off | Right-click entry for `.jxl` / `.jxr`, registered for the current user only |

## Fine-tuning

| Setting | Default | What it does |
| --- | --- | --- |
| Automatic SDR base | Off | Let libultrahdr tone-map the base image (ignores exposure and knee) |
| SDR exposure | 0 st | Brightness of the SDR base in stops. HDR layer unaffected |
| Highlight knee | 0.6 | Where the SDR roll-off starts (1.0 = 203 nits). Lower keeps more highlight detail and looks flatter |
| JPEG quality | 100 | Base image and gain map |
| Limit HDR peak | 0 (off) | Soft-limits the HDR layer's highlights to this many nits, with a roll-off from 75 % of it. Set it to your monitor's peak (often 1000) when a capture carries brighter highlights than the display showed and phones render it hotter than you remember. The only setting that alters the HDR layer |
| Gain map target peak | 0 (auto) | Auto matches the gain map's real maximum. 250–10000 to force a value |
| Input transfer | Auto | Float = scRGB, 16-bit = PQ. Set HLG for HLG games |

## Command-line flags

| Flag | Effect |
| --- | --- |
| `UltraShot.exe file1.jxl file2.jxr` | Converts those files (a running instance picks them up) |
| `--tray` | Start hidden in the tray (what the Startup shortcut uses) |
| `--new-instance` | Do not hand over to a running instance |
| `--debug` | Opens WebView2 developer tools |
