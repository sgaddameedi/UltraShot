# Publishing UltraShot on the Microsoft Store

The Store build of UltraShot is an MSIX package produced by `packaging/msix/build_msix.ps1` from the
same PyInstaller output as the zip release. The Store signs the package itself, so no code-signing
certificate is needed, and it handles installation, updates and uninstallation. This guide walks
through the one-time account setup, the package build, and the submission, and lists the text to
paste into the listing. Everything here happens in [Partner Center](https://partner.microsoft.com/dashboard).

## One-time setup

**Developer account.** Open Partner Center, choose *Windows & Xbox*, and register as an individual
developer. There is a one-off registration fee (about 19 US dollars for individuals) and Microsoft
verifies your identity, which usually takes a day or two. The publisher display name you choose here
is what the Store shows under the app name.

**Reserve the name.** Under *Apps and games*, create a new app and reserve the name `UltraShot`. Once
reserved, open *Product management → Product identity*. It shows three values you need for the
package:

| Partner Center value | Goes into |
| --- | --- |
| Package/Identity/Name (looks like `12345YourName.UltraShot`) | `-IdentityName` |
| Package/Identity/Publisher (looks like `CN=12345678-ABCD-…`) | `-Publisher` |
| Package/Properties/PublisherDisplayName | `-PublisherDisplayName` |

## Building the package

From the repository root, with Python and the project's dependencies installed:

```powershell
.\packaging\msix\build_msix.ps1 -Version 1.1.0.0 -IdentityName "12345YourName.UltraShot" -Publisher "CN=12345678-ABCD-…" -PublisherDisplayName "Your Name"
```

The script builds the app, renders the tile and icon assets from the app icon, stages everything with
`AppxManifest.xml` (identity and version substituted), fetches `makeappx` from the Windows SDK build
tools on first use (into `packaging/msix/tools`, nothing is installed system-wide), and writes
`dist\UltraShot.msix`. The version must be four numbers and must increase with every submission;
the Store rejects a package whose version is not higher than the live one.

Do not sign the package you upload. The `-Sign` switch exists only for installing a test build on
your own PC: it creates a self-signed certificate matching the publisher, signs the package, and
exports `dist\UltraShot-test.cer`. Installing that build requires the certificate to be trusted by
the machine (an administrator imports it into *Local Machine → Trusted People*), after which
`Add-AppxPackage dist\UltraShot.msix` installs it like a Store app.

## What is different inside the Store build

The app detects that it is running from a package and adapts two behaviours that an MSIX container
would otherwise silently virtualise:

- *Start with Windows* is provided by the package's startup task instead of a Startup-folder
  shortcut. Store policy requires it to be off by default; the user turns it on under Windows
  *Settings → Apps → Startup*, and the app's own switch opens that page. When Windows starts the
  app at sign-in, it opens hidden in the tray.
- The Explorer entry is a file-type association instead of a registry key: `.jxl` and `.jxr` files
  gain "Open with UltraShot", and the command `ultrashot` works from any terminal.

Everything else, including the watch folder, settings in `%APPDATA%\UltraShot`, conversion and the
tray, is unchanged.

## Submitting

In the app's dashboard start a new submission and work through the sections. The ones that need
real input are below; the rest can be left at their defaults.

**Packages.** Upload `dist\UltraShot.msix`. Partner Center validates the manifest and reports any
problem on the spot; the identity values must match what it issued. Two messages are expected.
Under *Device family availability* leave only *Windows 10/11 desktop* ticked, since the package
is x64 desktop only and every other family would need a package of its own. The warning that
*runFullTrust* is a restricted capability is normal for a packaged desktop app: the *Submission
options* section has a box for restricted-capability justification, and this text is enough:

  > UltraShot is a packaged Win32 desktop application (Python runtime with a WebView2 window). Full
  > trust is required to run the native image codecs, read the user's screenshot folder that the
  > app watches, write converted files next to the originals, and place an icon in the system tray.
  > The app makes no network connections and collects no data.

Approval is granted as part of certification, not in advance.

**Pricing and availability.** Free, all markets. If you later decide to charge, this is where the
price goes; the source stays open either way.

**Properties.** Category *Photo & video*. Privacy policy URL: UltraShot has no network access and
collects nothing, and Partner Center still asks for a URL when the app declares any capability. Use
`https://github.com/sgaddameedi/UltraShot/blob/main/docs/privacy.md` (a one-paragraph statement
that the app sends no data anywhere). System requirements: Windows 10 version 1809 or later, x64.

**Age ratings.** The questionnaire asks about violence, user interaction, data sharing and similar.
A converter with no network access answers "no" to everything and receives an all-ages rating.

**Store listing (English).** Ready-to-paste text:

- *Description:*

  > UltraShot turns HDR game screenshots into Ultra HDR JPEGs: ordinary JPEG files that carry a gain map, so Instagram, Threads, Google Photos, Chrome, Edge and Android phones display them in HDR while every other screen shows a correct SDR image. It reads the lossless JPEG XL files written by ReShade and the JPEG XR files written by the NVIDIA App and the Windows Game Bar, never alters the HDR data, writes gain-map metadata that phones apply in full, and prepares an Instagram-sized copy so nothing has to change during upload. A watch folder converts new captures automatically; the app runs from the tray and can start with Windows. Free and open source.

- *What's new in this version:* copy the matching section of `CHANGELOG.md`.
- *App features* (one per line): Converts ReShade .jxl and NVIDIA / Game Bar .jxr HDR captures; Ultra HDR JPEG output that stays HDR on Instagram, Threads, Google Photos and Chrome; Watch folder converts new captures automatically; Live SDR preview with exposure and highlight controls; Instagram-ready crop and resize; Runs from the tray, starts with Windows.
- *Screenshots:* 1920×1080 captures of every screen are produced by
  `SHOT_W=1920 SHOT_H=1080 SHOT_OUT=packaging/msix/store-listing/screenshots python tools/screenshots.py`
  (on PowerShell set the three variables with `$env:` first). Upload `main`, `inspector`,
  `instagram-crop`, `highlights-map`, `compare`, `file-details`, `panes-side-by-side` and
  `settings`.
- *Store logos:* `python packaging/msix/make_store_images.py` renders every image slot the
  listing offers into `packaging/msix/store-listing/`: the 300, 150 and 71 pixel tile icons,
  1:1 box art, 2:3 and 9:16 poster art, 16:9 super hero art at 4K and HD, and 2:1 promotional
  art. `packaging/msix/store-listing.md` maps each file to its slot and holds the listing text.
- *Search terms:* HDR screenshot, Ultra HDR, gain map, Instagram HDR, ReShade, JXR, JXL.
- *Copyright and trademark:* `© 2026 Sharath Gaddameedi. MIT licence.`
- *Support contact:* the GitHub issues page.

**Submission options.** Publish as soon as it passes certification. Certification takes one to three
days for a package like this; the report arrives by email and in the dashboard.

## Updating

Every tagged release builds the Store package automatically: the release workflow runs
`build_msix.ps1` with the identity values and attaches `UltraShot-vX.Y.Z.msix` to the GitHub
release next to the zip. To update the Store listing, download that file from the release page,
start a new submission in Partner Center (it copies the previous listing forward), upload the
package, and submit. Users receive the update through the Store automatically. The package version
is the tag with a fourth `.0` component, so tags must keep increasing.
