# Posting HDR to Instagram and Threads

Instagram and Threads display gain-map JPEGs in HDR on supported phones (Android 14+ with an HDR
screen, recent iPhones). The catch is that their upload flow strips the gain map the moment it
touches the pixels. The whole recipe is therefore: **make the final image in UltraShot, then upload
it without changing anything.**

## 1. Prepare in UltraShot

- Keep the **Instagram** output enabled. It produces a 1440 px wide copy, which is the width
  Instagram stores; wider uploads are resized server-side.
- Choose the **crop** you want in Settings → Output or in the inspector: `4:5` for portrait posts,
  `1:1` for square, `1.91:1` for the widest landscape Instagram allows, `9:16` for stories.
  Position the crop with the X / Y sliders while watching the preview.
- Check the **SDR look**. The base image is what shows on SDR screens, in thumbnails, and for
  anyone whose phone does not support HDR. Dark game scenes often benefit from +0.3 to +0.5 stops
  of exposure; the HDR layer is unaffected.

## 2. Upload

- Upload from a **desktop web browser** (instagram.com), or from an Android phone. Uploads from an
  iPhone are transcoded through HEIC and lose the gain map.
- In the crop step, open the aspect menu and choose **Original**. Do not drag the crop, do not zoom.
- Skip filters and adjustments. Any edit is applied to the base image only and drops the gain map.
- Post. The HDR shows in the Instagram app on compatible phones; the web and SDR phones show the
  base image.

For Threads, the same applies. Do not upload to Instagram via a Threads cross-post, which resizes.

## 3. Verify

Open the post in the Instagram app on an HDR phone and compare with the SDR screenshot in your
gallery; the highlights should visibly glow brighter than the UI. Chrome and Edge on an HDR monitor
also render the gain map when you open the `Insta\*.jpg` file directly, which is a quick desk check.

## Other services

| Service | Gain-map HDR | Notes |
| --- | --- | --- |
| Google Photos | Yes | Keeps the file as-is |
| Chrome / Edge | Yes | Any page or local file |
| Android gallery apps | Mostly | Pixel, Samsung Gallery, OnePlus |
| Apple Photos (iOS 18+) | Yes | ISO 21496-1 metadata, which UltraShot writes |
| Discord | No | Shows the SDR base |
| X / Twitter, Reddit, Facebook | No | Re-encoded to SDR |
| Messaging apps | No | Re-encoded unless sent as a file |

Services that strip the gain map still show a correct SDR image, which is the point of using the
format: nothing ever looks wrong, it just looks SDR.
