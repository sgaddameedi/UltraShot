# How UltraShot works

The whole pipeline lives in `jxl2uhdr.py`; the app is a shell around it.

## 1. Decoding to absolute luminance

| Input | Decoded as | Conversion to nits |
| --- | --- | --- |
| scRGB (float JXL, JXR) | float, linear, BT.709 primaries | `nits = value × 80` |
| HDR10 (16-bit JXL) | PQ code values, BT.2100 primaries | ST 2084 EOTF, 0..10000 nits |
| HLG (16-bit JXL) | HLG code values, BT.2100 | BT.2100 inverse OETF + OOTF (1000-nit, γ 1.2) |

Everything after this point works on a float32 array of nits per channel. Negative scRGB values
(out-of-gamut) are clamped to zero.

The HDR layer is modified only by two geometric operations, both in linear light:

- **Crop** to an aspect ratio, positioned by percentage.
- **Resize** with Lanczos (through Pillow's float mode), one channel at a time.

## 2. The SDR base image

Ultra HDR viewers reconstruct HDR from the base JPEG and the gain map, so the base is both the SDR
fallback and half of the HDR reconstruction. UltraShot renders it itself rather than using
libultrahdr's automatic tone map, so you can control it and preview it:

1. Convert to BT.709 primaries if the source is BT.2100 (3×3 matrix).
2. Scale so 1.0 = 203 nits (BT.2100's SDR reference white), then apply the exposure (in stops).
3. Compute luminance. Below the **knee** (default 0.6, i.e. 122 nits) nothing changes. Above it a
   rational shoulder `knee + (1 − knee) · x / (x + 1 − knee)` rolls highlights off toward 1.0, so a
   300-nit and a 1000-nit highlight remain distinguishable instead of both clipping to white.
4. Apply the same gain to all three channels (hue preserving), then pull any channel that still
   exceeds 1.0 toward the pixel's luminance rather than clipping it.
5. sRGB OETF, 8-bit.

"Automatic SDR base" in Settings hands this step to libultrahdr instead.

## 3. Encoding the gain map

The linear image (as float16 RGBA, 1.0 = 203 nits) and the SDR base go to libultrahdr via
`imagecodecs.ultrahdr_encode` with:

- `multichannel=True`: one gain value per channel, not a single luminance gain, which keeps
  saturated highlights accurate.
- `scale=1`: full-resolution gain map (the default is quarter resolution).
- quality 100 for both JPEGs, 4:4:4 chroma.
- `usage=QUALITY`.

## 4. Why the target peak matters

Ultra HDR metadata carries `HDRCapacityMin` / `HDRCapacityMax`. A viewer computes

```
weight = clamp((log2(display headroom) − log2(capacity_min)) / (log2(capacity_max) − log2(capacity_min)), 0, 1)
pixel  = base × 2 ^ (gain × weight)
```

where *display headroom* is how much brighter than SDR white the screen can currently go. If
`capacity_max` is far above what the content actually contains, every display with less headroom
than that number applies only a fraction of the gain map.

libultrahdr derives `capacity_max` from a *target display peak* that defaults to 10000 nits
(capacity ≈ 49×), while a typical capture's gain map tops out around 5× (1000 nits). On a phone
with 4× headroom:

| | weight | 891-nit highlight shows as |
| --- | --- | --- |
| capacity 49× (library default) | 0.36 | ≈ 360 nits |
| capacity matched to the gain map (UltraShot) | 0.87 | ≈ 810 nits |

UltraShot encodes once, reads back the gain map's real `max_content_boost`, and if the capacity
differs by more than 2 % re-encodes with the target peak set to exactly that value (clamped to the
library's 250–10000 nit range). The log line

```
gain map: max boost 4.92x (1000 nits), fully applied from 4.92x display headroom
```

confirms it. The `--peak-nits` option overrides the automatic choice.

## 5. Signalling for every reader

libultrahdr 2.x writes ISO 21496-1 metadata, which Android 15+, iOS 18+ and current Chrome read.
Older Android releases and Adobe software look for the `hdrgm` XMP form, so UltraShot adds that
too: an XMP packet in the gain-map image with the same values, and a container directory in the
primary image whose `Item:Length` matches the gain-map JPEG. The primary XMP is inserted before the
MPF segment so MPF offsets stay valid.

Finally the file is decoded again and the reconstructed peak is logged, so a broken file never
leaves the pipeline silently.

## Verification you can do yourself

```python
import imagecodecs as ic, numpy as np
data = open("out.jpg", "rb").read()
print(ic.ultrahdr_check(data))                               # True
base, gainmap, meta = ic.ultrahdr_decode_jpeg(data)          # the two JPEGs + metadata
hdr = ic.ultrahdr_decode(data, dtype=np.float16)[..., :3] * 203   # linear nits as a viewer sees it
print(meta["max_content_boost"], meta["hdr_capacity_max"], hdr.max())
```
