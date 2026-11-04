# ShowOnce: technical overview

This document explains how ShowOnce turns one clip into a robot run: the data that flows between stages, the models used, how the simulator works, and what is and is not claimed. For setup and demos see the [README](README.md).

## 1. What the system does

Input: one overhead (or angled) clip of a person doing a tabletop task, plus a small scene file naming the objects and containers.
Output: a symbolic **task program**, a MuJoCo Franka Panda executing it on a shuffled table, and a per-step check against what really happened.

The claim is *task-level imitation*: what moved where, in what order, with which verb. It does not learn motor skills, and the arm never copies the hand's trajectory.

```
clip ──┬─► SAM 3.1 tracking ──► rests + moves ──► learn.py ──┐
       │                                                      ├─► TaskProgram ─► executor ─► verify
       └─► Muse Spark 1.3 (video) ──► structured steps ───────┘        │                       │
                                                                  MuJoCo Panda          sim state + SAM
```

## 2. Stages

### 2.1 Perception (`src/showonce/perception/`, `meta/`)

- **SAM 3.1** (`meta/sam.py`) is prompted with a short noun phrase per object (`scene.prompts`) and tracks it through the clip, returning boxes per frame.
- **Rests and moves** (`perception/moves.py`). A hand hides an object while it moves, so paths are unreliable. Instead, frames where an object is clearly visible and still form a *rest*; a jump between two consecutive rests is a *move*. Only start and end positions are used.
- **Calibration** (`geometry.py`). A planar homography maps pixels to table metres. By default a whole frame maps onto a fixed table rectangle; the simulator's top camera is placed to see exactly that rectangle, so a pixel means the same thing in the clip and in the sim.
- **Object profiles** (`objects.py`, `perception/profiles.py`). Muse Spark looks at the first frame and describes each object (shape, size in cm, handle, openable, pressable); pixels supply colour. An object is reduced to a `box`, `cylinder`, `sphere` or `log` with real dimensions. Box-shaped things and plain dishes are also cut out of the first frame and laid as a decal on the simulated object.

### 2.2 Understanding (`learn.py`, `meta/muse.py`, `demo.py`)

Two independent readings of the same clip:

1. **Geometry** (`learn.py`): each move is explained from resting positions. Landing inside a container region becomes `place_in`; landing on another object becomes `stack_on`; landing beside one on open table becomes `place_near` with a relation from the dominant axis.
2. **Muse Spark 1.3** watches the video and returns steps as schema-validated JSON. Object and container names are checked against the scene, so the model cannot invent things; repeated or "set down" steps are dropped.

Geometry is primary. The two are cross-checked and any disagreement is reported. Muse Spark's reading replaces geometry only when geometry cannot explain the clip: for the *semantic* actions (`wipe`, `open`, `pour`, `stir`, `cut`, `press`), which leave no change in resting positions, or when nothing moved at all.

**Unposed mode** (`unposed.py`) is for clips with no usable pixel-to-table mapping (an angled close-up). Object positions are then not read from the clip; the objects get a default arrangement and the program comes from Muse Spark's steps.

### 2.3 The task program (`program.py`)

A `TaskProgram` is an ordered list of `Step(object, action, target, relation)` using names only, never pixels, so it stays valid on any layout. Ten actions:

| Action | Meaning |
|---|---|
| `place_in`, `stack_on`, `place_near` | pick and place into, onto, or beside |
| `push` | slide without grasping |
| `wipe` | sweep a tool over a surface |
| `open` | tear the seal strip off a packet |
| `pour`, `stir` | tip a cup into a container; circle a tool through it |
| `cut` | cut a box in two, or chop a carrot into slices |
| `press` | press a button straight down |

### 2.4 Execution (`sim/`)

- **Scene** (`sim/scene.py`): table, trays for containers, one free body per object built from its profile, a top camera, and the Panda from DeepMind's `mujoco_menagerie`.
- **Controller** (`sim/controller.py`): Cartesian waypoints with damped least-squares IK, gripper pointing down. A grasp is a MuJoCo weld constraint between hand and object (no contact-grasp physics). The sim gripper opens 8 cm, so objects that are grasped are scaled to fit; objects that are only pushed, cut or pressed keep their true size.
- **Skills** (`sim/skills.py`): one motion per action. A wipe is a raster over the surface that clears the stains it passes over; a stir is circles at a steady radius that blend the contents' colour; a cut sweeps the knife across a box.
- **Carrot slicing**: a carrot is a `log` lying along the table's y axis with a slice count. The knife comes down just past the next cut line, a slice drops onto a pile beside it, and the blade finishes its stroke through the gap. The last stub is the last slice. The carrot is drawn as a cylinder but collides as a flat-bottomed box so it does not roll.
- **Placement and perception in the sim** (`sim/executor.py`, `sim/perceive.py`): on a replay the robot does not know where objects are. It parks the arm, renders the top camera, and finds each object with SAM using a phrase built from its profile ("yellow ball"). Objects that look alike (three lemons) share one search and each takes a different detection; which lemon is which does not matter.
- **Shuffled layouts** (`replay.py`): objects are placed at random free spots (seeded) before the arm moves, so a program that worked only on the demo layout would fail.

### 2.5 Verification (`sim/executor.py`, `verify.py`)

Two independent checks:

- **Simulator ground truth.** Each step has a predicate on world state (object inside the tray, contents transferred, box replaced by its halves, carrot replaced by N slices, button latched).
- **SAM on the finished table** (`verify.py`). The arm parks, the top camera is rendered, SAM finds each object, and the position is compared with the step's goal. A step it sees as missed is re-run once from where SAM saw things. Steps a top-down picture cannot show (stir, cut, press, pour, open, wipe) are judged from simulator state, and the report labels each check `SAM:` or `sim:`.

`--repair` adds a second recovery path: on the first failed spatial step Muse Spark is asked for a small corrective nudge and the step is retried once.

## 3. Models and what each one does

| Model | Role | Where |
|---|---|---|
| SAM 3.1 | track objects in the clip; find objects in the simulated top view | `meta/sam.py`, `perception/pipeline.py`, `sim/perceive.py` |
| Muse Spark 1.3 | read steps from video; describe objects from the first frame; plan tidying; conversational clarification; advise a repair | `meta/muse.py`, `chat.py`, `tidy.py` |

Responses are cached on disk by request hash (`cache.py`), so re-runs of a clip are repeatable and cheap. The API key is read from `MODEL_API_KEY` (`config.py`).

## 4. Interfaces

- **CLI** (`cli.py`, Typer): `demo`, `replay`, `tidy`, `eval-demo`, `eval-replay`, `segment`, `moves`, `synth`, `sim-test`, `ui`.
- **Web app** (`api/`, `web/`): FastAPI serves a React/TypeScript studio. Jobs run in the background; the user picks or uploads a clip, talks the plan through with Muse Spark, approves it, and watches the arm.

## 5. Repository map

```
src/showonce/
  program.py        task program (verbs, steps)
  learn.py          moves -> steps
  demo.py           clip -> program -> run
  replay.py         saved program -> shuffled table
  verify.py         SAM check of the finished table
  tidy.py           no-demo mode
  perception/       moves, profiles, scene description
  meta/             SAM and Muse Spark clients and prompts
  sim/              scene, controller, skills, executor, perception, recorder
  api/              FastAPI app and job service
  synth/            synthetic clips with pixel ground truth
samples/            demo clips and scene files
demos/              finished human and robot video pairs
web/                frontend
tests/              unit and simulator tests
```

## 6. Testing

`uv run pytest` runs the suite (no network; Meta calls are mocked with `respx`). It covers move detection, learning rules, SAM response parsing, the executor and each skill in the simulator, verification, the API and the sample scene files. Tests that need the Panda model skip themselves if `scripts/fetch_assets.sh` has not been run.

Beyond unit tests, the demo pairs in `demos/` were produced end to end: learn from the clip, run, then replay on a shuffled table (seed 7) with SAM locating the objects. The replays in `demos/` all passed their step checks, with SAM within 3 mm of the simulator's true positions.

## 7. Limits

- Task-level imitation only. No dexterous, contact-rich or learned motor control; grasps are weld constraints.
- Fixed, roughly top-down camera for geometry; angled clips use unposed mode and a default layout.
- A handful of distinctly coloured objects. Same-looking objects are interchangeable by design; two different objects of the same colour and shape would be confused by SAM.
- Fluids, cloth and tearing are abstractions (a colour-blended disc, a stain mask, a strip coming off a flat bag). Cutting is a swap of one body for its pieces at the moment the blade passes.
- Some demo clips are AI-generated and have small glitches in the footage. Three of the six demos are real stock footage.
- Real hardware has not been tried.
