# Capturing HDR screenshots

UltraShot can only keep what the capture tool saved. This page covers the three tools that write
real HDR files on Windows and the settings that matter.

Before any of them: the game must actually be rendering in HDR. Turn on **Use HDR** in Windows
(Settings → System → Display) and enable HDR in the game. If either is off, the capture tools save
an 8-bit SDR image and UltraShot reports "input looks like an SDR screenshot".

## ReShade (recommended)

ReShade 6.x can save HDR screenshots losslessly as JPEG XL.

1. Open the ReShade overlay (Home by default) → **Settings** tab.
2. Under *Screenshots*, set the format to **JPEG XL** and choose a screenshot folder (the default
   is the game's own folder; `Videos\Captures` keeps everything in one place for the watch folder).
3. Take screenshots with the ReShade screenshot key (PrtScn by default).

What you get depends on the game's HDR mode:

- **scRGB games** (most modern titles): float16, linear light, BT.709 primaries, 1.0 = 80 nits.
- **HDR10 games**: 16-bit PQ (sometimes HLG), BT.2100 primaries.

UltraShot detects both automatically (float = scRGB, 16-bit = PQ). If a game uses HLG, set
*Input transfer* to HLG in Settings → Fine-tuning.

## NVIDIA App / GeForce Experience

Press **Alt+F1** in an HDR game. NVIDIA writes a `.jxr` (JPEG XR, float scRGB) into
`Videos\NVIDIA\<Game name>\`. Point UltraShot's watch folder at `Videos\NVIDIA` and keep
**Include subfolders** on, so every game's folder is covered.

NVIDIA also writes an SDR `.png` next to the `.jxr`; UltraShot ignores PNGs.

## Windows Game Bar

Press **Win+Alt+PrtScn** in an HDR game. Windows saves a `.jxr` to `Videos\Captures`, which is
UltraShot's default watch folder, so new captures convert without doing anything else.

## Tips for better results

- Capture at the resolution you want to share. UltraShot downsizes in linear light for the
  Instagram copy, but it will not invent detail for an upscale.
- Peak brightness is the game's business. A scene with "891 nits" on the card means the brightest
  pixel in the frame reaches 891 nits on a display that can show it; a dark interior might peak at
  300 nits and that is correct.
- The "subtle HDR" label only means few pixels exceed SDR white. It is not a warning.
