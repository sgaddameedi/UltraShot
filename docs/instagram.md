# Posting HDR screenshots to Instagram and Threads

Instagram and Threads both display gain-map JPEGs in HDR on phones that support it, which at the time
of writing means Android devices running version 14 or later with an HDR-capable screen, and recent
iPhones. The complication is that their upload flow removes the gain map whenever it touches the
pixels. Cropping, zooming, straightening, applying a filter or adjusting the exposure all produce a
new, ordinary JPEG. The whole procedure therefore comes down to one principle: finish the image in
UltraShot, and upload it without changing anything.

## Preparing the image

Leave the Instagram output enabled in Settings. It produces a copy 1440 pixels wide, which is the width
Instagram stores internally; anything wider is resized by Instagram's servers, and that resize removes
the gain map just as a manual crop would.

Choose the aspect ratio in Settings or in the inspector. Instagram's portrait posts are 4:5, square
posts are 1:1, landscape posts can be as wide as 1.91:1, and stories are 9:16. The crop is positioned
with the X and Y sliders while the preview updates, so the composition can be checked before anything
is written.

Review the SDR base image in the inspector. The base is what appears on SDR screens, in the feed
before the post is opened, in thumbnails, and on any phone that does not render HDR, so it deserves
the same attention as the HDR version. Dark game scenes often benefit from a third to half a stop of
additional exposure; the HDR layer is unaffected by the adjustment.

## Uploading

Upload from a desktop web browser at instagram.com, or from an Android phone. Uploads from an iPhone
pass through HEIC conversion and lose the gain map.

In the crop step, open the aspect-ratio menu and choose *Original*. Do not drag the crop frame and do
not pinch or zoom, because any of these actions re-renders the image. Skip the filters and
adjustments screens entirely, then post. On a compatible phone the Instagram app shows the post in
HDR; on the web and on SDR phones the base image is shown instead, which is the intended fallback.

Threads behaves the same way. Avoid cross-posting from Threads to Instagram, which resizes the image
on the way.

## Checking the result

Open the post in the Instagram application on an HDR-capable phone and compare it with an SDR
screenshot in the gallery. The highlights of an HDR post are visibly brighter than the white of the
user interface around them. On the desktop, Chrome and Edge render gain maps when an HDR monitor is
connected, so opening the file from the `Insta` folder directly in either browser is a quick way to
verify a conversion before uploading it.

## Other services

The table summarises how commonly used services handle gain-map JPEGs. Services that discard the gain
map still show the SDR base image correctly, which is the reason to prefer this format over HDR-only
formats: the worst case is a normal photograph, never a broken one.

| Service | Shows HDR | Notes |
| --- | --- | --- |
| Google Photos | Yes | Stores the file unchanged |
| Chrome and Edge | Yes | Any web page or local file, on an HDR display |
| Android gallery applications | Mostly | Pixel, Samsung Gallery and OnePlus render gain maps |
| Apple Photos (iOS 18 and later) | Yes | Reads the ISO 21496-1 metadata that UltraShot writes |
| Discord | No | Displays the base image |
| X, Reddit, Facebook | No | Re-encoded to SDR on upload |
| Messaging applications | No | Re-encoded when sent as a photo; preserved when sent as a file |
