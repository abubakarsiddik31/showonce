# ShowOnce — Product Requirements Document (v3)

Nov 1, 2026 · @Abu Bakar Siddik · Supersedes v2 (Oct 31, 2026)

## What changed in v3

v3 records what actually shipped on the `new-actions` branch. The action vocabulary grew from four verbs to ten, and two learning/physics fixes landed with it. Everything not listed here is unchanged from v2.

| # | Change | Why |
| --- | --- | --- |
| 1 | **Six new actions: `place_near`, `push`, `pour`, `stir`, `cut`, `press`** (4 → 10 verbs in `src/showonce/program.py`: `place_in`, `stack_on`, `wipe`, `open` plus the six new ones). Each has its own simulator skill, executor dispatch and ground-truth verification. `place_near`/`push` toward an object carry a `relation` (`next_to`, `left_of`, `right_of`, `in_front_of`, `behind`). | Demos are not only put-in and stack: people set things beside, slide, pour, stir, cut and press. |
| 2 | **`place_near` open-table learning fix.** A move ending beside another object on open table (not in/on it) is now learned as `place_near` with a relation (`src/showonce/learn.py`), instead of being misread. | Previously only container/on-top endings were explainable from resting positions. |
| 3 | **`push` true-size handling.** Profile fitting no longer shrinks an object that will only be pushed (never grasped) to fit the 8 cm gripper; pressed objects are fitted as `pressable` (`src/showonce/perception/profiles.py`, `src/showonce/sim/scene.py`). | A pushed book keeps its real size; only grasped objects need the gripper limit. |
| 4 | **Reading path extended.** Muse Spark's prompt/schema names all ten actions plus `relation` and the `pressable` object flag (`src/showonce/meta/muse.py`); chat wording, the web API schemas and the web editor understand the same ten verbs. `pour`, `stir`, `cut`, `press` join `wipe`/`open` in `SEMANTIC_ACTIONS` — geometry cannot see them, so Muse Spark's reading is used. | A new verb is only real if every layer can name it. |
| 5 | **Five new sample scenes** (`cup_pour`, `bowl_stir`, `book_push_aside`, `bar_cut`, `lamp_press`), scene files ready; footage generates on demand and is **not yet evaluated**. | Repeatable tests for the new verbs without invented scores. |
| 6 | **FR statuses corrected to shipped code** (see table below), task-type scope widened beyond move/stack, demo plan gains a new-action beat, and success metrics re-baselined to verified numbers only. | v2 marked several shipped items "Not started" and carried proposal targets as if measured. |

## Overview

ShowOnce lets you teach a simulated robot arm a tabletop task by filming it once. The robot watches the clip, asks a clarifying question only if the demo could mean more than one thing, then performs the task, including from a shuffled layout of the objects. It targets the Meta Global AI Developer Hackathon 2026, indie developer track, theme "Push the Frontier".

- **One-liner:** Show a robot a task once. It learns the rule, applies it to a new table, and checks its own work.
- **Input:** a 5 to 15 second phone video of a person moving 3 or 4 colored blocks or cups.
- **Output:** a simulated Franka Panda arm in MuJoCo performing the task, a reusable task program, and a pass or fail score against the goal.
- **Meta stack:** SAM 3.1 for object tracking and verification; Muse Spark 1.3 for the step plan and the candidate rules.
- **Claim:** task-level imitation (what moved where, in what order, under which rule). Not learned dexterous motor skills.
- **Deadline:** Wed Nov 4, 2026, 9:00 PM ET (about Thu Nov 5, 08:00 Dhaka). Confirm on the submit page.

## The Watch, Ask, Do flow

1. **Watch.** SAM 3.1 tracks each object. Resting-state comparison yields the moves (object, source, destination). Muse Spark reads the same clip and returns steps as JSON.
2. **Ask.**
   1. Muse Spark proposes candidate rules consistent with the demo (for example "stack by color" vs "stack by size").
   2. Each rule is compiled into a task program on the current layout.
   3. If the programs produce different action lists, the robot asks one multiple-choice question. If they agree, it does not ask.
   4. At most two questions per run. Answers are buttons or a terminal choice (Meta has no speech output).
3. **Do.** The chosen rule becomes a symbolic task program (object names and relations, no pixel positions). The arm executes it. On a shuffled layout, SAM re-finds the objects first.
4. **Verify and fix.** SAM segments the final sim frame and compares it to the goal. A miss triggers one corrective attempt and an on-screen note.

## Problem and opportunity

Programming a robot usually takes an expert or a large demonstration set, while showing a task once is what people expect. A single demonstration is ambiguous, so a system that notices the ambiguity and asks is closer to how people teach.

Crowding to acknowledge: at least one public entry tracks products through bench video with SAM 3.1, and GoferAI turned human demo videos into robot policies at a sim-first robotics hackathon. ShowOnce differs through the Ask step (divergence-checked questions), replay from a new layout, and the verified closed loop.

Why it can compete: a one-sentence idea with a visible demo, two Meta models doing distinct jobs in one pipeline, and an honest results table with failures.

## Goals and non-goals

**Goals** (numeric targets are proposals to adjust after real-footage tests)

1. Turn a supported phone video into a correct step list in at least 80% of test clips.
2. Execute the program in simulation and reach the correct final layout in at least 70% of runs.
3. Replay from a shuffled layout with the same success target.
4. Ask a question only when candidate rules diverge, and show one case where the answer changes the robot's action.
5. Ship a public repo, a README with a results table, and a three-minute demo video before the cutoff.

**Non-goals**

- Dexterous or contact-rich manipulation, real hardware, sim-to-real transfer.
- Arbitrary objects, clutter, deformable items, or a moving camera.
- Training a learned control policy.
- Voice input or output.

## Scope

Fixed camera, roughly top-down, whole table visible. 3 or 4 distinctly colored blocks or cups plus at most one box or zone. 5 to 15 seconds, steady light, one person's hands, each object still before and after every move.

Task types by priority:

1. **P0:** move an object into a container or zone; stack A on B; set an object beside another on open table (`place_near`).
2. **P0:** one ambiguity case where the Ask step changes the outcome (color vs size ordering).
3. **P1:** sort by color into zones; stack three; slide an ungraspable object (`push`); pour, stir, cut and press demos (one each, from the new sample scenes).
4. **Cut:** undo or reverse a stored task.

## Functional requirements

Statuses below were each checked against `src/showonce/` on this branch.

| ID | Requirement | Priority | Status |
| --- | --- | --- | --- |
| FR1 | Accept a phone video (mp4 or mov, up to 15 s) from the command line. | P0 | Done |
| FR2 | Cache every API result by content hash. | P0 | Done |
| FR3 | Run SAM 3.1 with one short noun phrase per object and store per-frame boxes. | P0 | Done (boxes only) |
| FR4 | Extract resting positions and moves, ignoring frames where a hand hides the object. | P0 | Done (8 of 8 synthetic clips exact) |
| FR6 | Have Muse Spark 1.3 return steps in a fixed JSON schema (object, action, target). | P0 | Done (ten actions + `relation`, `src/showonce/meta/muse.py`) |
| FR8 | Compile steps into a symbolic task program with no pixel positions. | P0 | Done (`src/showonce/program.py`, `learn.py`) |
| FR9 | Map image pixels to table coordinates with a four-corner homography. | P0 | Done (`src/showonce/geometry.py`) |
| FR10 | Execute the program in MuJoCo with a Panda arm, inverse kinematics and a weld-constraint grasp. | P0 | Done (all ten actions; stacking 10 of 10) |
| FR11 | Replay a stored program on a shuffled layout by re-finding objects with SAM on the sim camera frame. | P0 | Done (`src/showonce/replay.py`) |
| FR15 | **Ask step:** Muse Spark proposes candidate rules; compile each on the current layout; ask only if the action lists differ. | P0 | Done as shipped: the web Ask step asks only when tracked motion and Muse Spark's reading disagree (`src/showonce/api/questions.py`) |
| FR16 | **Verify and fix:** SAM checks the final frame against the goal and triggers one correction. | P0 | Partial: every step is verified against simulator ground truth (`src/showonce/sim/executor.py` `verify`); a SAM final-frame check with a corrective retry is not shipped |
| FR17 | **Why-SAM comparison:** a color-threshold baseline that fails on dim light or similar colors. | P1 | Not started |
| FR12 | Pass or fail per object on the final layout (merged into FR16). | P1 | Merged |
| FR14 | Save each run (video, plan, sim recording, score) for the results table. | P1 | Done (runs saved under `runs/<name>/`) |
| FR5, FR7 | Fragment merging, pixel cross-check. | Cut | Cut |
| FR13 | Web view. | Cut in v2 | Done — shipped anyway (`web/`, served by `showonce ui`); v2's cut is superseded |
| FR18 | `place_near`: set an object beside another on open table at a stated relation, learned from open-table endings. | P0 | Done on this branch |
| FR19 | `push`: slide an ungraspable object beside a neighbour or into a container, keeping its true size. | P0 | Done on this branch |
| FR20 | `pour`: tip a cup over a container and move its (abstract) contents into it. | P1 | Done on this branch |
| FR21 | `stir`: swirl a tool through a container's contents until mixed. | P1 | Done on this branch |
| FR22 | `cut`: one straight pass with a knife; the target becomes two halves. | P1 | Done on this branch |
| FR23 | `press`: push a button, pump or push-light straight down and latch it. | P1 | Done on this branch |

## System architecture

Two lanes read the same clip. SAM 3.1 gives geometry (moves), Muse Spark 1.3 gives semantics (steps and candidate rules). The Ask step compares the rules on the live layout, and the chosen program is saved and executed. Tools: `sam-3.1` and `muse-spark-1.3` through the Meta Model API (`https://api.meta.ai/v1`), MuJoCo for simulation, OpenCV for the homography. Code lives in `src/showonce/` (`meta/`, `perception/`, `sim/`, `synth/`).

## Technical design

The design rests on one idea: compare resting states, not continuous paths, because the hand hides objects during every move.

**Perception (SAM 3.1).** One short noun phrase per object runs over the clip through the Responses API, with the clip uploaded once through the Files API. Output is special-token text with explicit frame markers, boxes in source pixels, and low-resolution masks. Findings so far: frame indices match the source one to one; a hand-covered object keeps its track with a shrunken box; "red cup" returns nothing for a plain circle from above, so the synthetic clips use "red circle" (real cups need testing). Resting frames are those where the box is at least 70% of the object's typical area and the centroid is still.

**Semantic plan (Muse Spark 1.3).** The model watches the clip and returns structured output: steps (object, action, target) and candidate rules (name, description). Geometry confirms stacking when the final centroid sits over the target.

**Ask step.** Each candidate rule is compiled against the current layout into an ordered action list. If two or more lists differ, one multiple-choice question is generated from the difference. The divergence and the chosen answer are logged and shown on screen.

**Task program.** Object names and relations only, stored as JSON, valid on any layout.

**Simulation (MuJoCo).** Panda from `mujoco_menagerie`, a table, colored blocks and a tray, with a top-down camera. Grasp is a weld constraint switched on when the gripper closes. Gravity compensation prevents sag. Known issue: at its home pose the arm blocks the top camera, so replay needs a park pose before capturing the sim frame.

**Verify and fix.** SAM segments the final sim frame, positions are compared to the goal, and a miss triggers one correction with an on-screen note.

## Success metrics and evaluation

Re-baselined in v3 to verified numbers only. The v2 percentage targets (80% plan accuracy, 70% execution/replay) were proposals and are **not** claimed as measured; no eval percentages are stated until a labelled eval is run.

| Metric | Verified result | How it is measured |
| --- | --- | --- |
| Test suite | 128 Python tests passed (`.venv/bin/python -m pytest tests -q`, run Nov 1, 2026 on this branch) | pytest, offline, no API calls |
| Move detection | 8 of 8 synthetic clips exact | Synthetic clips with pixel-level ground truth |
| Sim stacking | 10 of 10 | `showonce sim-test`: random-layout block stacks |
| Ask precision | Asks only when the two readings diverge | By construction (`build_questions` returns no question on agreement); not yet measured over a labelled clip set |
| New-action clips | 5 scene files ready, **not yet evaluated** | `cup_pour`, `bowl_stir`, `book_push_aside`, `bar_cut`, `lamp_press`; footage generates on demand |
| Time to first result / API cost | Not measured | No verified numbers yet; nothing claimed |

**Test set:** the 5 evaluated sample clips in the README results table, plus the 8 synthetic clips with ground truth, plus the 5 new-action scenes once evaluated. The README shows the table with failures and the reason for each.

Measured so far (synthetic/AI-generated clips only): move detection 8 of 8; sim stacking 10 of 10; full suite 128 passed. No real footage has been tested.

## Demo plan (3 minutes)

| Time | Beat | What the viewer sees |
| --- | --- | --- |
| 0:00 to 0:20 | Hook | The payoff first: a person films a task, the robot does it. One sentence of story with a named user. |
| 0:20 to 1:00 | Watch | SAM masks with ids and Muse Spark's plan, side by side. Why SAM beats color thresholding. |
| 1:00 to 1:40 | Ask | The robot asks one question. The answer changes its action. |
| 1:40 to 2:20 | Do and shuffle | A second person shuffles the table. The robot re-finds the objects and finishes. |
| 2:20 to 2:35 | New action | Pour: the arm tips the red cup over the white bowl and the contents move across (`cup_pour`). One of the six new verbs, end to end. |
| 2:35 to 2:50 | Verify and fix | A visible miss, then a correction. |
| 2:50 to 3:00 | Results and limits | Results table with failures, stated limits, path to a real arm, and the Meta models used. |

Reliability rules: record backup takes of every run, keep two or three tasks that work every time, and run each demo task 10 times before filming.

## Hackathon compliance and submission

Rules below come from a participant's notes and press coverage, not the official rules page.

- [ ] Every commit made between Oct 26 and Nov 4 (repo started Oct 31).
- [ ] Meta models only, through the Meta Model API or open weights.
- [ ] Claim the $150 Meta credit in Discord; a spend alert does not stop billing.
- [ ] API key stays in a local `.env`, never committed. Check history before making the repo public.
- [ ] Add every team member on the submission.
- [ ] README: setup, architecture, results table, limits, which Meta model does what.
- [ ] Demo video added to the submission.
- [ ] Submit with hours of buffer before the cutoff.

## Risks and fallbacks

| Risk | Mitigation or fallback | First test |
| --- | --- | --- |
| SAM loses objects under real hand occlusion | Compare resting states only; fall back to Muse Spark's video reading as the main signal | One real clip, today |
| "red cup" returns nothing for real cups | Try alternative prompts ("red circle", "red mug"); test both | Real cup clip |
| Ask step looks scripted | Divergence check plus one case where the answer visibly changes the action | Log the diff on screen |
| Muse Spark returns a wrong step list or odd rules | Fixed JSON schema, geometric check, show disagreements | Hand-label 5 clips |
| Simulated grasp is unstable | Weld grasp, slow motions | Done: 10 of 10 stacks |
| Simulation-only is not accepted for the theme | Ask the organizers in Discord now | One message |
| Arm blocks the top camera at home pose | Park pose before capture | Replay test |
| Credit or cost surprise | Cache, per-run cost log, claim credit | Check credit today |
| Overclaiming | Describe it as task-level imitation; show failures | Review the script |

## Schedule

About three working days remain.

| When | Goal | Exit check |
| --- | --- | --- |
| Today (Sat Oct 31) | Foundation done: client, parser, move detection, sim stacking. Next: real-clip SAM test. | SAM tracks objects on a real hand-occluded clip. |
| Sun Nov 1 | One task end to end: video, SAM, Muse Spark plan, program, arm. | A filmed task runs to completion. |
| Mon Nov 2 | Ask step with divergence check, shuffled replay, verify and fix. | The answer visibly changes the action. |
| Tue Nov 3 | Reliability runs, results table, README, video script. | Table and script ready. |
| Wed Nov 4 | Record, edit, submit with buffer. | Submission confirmed. |

## Open questions

- [ ] Does a simulation-only project count for "Push the Frontier"? Ask the organizers.
- [ ] Do real cups work with the "red cup" prompt, or do they need another phrase?
- [ ] Which ambiguity case is the hero of the Ask demo (color vs size ordering is the default)?
- [ ] Which named user and task frames the story?
- [ ] Is the $150 credit claim live in Discord?
- [ ] Solo or team? Every member must be added on the submission.
- [ ] Is the cutoff exactly Wednesday 9 PM ET?

## Sources

- [Meta Model API models page](https://dev.meta.ai/docs/models): model ids, SAM 3.1 and Muse Spark capabilities.
- [Meta SAM guides](https://dev.meta.ai/docs/sam/segmenting): video input, limits, special-token output.
- [Meta hackathon coverage (Superpower Daily)](https://superpowerdaily.com/posts/meta-sets-october-26-start-for-1-million-ai-hackathon-capped-at-20-000-builders): dates, tracks, themes.
- [Participant repo with rules and Discord notes](https://github.com/sholaola23/meta-hackathon-2026): unofficial rules and judging criteria.
- [BeforeTheTape repo](https://github.com/felixbennet/before-the-tape): SAM 3.1 video tracking and the re-found object id problem.
- [AI Meets Robotics summary (lablab.ai)](https://lablab.ai/ai-articles/ai-meets-robotics-hackathon-summary): GoferAI and the sim-first format.
