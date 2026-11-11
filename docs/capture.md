# Capturing HDR screenshots with ReShade, the NVIDIA App and the Windows Game Bar

UltraShot can only preserve what the capture tool recorded, so the quality of the result is decided
at capture time. This guide covers the three tools on Windows that write genuine HDR files and the
settings each one needs.

One requirement applies to all of them: the game must actually be rendering in HDR when the capture
is taken. That means HDR must be enabled in Windows, under Settings, System, Display, and in the
game's own graphics options. If either is off, every capture tool silently saves an 8-bit SDR image,
and UltraShot reports that the input looks like an SDR screenshot.

## ReShade

ReShade is the recommended source, because recent 6.x releases can save HDR screenshots losslessly in
the JPEG XL format. Open the ReShade overlay (the Home key by default), switch to the Settings tab, and
in the Screenshots section set the format to JPEG XL and choose a screenshot folder. The default folder
is the game's own directory; pointing every game at `Videos\Captures` keeps all captures in one place
and lets UltraShot's watch folder handle them without further configuration. Screenshots are then
taken with ReShade's screenshot key, PrtScn by default.

What the file contains depends on how the game presents HDR to Windows. Games using scRGB, which is
the majority of modern titles, produce float16 images in linear light with BT.709 primaries, where a
value of 1.0 corresponds to 80 nits. Games using HDR10 produce 16-bit PQ images, occasionally HLG,
with BT.2100 primaries. UltraShot recognises both automatically by inspecting the data type. For the
rare HLG title, set *Input transfer* to HLG under Settings, Fine-tuning.

## NVIDIA App and GeForce Experience

Pressing Alt+F1 in an HDR game saves a JPEG XR file containing float scRGB data, alongside an SDR PNG
that UltraShot ignores. The NVIDIA App writes these to `Videos\NVIDIA\<game name>`, one subfolder per
game, so the convenient configuration is to set UltraShot's watch folder to `Videos\NVIDIA` and leave
*Include subfolders* enabled.

## Windows Game Bar

Pressing Win+Alt+PrtScn in an HDR game saves a JPEG XR file, again with float scRGB data, to
`Videos\Captures`. This is UltraShot's default watch folder, so Game Bar captures convert without any
configuration at all.

## Getting the most from a capture

Capture at the resolution you intend to share. UltraShot resizes in linear light when it prepares the
Instagram copy, which downscales cleanly, but it cannot add detail to a capture that is smaller than
the output you want.

The peak brightness shown on each card describes the scene rather than the conversion. A night-time
interior may peak at 300 nits and a sunlit exterior at 1,500; both are correct, and both will be
reproduced exactly on a display that can show them. Likewise, the "subtle HDR" label simply means that
few pixels in the frame exceed SDR white, which is often true of a well-exposed scene and is not a
warning.
