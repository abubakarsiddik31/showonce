# Six new actions: place_near, push, pour, stir, cut, press

Date: 2026-11-01
Status: approved in conversation; pending implementation

## Why

The action vocabulary is four verbs (`place_in`, `stack_on`, `wipe`, `open`). That leaves two
real gaps and four missing task families:

1. A move to open table is a hard learning failure — `classify_move` raises `LearnError`
   ("not inside a container and not on another object"), so "put the book aside" cannot be
   learned at all.
2. Wide or flat objects are silently shrunk by `fit_to_gripper` at learn time
   (`demo.py`), so the sim never shows a big object being handled at true size.
3. No verb covers pouring, stirring, cutting or pressing — common tabletop tasks that are
   invisible in resting positions.

The fix adds six actions, taking the vocabulary from four to ten. Each earns its slot by
closing gap 1 or 2 or by opening a task family, and each follows the existing pattern:
a motion in the simulator, an effect in the world, a ground-truth check, and an honest
refusal when preconditions fail.

## The two-track rule (unchanged)

Every action is read from the clip on one of two tracks:

- **Geometry track**: SAM resting positions before/after a move, compiled by
  `learn.classify_move`.
- **Semantic track**: Muse Spark reads the process; used for actions whose end state cannot
  reveal them (`SEMANTIC_ACTIONS`).

## Vocabulary

| Action | Track | `object` is | `target` is | `relation` |
|---|---|---|---|---|
| `place_near` | geometry | thing moved | reference object | one of the five, required |
| `push` | geometry default, semantic override | thing pushed | container, or reference object | optional (only with a reference object) |
| `pour` | semantic | the cup/bottle poured | container | none |
| `stir` | semantic | the spoon/tool | container | none |
| `cut` | semantic | the knife | the thing cut | none |
| `press` | semantic | the thing pressed | same as `object` | none |

`SEMANTIC_ACTIONS` becomes `{wipe, open, pour, stir, cut, press}`.

Track notes:

- **place_near** becomes `classify_move`'s fallback: destination in no container and on no
  object → target is the nearest other object (within a pixel radius), relation derived
  from the pixel offset direction (next_to when it is the generic fallback). Only an
  off-table destination remains a `LearnError`.
- **push** cannot be told apart from a pick-place by resting positions, so geometry reads
  such a move as `place_near`; when Muse reads "the hand pushed it", Muse's reading wins
  through the existing disagreement/question machinery.
- **cut** is semantic even though the object count changes: the moves pipeline tracks
  existing labels, and one object becoming two is not a move.

## Program schema

`Step` gains one optional field; every existing program file stays valid:

```python
relation: Literal["next_to", "left_of", "right_of", "in_front_of", "behind"] | None = None
```

Used by `place_near` (required) and `push` (optional). Overhead clips keep camera frame
and table frame co-oriented, so a relation word means the same thing at learn time and at
replay time.

`Step.__str__` gains: `put X next to Y` (and the other relations), `push X into Y` /
`push X next to Y`, `pour X into Y`, `stir Y with X`, `cut Y with X`, `press X`.

## Learning (`learn.py`)

- `classify_move` fallback: nearest other object within a pixel radius of the destination
  → `Step(object, "place_near", target=nearest, relation=derived)`. The relation is always
  directional, taken from the dominant axis of the pixel offset
  (`left_of`/`right_of`/`in_front_of`/`behind`). `next_to` is never produced by geometry;
  it exists for Muse Spark's reading and chat corrections, where a direction was not stated.
- `learn_program` height bookkeeping: a `place_near` sets `heights[object] = 0` (it ends on
  the table), like `place_in`.

## Muse reading (`meta/muse.py`)

- `PROMPT`: six new action lines in the same style as the current four, including the
  object/target/relations conventions above.
- `step_schema`: action enum extended; `relation` as an optional property restricted to the
  five words, valid only on `place_near`/`push`.
- `DESCRIBE_PROMPT`: one new line — `pressable` (buttons, pumps, push-lights), following the
  existing `openable` convention. `profile_from_description` reads it as a boolean.

## Objects (`objects.py`)

- `ObjectProfile.pressable: bool = False`.
- A `push` step's object skips `fit_to_gripper` at learn time: big/flat things keep their
  true size because they are never grasped.
- Cut halves: when the world splits a box, each half is a box with half the width, the same
  depth/height/colour, named `<name>_half_a`/`<name>_half_b`, with its own profile and SAM
  phrases (`sim_prompts` picks the colour word up from the parent name).

## World state (`sim/scene.py`)

Three abstractions, each with a visual stand-in, following `_dirt` and `_lid`:

- **Contents**: presence + `mixed` flag per name (label is cosmetic, no amounts, no fluid
  physics). Visual: a flat coloured disc inside the cup/tray, a sibling of `_add_dirt`;
  `pour` moves it, `stir` blends it. API: `pour_into(source, target)`, `contents_of(name)`,
  `is_mixed(name)`.
- **Split**: `split(name)` removes a box and reveals two pre-built hidden halves (built the
  way `_add_lid` pre-builds the seal). API: `halves_of(name)`.
- **Pressed**: a boolean per pressable object; visual is a small colour switch. API:
  `is_pressed(name)`.

World initialization follows `dirty_surfaces`: whatever a program pours **from** starts
full; whatever a program stirs starts with contents, unmixed; whatever a program presses
starts unpressed.

## Motions and checks (`sim/skills.py`, `sim/controller.py`, `sim/executor.py`)

| Action | Motion | `verify` check | Honest refusal |
|---|---|---|---|
| `place_near` | pick-place to a free spot relative to the target, via a free-spot helper generalized out of `_drop_spot` | offset from target within a band; direction matches `relation` | no free spot found |
| `push` | new `controller.slide(name, to)`: TCP behind the object at low z, drive forward — no grasp, contact does the work | object within band of target | no straight-line push path (blocked/other object in the way) |
| `pour` | grasp the cup, carry above the target, tilt the wrist, hold; `world.pour_into` moves the disc; put the cup back | target has contents, source does not | source holds no contents |
| `stir` | `wipe`'s pattern but circles inside the container rim, tool above the floor | `is_mixed(target)` | target has no contents |
| `cut` | grasp the knife, one straight sweep over the target; `world.split(target)` | both halves exist, original gone | target is not a box ("cannot cut a ball", mirroring the stacking-on-a-sphere refusal) |
| `press` | descend onto it, dwell, retract | `is_pressed(object)` | profile not `pressable` |

Executor dispatch follows the existing `open`/`wipe` early-continue pattern; belief updates
(`perceived`) apply to `place_near` and `push` like the pick-place path.

## Chat validation (`chat.py`), API, web

- Chat corrections keep the on-table constraint and gain profile-aware checks: no `press`
  on a non-pressable object, no `cut` on a non-box, no `pour` from a source that cannot
  hold contents. Same refusal style as today (the plan names objects that are not there).
- `api/schemas.py` mirrors the new action enum and `relation`.
- Web: `format.ts` labels for the six actions and the five relations; `StepRow` action
  picker plus a relation picker when the action uses one.

## Samples and evaluation

`scripts/generate_videos.py` gains one clip per family, each with a scene file:

- `cup_pour` — pour a cup into a bowl
- `bowl_stir` — stir a bowl with a spoon
- `book_push_aside` — push a wide flat box aside (true size, not shrunk)
- `bar_cut` — halve a box with a knife
- `lamp_press` — press a push-light

They join `eval-demo` and `eval-replay` automatically once `verify` supports their checks
(those tools iterate `samples/`). Replay needs no new machinery: halves carry SAM phrases,
so perception finds them on shuffled layouts.

## Testing

- `classify_move`: fallback-to-`place_near` tests, relation derivation, height bookkeeping.
- Per-action simulator tests in the `sim/stack_test.py` pattern: execute then `verify`,
  including each honest refusal.
- `muse.step_schema` enum/`relation` shape; `profile_from_description` `pressable` parsing.
- Chat validation tests for the three profile-aware refusals.
- Web `format.ts` tests for the new labels.
- All offline (no network), as today.

## Files touched

`program.py`, `learn.py`, `meta/muse.py`, `objects.py`, `sim/scene.py`, `sim/skills.py`,
`sim/controller.py`, `sim/executor.py`, `chat.py`, `api/schemas.py`, `demo.py` (skip
fitting for push), `evaluate.py` (sample wiring), `scripts/generate_videos.py`, web
(`format.ts`, `StepRow.tsx`, related tests), `samples/` (five new clips + scene files),
`README.md` (skills table, results).

## Out of scope

Selectors/macros (`sort`, "every red block") — a program-schema change deferred to its own
design. An `unknown` → question path for actions outside the vocabulary. Fluid amounts,
deformables, tearing beyond the seal-strip abstraction. Real footage.
