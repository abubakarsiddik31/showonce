# Findings log

Measured results that shaped the design. Newest first.

## 2026-10-31: MuJoCo Panda stacks reliably

`uv run showonce sim-test` stacks one block on another from random layouts.

- **10 of 10 stacks succeeded** (xy error about 5 mm, height error under 0.5 mm; blocks are 4 cm cubes).
- PyBullet would not compile on this Mac, so the sim uses MuJoCo with the Panda from `mujoco_menagerie` (`scripts/fetch_assets.sh` downloads it).
- The grasp is a weld constraint between the hand and the block, switched on when the gripper closes. It is far more stable than relying on friction alone. This matches the PRD's "constraint grasp".
- Arm gravity is compensated so the position actuators do not sag.
- 10 stacks take under 2 seconds of wall time.

Known issue: at its home pose the arm hangs over the table and blocks the top camera. The replay step needs a park pose before it captures the sim camera frame.

## 2026-10-31: move detection on all 8 synthetic clips

`uv run showonce eval-moves` scores detected moves (object, order, source and destination within 30 px) against the ground-truth json.

- **8 of 8 clips exact.** That covers blocks into a box, sorting into zones, stacking cups, stacking three, fast hands, and dim noisy light.
- A full run of 8 clips took about 40 s once uploads were cached, with 3 SAM calls in parallel per clip.
- **SAM 3.1 returns nothing for "red cup" on a plain circle seen from above.** The first run scored 5 of 8 for this reason: every cup clip detected zero moves. The synthetic cups now use the prompt "red circle". Real cups should be tested with "red cup".
- Resting positions are found only on frames where the box is at least 70% of the object's typical area. This keeps a still hand-covered object from counting as a rest.

Not yet tested: real footage, two objects of the same color, and objects that look alike.

## 2026-10-31: first live SAM 3.1 call (synthetic clip)

Clip: `move_red_into_box` (1280x720, 30 fps), prompt `"red block"`.

- Upload via Files API and `POST /responses` both returned 200. End to end took about 16 s, including upload.
- Frame indices match the source video frames one to one (178 frames in, 178 frames out). No resampling.
- One stable track id (0) covered the whole clip, including the move.
- At rest, the box center matched ground truth to within about 1 px at the start and exactly at the end.
- While the hand covers the block, the box shrinks to a partial view (area about 600 to 900, against 6,000 at rest) but the block is still detected. The track is not lost.
- Masks come back at reduced resolution (77 rows) with the lossless `~` marker. Boxes are enough for resting-state detection, so mask decoding is deferred.

Implication: comparing resting positions, as the PRD proposes, works on this clip. Real hands and real objects are still untested.
