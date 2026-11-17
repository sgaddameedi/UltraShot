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
out point can fall on any frame, because frames after the out point are simply not copied. The
join writes the pieces one after the other into a fresh container with the timestamps rewritten
so they run continuously; the packets inside are still the originals.

After each export the file is read back and compared with its source: codec, size, frame rate,
pixel format, bit depth, colour primaries, transfer, matrix, the HDR kind, the mastering display
and content light values, the Dolby Vision profile, and the audio streams. The result is shown
under the export button, row by row, so a mismatch is never silent.

## The editor

The left column is the clip bin. Add recordings with the button at the top or drop them anywhere
on the window; each one is probed in the background and shows its length, size and what it is,
such as "AV1 10-bit · HDR10 (PQ, bt2020) · 3840×2160 · 60 fps · 92 Mb/s". A recording that is
removed from the bin stays on disk.

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
drag on it to move the playhead, drag the two handles to set the in and out points, or press I and
O to mark them at the playhead; the in handle snaps to a keyframe when released and the line under
the timeline says where it landed. The bracket keys jump the playhead to the previous and next
keyframe, the arrow keys step one frame, with Shift one second, Space plays and pauses, and P plays
the selection from in to out. Add segment, or Enter, keeps the part between the handles as a
numbered segment below the timeline. Segments can come from different
recordings, can be reordered with the arrows on each one, previewed by clicking them and removed
with the cross or the Delete key.

The right column is the export. Each segment becomes its own file next to its recording, or in a
folder of your choice, named after the source with the in and out times appended. With *Join
segments into one file* on, the segments are written in their order into a single file whose name
you choose; joining requires that the segments share a codec, size, frame rate, pixel format and
audio layout, which is the case for pieces of one recording or of recordings made with the same
settings, and the editor says so when they do not. Progress and the verification report appear
under the button, with shortcuts to open the file, show it in its folder or bring it back into
the bin for a further cut.

## FFmpeg

The editor is built on FFmpeg, which does the probing, the frame grabs, the stream copies and the
verification. UltraShot looks for it on the PATH, in a WinGet installation and in `C:\ffmpeg\bin`.
When none is found the editor shows a *Get FFmpeg* chip that downloads the essentials build from
gyan.dev, verifies its checksum and unpacks it into UltraShot's own folder under `%LOCALAPPDATA%`,
without touching anything else on the system. Installing it with `winget install Gyan.FFmpeg`
works just as well.

## What the editor does not do

It does not re-encode, so it cannot cut on a frame that is not a keyframe, change the resolution
or frame rate, add transitions, titles or filters, or join recordings made with different
settings. It does not change the audio. These are the trade-offs that make the exports exact, and
a recording that needs any of them is better served by an editor that renders.
