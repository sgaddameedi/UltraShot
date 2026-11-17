# Trimming, cutting and joining HDR recordings

UltraShot's video editor takes the recordings that the NVIDIA App, OBS, the Windows Game Bar, a
capture card or a phone write and lets you trim them, cut pieces out of them and join pieces back
together without re-encoding a single frame. The exported file carries the same codec, the same
10-bit samples, the same BT.2020 and PQ or HLG colour tags, the same mastering display and content
light metadata, the same Dolby Vision configuration where the source has one, and the same audio
as the recording it came from. There is no quality setting because quality is never touched.

The editor is the *Video* tab at the top of the window, beside *Screenshots*, and it also opens on
its own when a recording is dropped on the window. Everything stays on this machine: recordings are read from where they are,
nothing is uploaded, and the only files written are the exports and, when the window cannot play a
file directly, a small preview copy in a local cache.

## How a lossless cut works

A video stream is a chain of frames where most frames are described as differences from the ones
before them, and only a keyframe stands on its own. A cut that lands between keyframes would
leave the first frames of the piece without the frames they depend on, so a player would have to
drop them or show garbage. Editors that cut on arbitrary frames solve this by decoding and
re-encoding the whole clip, which costs time and quality and, for HDR, is where metadata is most
often lost.

UltraShot instead moves every in point to the nearest keyframe and copies the packets from there
to the out point as they are. Recorders write a keyframe every half second to two seconds, so the
in point lands within a second of where it was placed and the editor tells you where it went. The
out point can fall on any frame, because frames after the out point are simply not copied; when a
recording uses B-frames, which are stored out of order, the one or two frames that are stored
before the last frame you keep come along with it, so the piece can run a frame or two past the
out point but never has a gap before it. The
join writes the pieces one after the other into a fresh container with the timestamps rewritten
so they run continuously; the packets inside are still the originals.

After each export the file is read back and compared with its source: codec, size, frame rate,
pixel format, bit depth, colour primaries, transfer, matrix, the HDR kind, the mastering display
and content light values, the Dolby Vision profile, and the audio streams. The result is shown
under the export button, row by row, so a mismatch is never silent.

## The editor

The left column is the clip bin. Add recordings by clicking the empty player, the dashed box in
the bin or *Add* at the top, or drop them anywhere on the window; each one is probed in the
background and shows its length, size and what it is, such as "AV1 10-bit · HDR10 (PQ, bt2020) ·
3840×2160 · 60 fps · 92 Mb/s". A recording that is removed from the bin stays on disk.

The middle holds the player, the transport and the timeline. The player streams the recording
from disk, so a fifty gigabyte file opens as quickly as a small one and seeking is immediate. The
window decodes HEVC, H.264 and AV1 at 10 bits, which covers what the NVIDIA App, OBS, the Game
Bar and phones write; the picture is a preview and the export is always made from the original
file, never from what the player shows. For a container or codec the window cannot decode, such
as an MPEG transport stream, the editor builds a small SDR preview copy once and edits against
that instead, while the export still comes from the original. Preview copies are kept in a local
cache that is capped at six gigabytes, oldest first.

Times are shown as timecode, hours, minutes, seconds and frames, and the in and out fields
accept a typed time in that form, as minutes and seconds, or as plain seconds. The timeline shows
a film strip of the recording under a ruler, with the keyframes marked as short ticks when they
are far enough apart to be told apart, and the part outside the in and out points dimmed. Click or
drag on it to move the playhead and drag the two handles, marked IN and OUT, to set the in and out
points. The bar that joins the two handles slides the whole selection along the recording with its
length kept, which is the quick way to adjust a piece once its length is right; the in point snaps
to a keyframe when the bar is released and the out point follows it. The *Mark* buttons beside the
in and out fields set a point at the playhead, as do the I
and O keys, and a right click on the timeline opens a menu that marks in or out, splits the
selection, adds it as a segment, plays from that point or resets the handles. The in handle snaps
to a keyframe when released and the line under the timeline says where it landed. *Reset* puts
both handles back to the whole recording. The bracket keys jump the playhead to the previous and
next keyframe, the arrow keys step one frame, with Shift one second, Space plays and pauses, and
*Preview* or P plays the selection from in to out.

*Add segment*, or Enter, keeps the part between the handles as a numbered segment below the
timeline. *Split here*, or S, cuts the selection in two at the keyframe nearest the playhead and
keeps both halves as segments, which is how a piece is taken out of the middle of a recording:
split on either side of it and remove the segment between. Segments can come from different
recordings. Click one to preview it, right-click it to play it, load it back into the handles,
move it or remove it, or use the arrows and the cross on each one and the Delete key. *Undo*
beside the total takes back the last segment change, as does Ctrl+Z, and *Clear all* empties the
list.

The right column is the export. Each segment becomes its own file next to its recording, or in a
folder of your choice, named after the source with the in and out times appended. With *Join
segments into one file* on, the segments are written in their order into a single file whose name
you choose; joining requires that the segments share a codec, size, frame rate, pixel format and
audio layout, which is the case for pieces of one recording or of recordings made with the same
settings, and the editor says so when they do not. Progress and the verification report appear
under the button, with *Play*, which plays the export in the editor's own player and adds it to
the bin so it can be cut again, *Open* for your default video player, and *Show in folder*.

## Framing for Shorts, Reels and feeds

The *Frame* row in the export panel reframes the export for the shapes that YouTube and
Instagram lay out natively: 9:16 for Shorts, Reels, TikTok and Stories, 4:5 and 1:1 for feed
posts, and 16:9 for ordinary videos and landscape feeds. Choosing one draws a window on the
player; drag it to decide what stays in the picture, and double-click it to centre it again.
*Size* keeps every pixel inside the window, which from a 4K recording gives 1214×2160 for 9:16,
or scales it to the largest size the platform keeps, 1080×1920 for the vertical shapes, so the
upload is smaller and the platform does no scaling of its own.

This is the one export that is not a stream copy, and the panel says so. A crop changes every
frame, so the picture has to be encoded again; there is no way around that, and a tool that
claims otherwise is re-encoding quietly. UltraShot does it as carefully as it can: the segment is
cut losslessly first, so only the seconds you keep are ever decoded, and the cut is then encoded
on the GPU, AV1 for AV1 recordings and HEVC otherwise, at a quality setting far above what any
platform keeps after upload, with a keyframe every two seconds so the result trims well later.
The bit depth, the BT.2020 primaries, the PQ or HLG transfer, the mastering display and content
light metadata and the audio are carried across unchanged, and the result is read back and
checked row by row like every other export; the report names the encoder and shows the new size
beside the old one. A Dolby Vision layer cannot survive a re-encode and is dropped, which leaves
the HDR10 picture underneath. On a machine without an NVIDIA GPU the encode falls back to the
software HEVC encoder, which is slower but gives the same result. A recording that already has
the chosen frame, such as a 16:9 recording framed 16:9 at full size, is copied losslessly as it
is.

YouTube keeps HDR on Shorts and on ordinary uploads when the file is tagged as above. Instagram
accepts HDR from its phone apps and is less predictable with files uploaded from a computer,
where some viewers see the same file in SDR; that is a limit of the platform, not of the file.

## FFmpeg

The editor is built on FFmpeg, which does the probing, the frame grabs, the stream copies and the
verification. UltraShot looks for it on the PATH, in a WinGet installation and in `C:\ffmpeg\bin`.
When none is found the editor shows a *Get FFmpeg* chip that downloads the essentials build from
gyan.dev, verifies its checksum and unpacks it into UltraShot's own folder under `%LOCALAPPDATA%`,
without touching anything else on the system. Installing it with `winget install Gyan.FFmpeg`
works just as well.

## What the editor does not do

Apart from reframing, it does not re-encode, so it cannot cut on a frame that is not a keyframe,
change the frame rate, add transitions, titles or filters, or join recordings made with different
settings. It does not change the audio. These are the trade-offs that make the exports exact, and
a recording that needs any of them is better served by an editor that renders.
