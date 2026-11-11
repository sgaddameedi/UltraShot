# How UltraShot works

The entire conversion pipeline is contained in one module, `jxl2uhdr.py`, and the desktop application
is a shell around it: it decides which files to convert and with which settings, and the module does
the work. This document follows a capture through that module from the file on disk to the finished
Ultra HDR JPEG, and explains the decisions that were made along the way.

## Decoding to absolute luminance

The first step converts whatever the capture tool wrote into a single, unambiguous representation:
a floating-point image whose values are absolute luminance in nits, per channel. The three kinds of
input reach that representation by different routes.

| Input | Decoded as | Conversion to nits |
| --- | --- | --- |
| scRGB (float JXL, JXR) | Float, linear light, BT.709 primaries | Multiply by 80, since scRGB defines 1.0 as 80 nits |
| HDR10 (16-bit JXL) | PQ code values, BT.2100 primaries | The SMPTE ST 2084 EOTF, giving 0 to 10,000 nits |
| HLG (16-bit JXL) | HLG code values, BT.2100 primaries | The BT.2100 inverse OETF followed by the OOTF for a 1,000-nit display with a system gamma of 1.2 |

Negative scRGB values, which encode colours outside the BT.709 gamut, are clamped to zero. From this
point onward the HDR data is changed by only two operations, both of them geometric and both carried
out in linear light: cropping to an aspect ratio, positioned by percentage of the frame, and resizing
with a Lanczos filter, applied through Pillow's floating-point mode one channel at a time. Resizing in
linear light rather than on gamma-encoded values is what keeps small bright highlights from darkening
when the image is reduced.

## Rendering the SDR base image

An Ultra HDR viewer reconstructs the HDR image from the base JPEG and the gain map together, so the
base image serves two purposes at once: it is the picture that SDR viewers see, and it is half of the
data from which HDR viewers rebuild the original. libultrahdr can generate this image itself, and the
*Automatic SDR base* setting uses that path, but by default UltraShot renders the base image in its
own code so that it can be controlled and, more importantly, previewed before conversion.

The rendering proceeds in five steps. If the source uses BT.2100 primaries it is first converted to
BT.709 with a 3×3 matrix. The values are then scaled so that 1.0 corresponds to 203 nits, the SDR
reference white defined in BT.2100, and the exposure adjustment is applied as a power of two of the
chosen number of stops. Luminance is computed from the three channels, and everything below the knee,
which defaults to 0.6 or about 122 nits, is left exactly as it is. Luminance above the knee is passed
through a rational shoulder, `knee + (1 − knee) · x / (x + 1 − knee)` where `x` is the excess over the
knee, which approaches 1.0 asymptotically; the practical effect is that a 300-nit highlight and a
1,000-nit highlight remain distinguishable in the SDR image rather than both becoming the same white.
The resulting gain is applied equally to all three channels so that hues are preserved, after which any
channel that still exceeds 1.0 is pulled toward the pixel's luminance instead of being clipped, which
avoids the hue shifts that per-channel clipping produces in saturated highlights. Finally the sRGB
transfer function is applied and the image is quantised to eight bits.

## Encoding the gain map

The linear image, converted to half-precision float with 1.0 representing 203 nits, and the SDR base
image are passed to libultrahdr through `imagecodecs.ultrahdr_encode`. Four choices are made at this
point. The gain map is computed per channel rather than as a single luminance gain, which keeps
saturated highlights accurate. It is stored at full resolution rather than the default quarter
resolution, which preserves fine detail in highlights at the cost of file size. Both the base image and
the gain map are encoded at quality 100 with 4:4:4 chroma subsampling. And the encoder is asked to
optimise for quality rather than speed.

## Why the declared display capacity matters

The Ultra HDR metadata includes two values, `HDRCapacityMin` and `HDRCapacityMax`, that describe the
range of display headroom over which the gain map should be applied. A viewer computes a weight from
its own display's headroom, meaning how much brighter than SDR white the screen can currently go, and
applies the gain map in proportion to that weight:

```
weight = clamp((log2(headroom) − log2(capacity_min)) / (log2(capacity_max) − log2(capacity_min)), 0, 1)
pixel  = base × 2 ^ (gain × weight)
```

The consequence is that if `capacity_max` is set far above what the image actually contains, every
display with less headroom than that number applies only part of the gain map. libultrahdr derives
`capacity_max` from a target display peak that defaults to 10,000 nits, which corresponds to a capacity
of about 49 times SDR white, whereas the gain map of a typical game capture tops out at around five
times, or 1,000 nits. On a phone with four times headroom, which is a common figure, the difference is
stark.

| Declared capacity | Weight applied | An 891-nit highlight is shown as |
| --- | --- | --- |
| 49× (the library default) | 0.36 | about 360 nits |
| Matched to the gain map (UltraShot) | 0.87 | about 810 nits |

UltraShot therefore encodes once, reads the gain map's actual maximum boost back out of the file, and
if the declared capacity differs from it by more than two percent, encodes a second time with the
target peak set to exactly that value, within the 250 to 10,000-nit range the library accepts. The
log line that confirms this reads, for example, "gain map: max boost 4.92x (1000 nits), fully applied
from 4.92x display headroom". The `--peak-nits` option on the command line, and the *Gain map target
peak* setting in the application, override the automatic choice when a specific value is wanted.

## Signalling the gain map to every reader

libultrahdr 2.x writes the ISO 21496-1 metadata that Android 15, iOS 18 and current versions of Chrome
read. Older Android releases and Adobe's applications look instead for the earlier `hdrgm` XMP form,
so UltraShot adds that as well: an XMP packet inside the gain-map image carrying the same parameters,
and a container directory in the primary image whose declared gain-map length matches the embedded
JPEG. The primary image's XMP is inserted ahead of the MPF segment so that the MPF offsets, which
point to the gain-map image, remain valid.

As a last step the finished file is decoded again and the peak brightness that an HDR viewer will
reconstruct is written to the log alongside the peak of the source, so that a problem in the encoder
can never pass silently.

## Verifying a file yourself

The same library that UltraShot uses can inspect any Ultra HDR JPEG:

```python
import imagecodecs as ic
import numpy as np

data = open("out.jpg", "rb").read()
print(ic.ultrahdr_check(data))                                  # True for a valid Ultra HDR file
base, gainmap, meta = ic.ultrahdr_decode_jpeg(data)             # the two JPEGs and the metadata
hdr = ic.ultrahdr_decode(data, dtype=np.float16)[..., :3] * 203  # linear nits, as a viewer sees them
print(meta["max_content_boost"], meta["hdr_capacity_max"], hdr.max())
```
