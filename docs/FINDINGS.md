# Findings log

Measured results that shaped the design. Newest first.

## 2026-10-31: first live SAM 3.1 call (synthetic clip)

Clip: `move_red_into_box` (1280x720, 30 fps), prompt `"red block"`.

- Upload via Files API and `POST /responses` both returned 200. End to end took about 16 s, including upload.
- Frame indices match the source video frames one to one (178 frames in, 178 frames out). No resampling.
- One stable track id (0) covered the whole clip, including the move.
- At rest, the box center matched ground truth to within about 1 px at the start and exactly at the end.
- While the hand covers the block, the box shrinks to a partial view (area about 600 to 900, against 6,000 at rest) but the block is still detected. The track is not lost.
- Masks come back at reduced resolution (77 rows) with the lossless `~` marker. Boxes are enough for resting-state detection, so mask decoding is deferred.

Implication: comparing resting positions, as the PRD proposes, works on this clip. Real hands and real objects are still untested.
