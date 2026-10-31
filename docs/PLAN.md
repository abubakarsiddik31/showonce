# ShowOnce — Delivery Plan

Hard deadline: **Wed Nov 4, 2026, 9:00 PM ET** (about Thu Nov 5, 08:00 Dhaka). Confirm on the submit page.
Scope is P0 only. P1 items are stretch goals and are only started once the P0 demo runs end to end.

## Decisions

| Decision | Choice | Why |
| --- | --- | --- |
| Simulator | MuJoCo (not PyBullet) | PyBullet 3.2.7 fails to compile on macOS arm64 against the current OpenGL headers. MuJoCo ships prebuilt wheels. |
| Robot model | Franka Panda from `mujoco_menagerie` | Maintained, Apache-2.0, fetched by `scripts/fetch_assets.sh`, not vendored. |
| Perception | SAM 3.1 boxes per frame | Boxes give centroids, which is all resting-state detection needs. Mask decoding is added only if needed. |
| Planning | Muse Spark 1.3, structured JSON | Reads the clip into (object, action, target) steps. |
| Tooling | uv, ruff, mypy strict, pytest | Reproducible and quick to set up. |
| Secrets | `MODEL_API_KEY` in `.env`, never committed | Matches Meta's own docs. |

## Milestones

| Day | Goal | Exit check |
| --- | --- | --- |
| Sat Oct 31 | Repo, config, API client, SAM parser. First live SAM call on a clip with hands. Panda loads in MuJoCo. | SAM returns boxes for 3 colored blocks on a hand-occluded clip. |
| Sun Nov 1 | Resting-state detection, Muse Spark plan, task program, IK and grasp. | One filmed task runs from video to robot finishing it. |
| Mon Nov 2 | Replay on a shuffled layout. Three tasks work. Side-by-side output video. | Replay succeeds on a shuffled layout. |
| Tue Nov 3 | Evaluation set (target 8 to 15 clips) and README results table, failures included. | Table is in the README. |
| Wed Nov 4 | Demo video, repo clean-up, submit before the cutoff. | Submission confirmed. |

## Work breakdown (P0)

1. **Foundation**: config, disk cache by content hash, Meta API client (Files + Responses streaming), SAM output parser.
2. **Perception**: per-object SAM tracking, resting-state and move detection, homography from pixels to table.
3. **Planning**: Muse Spark step extraction into a fixed schema, compile to a symbolic task program.
4. **Simulation**: Panda scene, IK controller, constraint-style grasp, task executor.
5. **Replay**: SAM on the sim camera frame to re-find objects on a new layout, then execute the stored program.
6. **Delivery**: CLI, evaluation script, README, demo video.

## P1 (only if P0 is done)

Fragment merging, geometry vs Muse Spark cross-check, web view, SAM-based verification score.

## Open questions

- Does a simulation-only project count for "Push the Frontier"? Ask the organizers in Discord.
- Claim the $150 credit in the Discord credit channel.
- Solo or team? Every member must be added on the submission.
- Official rules: confirm the commit window (Oct 26 to Nov 4) and Meta-models-only requirement.
