# Privacy statement

UltraShot runs entirely on your computer. It does not connect to the internet, does not collect or
transmit any data, does not use analytics or crash reporting, and does not require an account. The
only files it reads are the screenshots you give it, and the only files it writes are the converted
images in the folders you choose and its own settings in `%APPDATA%\UltraShot`. Nothing leaves your
machine unless you share the resulting images yourself.

The video editor works the same way. Recordings are read from where they are and streamed to the
window's player over a connection that exists only inside your computer, on the loopback address,
under a random token for each opened file, and that is closed when the application quits. The only
files it writes are the exports you ask for and, for a recording the window cannot decode, a small
preview copy in `%LOCALAPPDATA%\UltraShot\proxies`, a cache that never grows past six gigabytes
and can be deleted at any time. The one optional download is FFmpeg itself: the *Get FFmpeg* chip
fetches the essentials build from gyan.dev, checks its published checksum and unpacks it under
`%LOCALAPPDATA%\UltraShot`, and nothing is sent in that request beyond the download itself. An
FFmpeg already installed on the system is used instead and no download happens.

This applies to every distribution of UltraShot: the zip release, the winget package and the
Microsoft Store package.
