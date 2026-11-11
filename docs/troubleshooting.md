# Troubleshooting

Open the **Log** drawer (terminal icon, top right) first. Every conversion logs the decoded format,
peak brightness, the gain-map range and the reconstructed peak, and failures include a traceback.

## The app

**Nothing happens when I double-click UltraShot.exe.** An instance is probably already running in
the tray (look for the icon near the clock); the new launch hands over to it and exits. Right-click
the tray icon → *Open UltraShot*.

**The window is blank.** Edge WebView2 is missing or broken. It ships with Windows 11 and recent
Windows 10 builds; reinstall it from Microsoft's "Evergreen Bootstrapper" page.

**Dropping files does nothing.** Only `.jxl` and `.jxr` files are accepted; PNG/JPG/HEIC are not
HDR captures. Folders are scanned one level deep.

**The watch folder does not pick up captures.** Check the folder in Settings, and that *Include
subfolders* is on for NVIDIA App captures. The log shows "new capture: …" when a file is detected.
If your capture tool writes slowly, raise *Stable for*.

**Start with Windows does nothing.** The Startup shortcut points at the exe that created it. If you
moved UltraShot, open it once from the new location; it refreshes the shortcut.

## Conversion

**"input looks like an SDR screenshot, not HDR".** The file is 8-bit. The game or Windows was not
in HDR mode at capture time.

**"input is not a JPEG XL or JPEG XR file".** The extension is wrong or the file is truncated.
Re-capture.

**The 4K output is huge (15–20 MB).** Expected: quality 100, 4:4:4, plus a full-resolution gain map.
The Instagram copy is the one to upload; lower *JPEG quality* if you need smaller full-size files.

**Conversion takes 6–10 s per capture.** Decoding a 4K lossless JXL and encoding two JPEGs at
quality 100 is CPU-bound. The watch folder runs one conversion at a time on purpose.

## The result

**It looks SDR on my phone.** The viewer must support gain maps (Google Photos, Chrome, Instagram,
Threads, Samsung Gallery). Transferring through WhatsApp, Telegram, Discord or email re-encodes the
file; send it as a *file*/document or use cloud storage.

**It looks SDR in Windows Photos.** Windows Photos does not render gain maps. Use Chrome or Edge on
an HDR monitor to check files on the desktop.

**Instagram shows it dim or SDR.** The upload crop/zoom/filter or an iPhone upload removed the gain
map. See [instagram.md](instagram.md).

**Highlights look clipped in HDR.** Check the log: "HDR layer after encode: peak N nits" should
match the source peak within a few percent. If it does not, open an issue with the capture.

**The SDR base is too dark / too flat.** Adjust *SDR exposure* and *Highlight knee* in the inspector
while watching the preview; the HDR layer is unaffected.
