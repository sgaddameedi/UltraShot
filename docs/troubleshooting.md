# Troubleshooting

Most problems fall into one of three groups: the application itself, the conversion, or the way the
result is displayed somewhere else. Whichever it is, the Log drawer (the terminal icon in the top bar)
is the first place to look. Every conversion records the decoded format and resolution, the peak
brightness of the capture, the range of the gain map, and the peak brightness that an HDR viewer will
reconstruct from the finished file. Failures are logged with a full traceback, and that traceback is
the most useful thing to include in a bug report.

## The application

**Double-clicking UltraShot.exe appears to do nothing.** In almost every case an instance is already
running in the system tray, and the new launch has handed over to it and exited, which is the intended
behaviour. Look for the UltraShot icon near the clock and choose *Open UltraShot* from its menu. If you
genuinely need a second instance, for example a development copy alongside an installed one, start it
with the `--new-instance` flag.

**The window opens but is blank.** The user interface runs inside the Edge WebView2 runtime, which is
part of Windows 11 and of every recently updated Windows 10 installation. If it has been removed or
is damaged, reinstall it from Microsoft's WebView2 download page (the "Evergreen Bootstrapper").

**Dropping files has no effect.** Only `.jxl` and `.jxr` files are accepted, because those are the
formats the capture tools write for HDR. PNG, JPEG and HEIC files are not HDR captures. Dropped folders
are searched one level deep.

**The watch folder does not notice new captures.** Confirm the folder in Settings, and that *Include
subfolders* is enabled if the captures come from the NVIDIA App, which keeps one subfolder per game.
When a capture is detected the log records "new capture: …" followed by the file name. If the capture
tool writes large files slowly, increasing the *Stable for* interval gives it more time to finish
before UltraShot reads the file.

**Start with Windows stopped working after moving the application.** The Startup shortcut points at the
copy of UltraShot that created it. Opening the application once from its new location refreshes the
shortcut, as it does the Explorer menu entry.

## The conversion

**"input looks like an SDR screenshot, not HDR".** The file contains 8-bit image data, which means the
capture was taken while the game, or Windows itself, was not in HDR mode. HDR has to be enabled in
Windows display settings and in the game's own graphics settings.

**"input is not a JPEG XL or JPEG XR file".** The file has the right extension but the wrong contents,
or it was truncated while being written. Taking the capture again is the only remedy.

**The full-size output is very large.** Files of fifteen to twenty megabytes are normal for a 4K
capture. The base image and the gain map are both encoded at quality 100 with 4:4:4 chroma, and the
gain map is stored at full resolution because that is what preserves fine highlight detail. The
Instagram copy is the one intended for uploading; if you need smaller full-size files, lower the
*JPEG quality* setting.

**Conversion takes several seconds per capture.** Decoding a lossless 4K JPEG XL and encoding two
JPEGs at quality 100 is processor-bound work, and six to ten seconds is typical. The watch folder
deliberately converts one capture at a time so that a burst of screenshots does not compete with the
game for the processor.

## The result

**The image looks like ordinary SDR on a phone.** The viewing application must support gain maps and
the display must be in a mode that permits HDR. Google Photos, Chrome, Instagram, Threads and Samsung
Gallery all render gain maps; many other gallery and messaging applications do not. Transferring the
file through WhatsApp, Telegram, Discord or email as a photo re-encodes it and removes the gain map.
Sending it as a file or document, or through cloud storage, preserves it.

**The image looks like ordinary SDR in Windows Photos.** Windows Photos does not render gain maps.
Chrome and Edge do, so opening the file in either browser on an HDR monitor is the reliable way to
check a result on the desktop.

**Instagram shows the post dim, or without HDR.** The upload flow applied a crop, zoom or filter, or
the upload came from an iPhone, either of which removes the gain map. The procedure in
[instagram.md](instagram.md) avoids both.

**Highlights appear clipped on an HDR display.** Compare the two peak values in the log: the capture's
peak and the "HDR layer after encode" peak should agree to within a few percent. If they do not,
please open an issue and attach the capture, since this indicates a problem in the encoder rather
than in the viewer.

**The SDR version is too dark or too flat.** Adjust *SDR exposure* and *Highlight knee* in the
inspector while watching the preview. These settings shape only the base image; the HDR layer is the
same whatever you choose.
