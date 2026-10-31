# Six New Actions Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `place_near`, `push`, `pour`, `stir`, `cut` and `press` to ShowOnce's action vocabulary, each with a learning path, a simulator motion, a ground-truth check and an honest refusal.

**Architecture:** The vocabulary lives in `program.py` and fans out to `muse.py` (semantic track), `learn.py` (geometry track), `scene.py` (world state), `skills.py`/`controller.py` (motions), `executor.py` (dispatch + verify), `chat.py`/`api`/web (conversation and UI). New world state (contents, halves, pressed) follows the existing `dirt`/`lid` pattern: abstract state with a visual stand-in, initialized from the program.

**Tech Stack:** Python 3.12 + uv, pydantic, MuJoCo, pytest; React + TypeScript + Tailwind in `web/`.

**Spec:** `docs/superpowers/specs/2026-11-01-new-actions-design.md`

## Global Constraints

- All tests run offline: `uv run pytest` needs no network and no API keys. Simulator tests skip automatically when `assets/mujoco_menagerie/franka_emika_panda/panda.xml` is missing (`needs_panda` marker, see `tests/test_skills.py:14`).
- The action tuple, verbatim: `("place_in", "stack_on", "wipe", "open", "place_near", "push", "pour", "stir", "cut", "press")`.
- The relation tuple, verbatim: `("next_to", "left_of", "right_of", "in_front_of", "behind")`.
- `SEMANTIC_ACTIONS` after this plan: `frozenset({"wipe", "open", "pour", "stir", "cut", "press"})`.
- Every existing program JSON in `runs/` must still parse: `Step.relation` defaults to `None`.
- World-frame relation units (top camera: image right is world −y, image up is world +x; the filming hand enters from the bottom edge): `left_of` → +y, `right_of` → −y, `in_front_of` → −x, `behind` → +x.
- No new dependencies. No fluid amounts, no deformables — state abstractions only.
- Honest refusals are `ExecutionError` with a message naming the object, in the style of `executor.py` today.

---

### Task 1: Vocabulary and the `relation` field

**Files:**
- Modify: `src/showonce/program.py`
- Modify: `src/showonce/geometry.py` (add `RELATION_UNIT` near the top, after the existing constants)
- Create: `tests/test_program.py`

**Interfaces:**
- Produces: `Action` (10-entry Literal), `Relation` (5-entry Literal), `SEMANTIC_ACTIONS` (6 entries), `Step.relation: Relation | None = None`, `RELATION_UNIT: dict[str, tuple[float, float]]` in `showonce.geometry`. Later tasks import these exact names.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_program.py`:

```python
from showonce.program import SEMANTIC_ACTIONS, Step


def test_step_text_for_the_new_actions() -> None:
    assert (
        str(Step(object="red block", action="place_near", target="blue block"))
        == "put red block next to blue block"
    )
    assert (
        str(Step(object="red block", action="place_near", target="blue block", relation="left_of"))
        == "put red block left of blue block"
    )
    assert str(Step(object="green book", action="push", target="bin")) == "push green book into bin"
    assert (
        str(Step(object="green book", action="push", target="red block", relation="behind"))
        == "push green book behind red block"
    )
    assert str(Step(object="red cup", action="pour", target="bowl")) == "pour red cup into bowl"
    assert str(Step(object="yellow spoon", action="stir", target="bowl")) == "stir bowl with yellow spoon"
    assert str(Step(object="gray knife", action="cut", target="white bar")) == "cut white bar with gray knife"
    assert str(Step(object="orange lamp", action="press", target="orange lamp")) == "press orange lamp"


def test_relation_defaults_to_none_so_old_programs_still_parse() -> None:
    step = Step.model_validate_json('{"object": "a", "action": "place_in", "target": "bin"}')
    assert step.relation is None


def test_semantic_actions_cover_the_invisible_processes() -> None:
    assert SEMANTIC_ACTIONS == frozenset({"wipe", "open", "pour", "stir", "cut", "press"})
```

Add to `tests/test_program.py`:

```python
def test_relation_unit_points_the_way_the_camera_sees() -> None:
    from showonce.geometry import RELATION_UNIT

    assert RELATION_UNIT["left_of"] == (0.0, 1.0)
    assert RELATION_UNIT["right_of"] == (0.0, -1.0)
    assert RELATION_UNIT["in_front_of"] == (-1.0, 0.0)
    assert RELATION_UNIT["behind"] == (1.0, 0.0)
    assert RELATION_UNIT["next_to"] == (0.0, 0.0)
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_program.py -v`
Expected: FAIL (`Step` rejects the new action values; `RELATION_UNIT` missing).

- [ ] **Step 3: Implement**

In `src/showonce/geometry.py`, after the existing module constants, add:

```python
# Which way a relation points on the table, in world meters (x toward the far edge, y left).
# The top camera maps image right to world -y and image up to world +x, and the filming
# hand enters from the bottom edge, so these match what the person in the clip saw.
RELATION_UNIT: dict[str, tuple[float, float]] = {
    "next_to": (0.0, 0.0),
    "left_of": (0.0, 1.0),
    "right_of": (0.0, -1.0),
    "in_front_of": (-1.0, 0.0),
    "behind": (1.0, 0.0),
}
```

Replace the top of `src/showonce/program.py` (lines 10–14) with:

```python
Action = Literal[
    "place_in", "stack_on", "wipe", "open", "place_near", "push", "pour", "stir", "cut", "press"
]
Relation = Literal["next_to", "left_of", "right_of", "in_front_of", "behind"]

# Actions that geometry (where things ended up) cannot tell apart from a plain move: the
# video has to be understood. A wipe slides a tool over something, an open tears it apart,
# a pour tips a cup, a stir circles a tool through a bowl, a cut divides, a press pushes
# straight down and changes nothing that rests.
SEMANTIC_ACTIONS: frozenset[str] = frozenset({"wipe", "open", "pour", "stir", "cut", "press"})
```

Rewrite the `Step` docstring and class body in `program.py`:

```python
class Step(BaseModel):
    """What happens to ``object``.

    - place_in / stack_on: ``object`` ends up in / on ``target``.
    - place_near: ``object`` ends up on the table, ``relation`` says where around ``target``.
    - push: ``object`` is slid, not lifted, to ``target`` (a container, or an object + relation).
    - wipe: ``object`` is a tool (sponge, cloth) rubbed over ``target`` to clean it.
    - pour: ``object`` is a cup whose contents end up in the container ``target``.
    - stir: ``object`` is a spoon or tool stirred through the container ``target``.
    - cut: ``object`` is a knife; ``target`` ends up in two halves.
    - press: ``object`` is pressed straight down. ``target`` is ``object``.
    - open: ``object`` is a packet, bag or box that gets torn open. ``target`` is ``object``.
    """

    object: str
    action: Action
    target: str
    relation: Relation | None = None

    def __str__(self) -> str:
        rel = (self.relation or "next_to").replace("_", " ")
        match self.action:
            case "place_in":
                return f"put {self.object} in {self.target}"
            case "stack_on":
                return f"stack {self.object} on {self.target}"
            case "place_near":
                return f"put {self.object} {rel} {self.target}"
            case "push":
                to = rel if self.relation else "into"
                return f"push {self.object} {to} {self.target}"
            case "pour":
                return f"pour {self.object} into {self.target}"
            case "stir":
                return f"stir {self.target} with {self.object}"
            case "cut":
                return f"cut {self.target} with {self.object}"
            case "press":
                return f"press {self.object}"
            case "open":
                return f"open {self.object}"
            case "wipe":
                return f"wipe {self.target} with {self.object}"
```

- [ ] **Step 4: Run the tests**

Run: `uv run pytest tests/test_program.py -v`
Expected: PASS (all 4).

- [ ] **Step 5: Run the full suite for regressions**

Run: `uv run pytest -x -q`
Expected: PASS except possibly tests that enumerate actions — if `tests/test_muse.py` or web-adjacent Python tests assert the old 4-entry enum, note the failures; they are fixed by their own tasks below. Do not fix them here.

- [ ] **Step 6: Commit**

```bash
git add src/showonce/program.py src/showonce/geometry.py tests/test_program.py
git commit -m "Add six actions and the relation field to the task program"
```

---

### Task 2: Geometry-track fallback — `place_near` in learning

**Files:**
- Modify: `src/showonce/learn.py`
- Modify: `tests/test_learn.py`

**Interfaces:**
- Consumes: `Step(..., relation=...)` from Task 1.
- Produces: `classify_move` no longer raises for a move to open table near another object; it returns `Step(object, "place_near", target, relation=...)`. Module constant `NEAR_RADIUS_PX = 90.0`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_learn.py` (mirror its existing imports; it already imports `LearnError`, `learn_program`, `Move`, `Rest`, `Step` — extend the `Step` usage with `relation=`):

```python
def test_move_to_open_table_becomes_place_near() -> None:
    moves = [
        Move(label="red block", start_frame=10, end_frame=40, src=(100.0, 100.0), dst=(300.0, 110.0))
    ]
    rests = {
        "red block": [Rest(0, 10, (100.0, 100.0)), Rest(40, 90, (300.0, 110.0))],
        "blue block": [Rest(0, 90, (320.0, 100.0))],
    }
    program = learn_program("t", moves, rests, [])
    assert program.steps == [
        Step(object="red block", action="place_near", target="blue block", relation="left_of")
    ]


def test_place_near_relation_follows_the_dominant_axis() -> None:
    moves = [
        Move(label="red block", start_frame=10, end_frame=40, src=(100.0, 100.0), dst=(320.0, 160.0))
    ]
    rests = {
        "red block": [Rest(0, 10, (100.0, 100.0)), Rest(40, 90, (320.0, 160.0))],
        "blue block": [Rest(0, 90, (320.0, 100.0))],
    }
    program = learn_program("t", moves, rests, [])
    assert program.steps[0].relation == "in_front_of"  # lower in frame, toward the person


def test_a_move_to_nowhere_still_fails() -> None:
    moves = [
        Move(label="red block", start_frame=10, end_frame=40, src=(100.0, 100.0), dst=(600.0, 500.0))
    ]
    rests = {
        "red block": [Rest(0, 10, (100.0, 100.0)), Rest(40, 90, (600.0, 500.0))],
        "blue block": [Rest(0, 90, (320.0, 100.0))],
    }
    with pytest.raises(LearnError):
        learn_program("t", moves, rests, [])
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_learn.py -v`
Expected: the three new tests FAIL with `LearnError` raised (fallback not implemented).

- [ ] **Step 3: Implement**

In `src/showonce/learn.py`, add after `STACK_RADIUS_PX = 45.0`:

```python
NEAR_RADIUS_PX = 90.0  # how close to another object a "put it beside that" landing counts
```

Add the helper:

```python
def _pixel_relation(dx: float, dy: float) -> str:
    """Which side of the target an object landed on, in the clip's image frame.

    Image x runs right and image y runs down; the hand enters from the bottom edge, so
    dy > 0 is toward the person (in front).
    """
    if abs(dx) >= abs(dy):
        return "left_of" if dx < 0 else "right_of"
    return "in_front_of" if dy > 0 else "behind"
```

In `classify_move`, track the nearest rest alongside the stack search. Replace the block
that starts `best: tuple[int, float, str] | None = None` through the `return Step(...,
"stack_on", ...)` with:

```python
    best: tuple[int, float, str] | None = None
    nearest: tuple[float, str, Rest] | None = None
    for label, rests in all_rests.items():
        if label == move.label:
            continue
        rest = _rest_near(rests, move.end_frame)
        if rest is None:
            continue
        distance = math.dist(rest.center, move.dst)
        if nearest is None or distance < nearest[0]:
            nearest = (distance, label, rest)
        if distance > STACK_RADIUS_PX:
            continue
        candidate = (-heights.get(label, 0), distance, label)
        if best is None or candidate < best:
            best = candidate
    if best is not None:
        return Step(object=move.label, action="stack_on", target=best[2])
    if nearest is not None and nearest[0] <= NEAR_RADIUS_PX:
        distance, label, rest = nearest
        dx, dy = move.dst[0] - rest.center[0], move.dst[1] - rest.center[1]
        return Step(
            object=move.label,
            action="place_near",
            target=label,
            relation=_pixel_relation(dx, dy),  # type: ignore[arg-type]
        )
    raise LearnError(
        f"Cannot explain move of {move.label} to {tuple(round(v) for v in move.dst)}: "
        "not inside a container, not on another object and not beside one."
    )
```

`learn_program` needs no change: its height bookkeeping already writes `0` for every
non-`stack_on` action, and `place_near` ends on the table.

- [ ] **Step 4: Run the tests**

Run: `uv run pytest tests/test_learn.py -v`
Expected: PASS (new and old).

- [ ] **Step 5: Commit**

```bash
git add src/showonce/learn.py tests/test_learn.py
git commit -m "Learn place_near when a move ends beside an object on open table"
```

---

### Task 3: `pressable` on the object profile

**Files:**
- Modify: `src/showonce/objects.py`
- Modify: `tests/test_objects.py`

**Interfaces:**
- Produces: `ObjectProfile.pressable: bool = False`; `profile_from_description` reads `pressable` from the description dict; `sim_prompts` yields a button phrase first for pressable objects. Task 5 (`Shape.pressable`) and Task 12 (executor refusal) consume this.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_objects.py`:

```python
def test_pressable_comes_from_the_description() -> None:
    profile = profile_from_description(
        {"shape": "cylinder", "width_cm": 8, "depth_cm": 8, "height_cm": 3, "pressable": True}
    )
    assert profile.pressable


def test_pressable_prompts_lead_with_a_button() -> None:
    profile = ObjectProfile(shape="cylinder", width=0.08, depth=0.08, height=0.03, pressable=True, rgb=(0.9, 0.4, 0.1))
    assert sim_prompts("orange lamp", profile)[0] == "orange button"
```

Check the file's existing imports and add `profile_from_description`, `sim_prompts` if missing.

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_objects.py -v`
Expected: the two new tests FAIL.

- [ ] **Step 3: Implement**

In `src/showonce/objects.py`:

Add to `ObjectProfile` after `openable`:

```python
    pressable: bool = False  # a button, pump or push-light: press it straight down
```

In `profile_from_description`, add to the `ObjectProfile(...)` constructor call after `openable=...`:

```python
        pressable=bool(description.get("pressable")),
```

In `sim_prompts`, add a branch before the `elif profile.shape == "cylinder" and ...` branch:

```python
    elif profile.pressable:
        phrases = [f"{word} button", f"{word} lamp"]
```

- [ ] **Step 4: Run the tests**

Run: `uv run pytest tests/test_objects.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/showonce/objects.py tests/test_objects.py
git commit -m "Objects can be pressable, with a button phrase for SAM"
```

---

### Task 4: Contents state in the world (pour/stir)

**Files:**
- Modify: `src/showonce/sim/scene.py`
- Modify: `src/showonce/sim/executor.py` (init wiring only)
- Modify: `tests/test_sim.py`

**Interfaces:**
- Produces: `SimWorld.__init__(..., contents: Collection[str] = (), pour_targets: Collection[str] = ())`; methods `pour_into(source: str, target: str) -> None`, `contents_of(name: str) -> str | None`, `stir(name: str) -> None`, `is_mixed(name: str) -> bool`. In executor: `contents_for(program) -> tuple[set[str], set[str]]` and `build_world` passing both sets. Tasks 9 and 10 consume these.
- Consumes: nothing new.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_sim.py` (reuse its imports; it already imports `SimWorld`, `ZoneDef`, `block_def`, `ObjectProfile` and the `needs_panda` marker — follow whatever exact import style the file uses):

```python
@needs_panda
def test_contents_pour_from_the_cup_into_the_bowl() -> None:
    cup = block_def("red cup", ObjectProfile(shape="cylinder", width=0.06, depth=0.06, height=0.08))
    world = SimWorld(
        [cup], [ZoneDef("bowl", (0.4, 0.1), (0.16, 0.16))],
        contents=["red cup"], pour_targets=["bowl"],
    )
    assert world.contents_of("red cup") is not None and world.contents_of("bowl") is None
    world.pour_into("red cup", "bowl")
    assert world.contents_of("red cup") is None and world.contents_of("bowl") is not None


@needs_panda
def test_a_stirred_bowl_is_marked_mixed() -> None:
    bowl = ZoneDef("bowl", (0.4, 0.1), (0.16, 0.16))
    world = SimWorld([], [bowl], contents=["bowl"])
    assert not world.is_mixed("bowl")
    world.stir("bowl")
    assert world.is_mixed("bowl")


def test_contents_for_the_program_from_its_pour_and_stir_steps() -> None:
    program = TaskProgram(
        name="t",
        steps=[
            Step(object="red cup", action="pour", target="bowl"),
            Step(object="yellow spoon", action="stir", target="bowl"),
        ],
    )
    full, targets = contents_for(program)
    assert full == {"red cup", "bowl"} and targets == {"bowl"}
```

Add `contents_for` and, if missing, `build_world`, `Layout`, `TaskProgram`, `Step` to the test file's imports from `showonce.sim.executor` / `showonce.program`.

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_sim.py -v`
Expected: the new tests FAIL (`contents` unknown, `contents_for` not importable).

- [ ] **Step 3: Implement**

In `src/showonce/sim/scene.py`:

Add a constant after `DIRT_RADIUS = 0.012`:

```python
CONTENTS_RGBA = (0.55, 0.42, 0.2, 1.0)  # dry cereal-brown: contents are an abstraction, not a fluid
```

Change `SimWorld.__init__` signature (after `dirty`):

```python
        contents: Collection[str] = (),
        pour_targets: Collection[str] = (),
```

In `__init__`, after the `self._dirt = {...}` block, add:

```python
        self._contents = {name: "full" for name in contents}
        self._mixed: set[str] = set()
        self._content_geoms = {
            name: mujoco.mj_name2id(
                self.model, mujoco.mjtObj.mjOBJ_GEOM, f"contents_{name}"
            )
            for name in (*contents, *pour_targets)
        }
        for name in pour_targets:
            self.model.geom_rgba[self._content_geoms[name], 3] = 0.0  # empty until poured into
```

In `_build_scene`, add a `contents`/`pour_targets` pass — change its signature to
`_build_scene(spec, blocks, zones, dirty, contents, pour_targets)` (all plain sets), update
the call in `__init__` to pass them through, and in the zone loop after `_add_tray` add:

```python
            if zone.name in contents or zone.name in pour_targets:
                half = (zone.size[0] / 2 - RIM_THICKNESS, zone.size[1] / 2 - RIM_THICKNESS)
                SimWorld._add_contents(world, zone.name, (*zone.center, TRAY_FLOOR), half)
```

In the block loop, after the `if block.name in dirty:` block, add:

```python
            if block.name in contents or block.name in pour_targets:
                hx, hy, hz = block.shape.half
                SimWorld._add_contents(body, block.name, (0.0, 0.0, hz), (hx, hy))
```

Add the static builder next to `_add_dirt`:

```python
    @staticmethod
    def _add_contents(
        body: mujoco.MjsBody, name: str, top: tuple[float, float, float], half: tuple[float, float]
    ) -> None:
        """A flat disc of contents, drawn only (no collisions): what a pour moves around."""
        cx, cy, z = top
        body.add_geom(
            name=f"contents_{name}",
            type=mujoco.mjtGeom.mjGEOM_CYLINDER,
            pos=[cx, cy, z + 0.0008],
            size=[min(half) * 0.7, 0.0008, 0],
            rgba=list(CONTENTS_RGBA),
            contype=0,
            conaffinity=0,
            mass=0.0001,
        )
```

Add the state methods next to `scrub`/`dirt_left`:

```python
    def pour_into(self, source: str, target: str) -> None:
        """Everything in ``source`` ends up in ``target``: the disc moves, no drops, no amounts."""
        if self._contents.get(source) is None:
            raise ValueError(f"'{source}' has nothing to pour")
        self._contents[source] = None
        self._contents[target] = "poured"
        self.model.geom_rgba[self._content_geoms[source], 3] = 0.0
        self.model.geom_rgba[self._content_geoms[target], 3] = 1.0

    def contents_of(self, name: str) -> str | None:
        return self._contents.get(name)

    def stir(self, name: str) -> None:
        self._mixed.add(name)

    def is_mixed(self, name: str) -> bool:
        return name in self._mixed
```

In `src/showonce/sim/executor.py`, add next to `dirty_surfaces`:

```python
def contents_for(program: TaskProgram) -> tuple[set[str], set[str]]:
    """(what starts holding contents, what starts empty but will be poured into).

    Like ``dirty_surfaces``: the program itself says what the world must start with, so a
    pour source starts full and a stirred bowl starts unmixed-but-full.
    """
    full = {s.object for s in program.steps if s.action == "pour"}
    full |= {s.target for s in program.steps if s.action == "stir"}
    targets = {s.target for s in program.steps if s.action == "pour"}
    return full, targets
```

In `build_world`, compute and pass them:

```python
    full, pour_targets = contents_for(program) if program else (set(), set())
    world = SimWorld(
        [block_def(name, layout.profiles.get(name)) for name in layout.objects],
        [ZoneDef(r.name, r.center, r.size) for r in layout.regions],
        dirty=dirty_surfaces(program) if program else (),
        contents=full,
        pour_targets=pour_targets,
    )
```

- [ ] **Step 4: Run the tests**

Run: `uv run pytest tests/test_sim.py -v`
Expected: PASS (new and existing).

- [ ] **Step 5: Commit**

```bash
git add src/showonce/sim/scene.py src/showonce/sim/executor.py tests/test_sim.py
git commit -m "World contents: an abstract disc that a pour moves and a stir mixes"
```

---

### Task 5: Pressed and split state in the world (press/cut)

**Files:**
- Modify: `src/showonce/objects.py` (nothing — pressable already there)
- Modify: `src/showonce/sim/scene.py`
- Modify: `src/showonce/sim/executor.py` (halves wiring in `build_world`)
- Modify: `tests/test_sim.py`

**Interfaces:**
- Produces: `Shape.pressable: bool`; `SimWorld.press(name)`, `is_pressed(name)`, `split(name)`, `is_split(name)`, `halves_of(name) -> tuple[str, str]` (raises `KeyError` when the world has no halves for `name`). Halves are named `"<name> half a"` / `"<name> half b"` and appear in `world.block_names`. `build_world` adds halves for every `cut` target. Tasks 11 and 12 consume these.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_sim.py`:

```python
@needs_panda
def test_pressing_darkens_and_marks_the_object() -> None:
    lamp = block_def(
        "orange lamp", ObjectProfile(shape="cylinder", width=0.08, depth=0.08, height=0.03, pressable=True)
    )
    world = SimWorld([lamp], [])
    world.set_block("orange lamp", (0.45, 0.0))
    assert not world.is_pressed("orange lamp")
    world.press("orange lamp")
    assert world.is_pressed("orange lamp")


@needs_panda
def test_cutting_swaps_a_box_for_its_two_halves() -> None:
    profiles = {"white bar": ObjectProfile(shape="box", width=0.12, depth=0.05, height=0.04)}
    program = TaskProgram(
        name="t", steps=[Step(object="gray knife", action="cut", target="white bar")]
    )
    world = build_world(Layout({"white bar": (0.45, 0.0), "gray knife": (0.45, 0.2)}, [], profiles), program)
    assert world.halves_of("white bar") == ("white bar half a", "white bar half b")
    assert not world.is_split("white bar")
    world.split("white bar")
    assert world.is_split("white bar")
    for half in world.halves_of("white bar"):
        assert world.block_pos(half)[2] > 0.0  # both halves rest on the table
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_sim.py -v`
Expected: the two new tests FAIL.

- [ ] **Step 3: Implement**

In `src/showonce/sim/scene.py`:

Add to `Shape` after `openable`:

```python
    pressable: bool = False  # a button or pump: press it straight down
```

In `shape_of`, pass it through:

```python
    return Shape(profile.shape, half, handle, profile.openable, profile.pressable)
```

In `__init__`, after the `self._content_geoms` block, add:

```python
        names = set(self.block_names)
        self._halves = {
            b.name: (f"{b.name} half a", f"{b.name} half b")
            for b in blocks
            if f"{b.name} half a" in names and f"{b.name} half b" in names
        }
        self._pressed: set[str] = set()
```

In `_build_scene`, after the block loop's `graspable` handling, hide halves so they start
out of the scene — pass the halves map into `_build_scene` (or recompute it there by the
same name convention) and add after the equality welds:

```python
        for block in blocks:
            if f"{block.name} half a" in {b.name for b in blocks}:
                for half in (f"{block.name} half a", f"{block.name} half b"):
                    spec.body(half).pos = [0.0, 0.0, -0.4]  # parked under the table until the cut
```

Then in `__init__`, right before `self.reset()`, freeze the hidden halves:

```python
        for pair in self._halves.values():
            for half in pair:
                body_id = mujoco.mj_name2id(self.model, mujoco.mjtObj.mjOBJ_BODY, half)
                self.model.body_gravcomp[body_id] = 1.0  # frozen while parked
```

Add the state methods next to `is_open`:

```python
    def halves_of(self, name: str) -> tuple[str, str]:
        """The two bodies a cut replaces ``name`` with."""
        return self._halves[name]

    def split(self, name: str) -> None:
        """Replace a box with its two halves, lying side by side where it stood."""
        if name not in self._halves:
            raise ValueError(f"'{name}' is not something that can be cut in two")
        pos = self.block_pos(name)
        hx = self._shapes[name].half[0]
        for sign, half in zip((1.0, -1.0), self._halves[name]):
            self.set_block(half, (float(pos[0]) + sign * (hx / 2 + 0.008), float(pos[1])))
            body_id = mujoco.mj_name2id(self.model, mujoco.mjtObj.mjOBJ_BODY, half)
            self.model.body_gravcomp[body_id] = 0.0  # a real object again
        self._park(name)

    def is_split(self, name: str) -> bool:
        if name not in self._halves:
            return False
        gone = self.block_pos(name)[2] < 0.0
        on_table = all(self.block_pos(h)[2] > 0.0 for h in self._halves[name])
        return gone and on_table

    def press(self, name: str) -> None:
        """Press a pressable object: it latches down and darkens."""
        geom = mujoco.mj_name2id(self.model, mujoco.mjtObj.mjOBJ_GEOM, f"{name}_geom")
        self.model.geom_rgba[geom, :3] *= 0.6
        self._pressed.add(name)

    def is_pressed(self, name: str) -> bool:
        return name in self._pressed

    def _park(self, name: str) -> None:
        """Teleport a body far under the table and freeze it, out of the scene."""
        joint = self.model.joint(int(self.model.body(name).jntadr[0]))
        adr = int(joint.qposadr[0])
        self.data.qpos[adr : adr + 7] = [0.0, 0.0, -0.4, 1, 0, 0, 0]
        self.data.qvel[int(joint.dofadr[0]) : int(joint.dofadr[0]) + 6] = 0
        self.model.body_gravcomp[self.model.body(name).id] = 1.0
        mujoco.mj_forward(self.model, self.data)
```

In `src/showonce/sim/executor.py`, extend `build_world` to create halves for cut targets:

```python
def _half_profiles(layout: Layout, program: TaskProgram | None) -> dict[str, ObjectProfile]:
    """A half-profile for every box the program cuts: half the width, everything else the same."""
    halves: dict[str, ObjectProfile] = {}
    if not program:
        return halves
    for step in program.steps:
        if step.action != "cut" or step.target in halves:
            continue
        parent = layout.profiles.get(step.target)
        if parent is None:
            continue
        for suffix in ("a", "b"):
            halves[f"{step.target} half {suffix}"] = parent.model_copy(
                update={"width": parent.width / 2}
            )
    return halves
```

and in `build_world`:

```python
    blocks = [
        block_def(name, layout.profiles.get(name)) for name in layout.objects
    ] + [
        block_def(name, profile)
        for name, profile in _half_profiles(layout, program).items()
    ]
    world = SimWorld(
        blocks,
        [ZoneDef(r.name, r.center, r.size) for r in layout.regions],
        dirty=dirty_surfaces(program) if program else (),
        contents=full,
        pour_targets=pour_targets,
    )
    for name, xy in layout.objects.items():
        world.set_block(name, xy)
```

Note: `set_block` is only called for `layout.objects`, so the halves keep the parked start
position given in `_build_scene`.

- [ ] **Step 4: Run the tests**

Run: `uv run pytest tests/test_sim.py -v`
Expected: PASS. If MuJoCo rejects two free bodies at the same parked spot, jitter the
parked positions in `_build_scene` (`-0.4 - 0.05 * i` per half).

- [ ] **Step 5: Commit**

```bash
git add src/showonce/sim/scene.py src/showonce/sim/executor.py tests/test_sim.py
git commit -m "World press and split: a pressed latch and a box that becomes two halves"
```

---

### Task 6: Controller primitives — `tilt` and `slide`

**Files:**
- Modify: `src/showonce/sim/controller.py`
- Modify: `tests/test_skills.py`

**Interfaces:**
- Produces: `PandaController.tilt(angle: float, steps: int = 200) -> None` (0 returns the wrist upright), `PandaController.dwell(steps: int = 100) -> None`, and `PandaController.slide(name: str, to: tuple[float, float]) -> None` (push without grasping). `sweep` gains a default `on_waypoint=None`. Tasks 8, 9, 10, 12 consume them.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_skills.py`:

```python
@needs_panda
def test_slide_pushes_a_box_without_grasping() -> None:
    book = ObjectProfile(shape="box", width=0.2, depth=0.14, height=0.03)  # far too wide to grasp
    layout = Layout({"green book": (0.35, -0.1)}, [], {"green book": book})
    world = build_world(layout, None)
    controller = PandaController(world)
    controller.reset_to_home()
    before = world.block_pos("green book").copy()
    controller.slide("green book", (0.35, 0.15))
    moved = float(np.linalg.norm(world.block_pos("green book")[:2] - before[:2]))
    assert moved > 0.15
```

Add `import numpy as np` if the file does not already import it.

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_skills.py::test_slide_pushes_a_box_without_grasping -v`
Expected: FAIL with `AttributeError: ... no attribute 'slide'`.

- [ ] **Step 3: Implement**

In `src/showonce/sim/controller.py`, first give `sweep`'s callback a default (the stir
skill calls it without one):

```python
    def sweep(
        self,
        path: list[tuple[float, float]],
        z: float,
        on_waypoint: Callable[[], None] | None = None,
    ) -> None:
```

(`Callable` is already imported at the top of the file.)

Then add after `pull_off`:

```python
    def dwell(self, steps: int = 100) -> None:
        """Advance the simulation in place: a held moment, nothing moving on purpose."""
        self._advance(steps)

    def slide(self, name: str, to: tuple[float, float]) -> None:
        """Push ``name`` across the table to ``to`` without picking it up.

        For things too wide or flat for the gripper: the closed fingertips drive it and
        contact does the work.
        """
        pos = self.world.block_pos(name)
        delta = np.array([to[0] - float(pos[0]), to[1] - float(pos[1])])
        length = float(np.linalg.norm(delta))
        if length < 1e-3:
            return
        unit = delta / length
        standoff = self.world.shape(name).footprint + 0.03
        z = max(float(pos[2]), 0.03)  # never drag the fingertips on the table
        start = np.array([float(pos[0]) - unit[0] * standoff, float(pos[1]) - unit[1] * standoff, z])
        finish = np.array([to[0] + unit[0] * standoff * 0.5, to[1] + unit[1] * standoff * 0.5, z])
        self.set_gripper(CLOSED, steps=60)
        self.move_to(start + np.array([0.0, 0.0, 0.06]))
        self.move_to(start)
        self.move_to(finish)
        self._advance(300)  # let it settle
        self.move_to(finish + np.array([0.0, 0.0, 0.06]))

    def tilt(self, angle: float, steps: int = 200) -> None:
        """Pitch the wrist by ``angle`` radians from upright (joint 5), cup still in hand."""
        target = self.q_home.copy()
        target[4] = self.q_home[4] + angle
        self._move_joints(target, steps=steps)
```

- [ ] **Step 4: Run the tests**

Run: `uv run pytest tests/test_skills.py -v`
Expected: PASS. If the push stalls (moved < 0.15), raise the settle count to 600 before
touching anything else; if it still stalls, increase `standoff` to `footprint + 0.05`.

- [ ] **Step 5: Commit**

```bash
git add src/showonce/sim/controller.py tests/test_skills.py
git commit -m "Controller can push without grasping and tilt its wrist"
```

---

### Task 7: `place_near` — free-spot search, executor dispatch, verify

**Files:**
- Modify: `src/showonce/sim/skills.py`
- Modify: `src/showonce/sim/executor.py`
- Modify: `tests/test_executor.py`

**Interfaces:**
- Produces: `free_spot(anchor: XY, half: tuple[float, float], others: list[tuple[XY, float]], keep_out: list[tuple[XY, XY]], direction: XY | None = None) -> XY` in `skills.py` (raises `ValueError` when no spot is free). Executor handles `place_near`; `verify` checks it. Task 8 reuses `free_spot` for `push`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_executor.py` (mirror existing imports: `Layout`, `build_world`, `execute`, `verify`, `ExecutionError`, `PandaController`, `Step`, `TaskProgram`, `ObjectProfile`, and `needs_panda` if the file defines it — if not, copy the marker from `tests/test_skills.py`):

```python
@needs_panda
def test_place_near_sets_it_down_beside_the_target() -> None:
    profiles = {
        "red block": ObjectProfile(shape="box", width=0.05, depth=0.05, height=0.05),
        "blue block": ObjectProfile(shape="box", width=0.05, depth=0.05, height=0.05),
    }
    layout = Layout({"red block": (0.35, -0.1), "blue block": (0.5, 0.1)}, [], profiles)
    program = TaskProgram(
        name="t",
        steps=[Step(object="red block", action="place_near", target="blue block", relation="left_of")],
    )
    world = build_world(layout, program)
    execute(program, world, PandaController(world), [])
    checks = verify(program, world, [])
    assert all(c.ok for c in checks), [c.detail for c in checks]
    dx, dy = world.block_pos("red block")[:2] - world.block_pos("blue block")[:2]
    assert dy > 0.0  # left_of is world +y


def test_place_near_refuses_an_unknown_target() -> None:
    program = TaskProgram(name="t", steps=[Step(object="a", action="place_near", target="ghost")])
    with pytest.raises(ExecutionError):
        execute(program, _empty_world_with("a"), PandaController(_empty_world_with("a")), [])
```

For the second test, add a tiny helper at the top of the appended block instead of
`_empty_world_with` (name it concretely):

```python
def _world_with_blocks(**profiles: ObjectProfile) -> tuple:
    layout = Layout({name: (0.4 + 0.1 * i, 0.0) for i, name in enumerate(profiles)}, [], dict(profiles))
    world = build_world(layout, None)
    return world, PandaController(world)
```

and rewrite the refusal test to use it:

```python
@needs_panda
def test_place_near_refuses_an_unknown_target() -> None:
    world, controller = _world_with_blocks(**{"red block": ObjectProfile()})
    program = TaskProgram(
        name="t", steps=[Step(object="red block", action="place_near", target="ghost")]
    )
    with pytest.raises(ExecutionError, match="Unknown"):
        execute(program, world, controller, [])
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_executor.py -v`
Expected: new tests FAIL (executor falls through to the container branch).

- [ ] **Step 3: Implement**

In `src/showonce/sim/skills.py`, generalize `_drop_spot` by adding a public helper above it
(leave `_drop_spot` in place for `open_package`; it can be refactored onto `free_spot`
later without behavior change):

```python
REACH_X, REACH_Y = (0.20, 0.62), (-0.28, 0.28)  # where the arm can set something down


def free_spot(
    anchor: XY,
    half: tuple[float, float],
    others: list[tuple[XY, float]],
    keep_out: list[tuple[XY, XY]],
    direction: XY | None = None,
) -> XY:
    """A clear place to set something down: beside ``anchor`` at ``half``'s footprint.

    ``direction`` is a unit vector away from the anchor (a relation's world unit); ``None``
    tries all four sides. Raises ``ValueError`` when nowhere within arm reach is clear.
    """
    reach_x = max(half[0], 0.02)
    reach_y = max(half[1], 0.02)
    unit = (direction[0], direction[1]) if direction and direction != (0.0, 0.0) else None
    dirs = [unit] if unit else [(1.0, 0.0), (-1.0, 0.0), (0.0, 1.0), (0.0, -1.0)]
    gaps = (0.02, 0.05, 0.08, 0.11)
    best, best_room = None, -math.inf
    for d in dirs:
        dx, dy = d[0] * (reach_x if d[0] else reach_y), d[1] * (reach_y if d[1] else reach_x)
        for gap in gaps:
            spot = (anchor[0] + dx + d[0] * gap, anchor[1] + dy + d[1] * gap)
            if not (REACH_X[0] <= spot[0] <= REACH_X[1] and REACH_Y[0] <= spot[1] <= REACH_Y[1]):
                continue
            room = min(
                [
                    max(abs(spot[0] - p[0]) - r - half[0], abs(spot[1] - p[1]) - r - half[1])
                    for p, r in others
                ]
                + [1.0]
            )
            for centre, size in keep_out:
                room = min(
                    room,
                    max(abs(spot[0] - centre[0]) - size[0] / 2, abs(spot[1] - centre[1]) - size[1] / 2),
                )
            if gap != 0:
                room -= gap * 0.5  # the closer beside, the better
            if room > best_room:
                best, best_room = spot, room
    if best is None:
        raise ValueError(f"No free place beside {anchor}")
    return best
```

In `src/showonce/sim/executor.py`:

- Import `free_spot` from `showonce.sim.skills` (extend the existing import line) and
  `RELATION_UNIT` from `showonce.geometry`.
- Inside `execute`, after the `wipe` branch and before the `stack_on` branch, add:

```python
        if step.action == "place_near":
            if step.target not in world.block_names:
                raise ExecutionError(f"Unknown neighbour '{step.target}' in step: {step}")
            neighbour = where(step.target)
            others = [
                (tuple(where(n)[:2]), world.shape(n).footprint)
                for n in world.block_names
                if n not in (step.object, step.target)
            ]
            keep_out = [(r.center, (r.size[0] + 0.05, r.size[1] + 0.05)) for r in regions]
            hx, hy, _ = world.shape(step.object).half
            unit = RELATION_UNIT.get(step.relation or "next_to")
            try:
                target_xy = free_spot(
                    (float(neighbour[0]), float(neighbour[1])), (hx, hy), others, keep_out, unit
                )
            except ValueError as exc:
                raise ExecutionError(f"No free spot for '{step.object}': {exc}") from exc
            controller.pick_place(
                step.object, target_xy, 0.0, pick_at=where(step.object) if belief else None
            )
            if belief is not None:
                belief[step.object] = np.array(
                    [target_xy[0], target_xy[1], world.half_height(step.object)]
                )
            if on_step_done is not None:
                on_step_done(index, str(step))
            continue
```

- In `verify`, add before the final `else` (stack_on) branch:

```python
        elif step.action == "place_near":
            near = world.block_pos(step.target)
            dx, dy = pos[0] - near[0], pos[1] - near[1]
            band = world.shape(step.object).radius + world.shape(step.target).radius + 0.04
            ok = (dx * dx + dy * dy) ** 0.5 <= band
            if ok and step.relation and step.relation != "next_to":
                ux, uy = RELATION_UNIT[step.relation]
                ok = dx * ux + dy * uy > 0  # on the side the relation names
            checks.append(
                StepCheck(str(step), bool(ok), f"offset ({dx * 1000:.0f}, {dy * 1000:.0f}) mm")
            )
```

- [ ] **Step 4: Run the tests**

Run: `uv run pytest tests/test_executor.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/showonce/sim/skills.py src/showonce/sim/executor.py tests/test_executor.py
git commit -m "place_near: a free-spot pick-and-place beside a neighbour"
```

---

### Task 8: `push` — executor dispatch and verify

**Files:**
- Modify: `src/showonce/sim/executor.py`
- Modify: `tests/test_executor.py`

**Interfaces:**
- Consumes: `controller.slide` (Task 6), `free_spot` (Task 7), `RELATION_UNIT`.
- Produces: executor handles `push` (container target or object target with optional relation); `verify` checks both.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_executor.py`:

```python
@needs_panda
def test_push_slides_a_too_wide_book_beside_a_block() -> None:
    profiles = {
        "green book": ObjectProfile(shape="box", width=0.2, depth=0.14, height=0.03),
        "red block": ObjectProfile(shape="box", width=0.05, depth=0.05, height=0.05),
    }
    layout = Layout({"green book": (0.32, -0.15), "red block": (0.5, 0.1)}, [], profiles)
    program = TaskProgram(
        name="t",
        steps=[Step(object="green book", action="push", target="red block", relation="behind")],
    )
    world = build_world(layout, program)
    execute(program, world, PandaController(world), [])
    checks = verify(program, world, [])
    assert all(c.ok for c in checks), [c.detail for c in checks]
    dz = world.block_pos("green book")[0] - world.block_pos("red block")[0]
    assert dz > 0.0  # behind is world +x


@needs_panda
def test_push_into_a_container_lands_inside() -> None:
    profiles = {"green book": ObjectProfile(shape="box", width=0.2, depth=0.14, height=0.03)}
    layout = Layout(
        {"green book": (0.32, -0.15)},
        [Region("bin", (0.5, 0.15), (0.22, 0.22))],
        profiles,
    )
    program = TaskProgram(name="t", steps=[Step(object="green book", action="push", target="bin")])
    world = build_world(layout, program)
    execute(program, world, PandaController(world), layout.regions)
    assert all(c.ok for c in verify(program, world, layout.regions))
```

`Region` comes from `showonce.sim.executor` (already imported in this test file's import
line if not, add it), plus one refusal test:

```python
@needs_panda
def test_push_refuses_a_blocked_path() -> None:
    profiles = {
        "green book": ObjectProfile(shape="box", width=0.2, depth=0.14, height=0.03),
        "red block": ObjectProfile(shape="box", width=0.05, depth=0.05, height=0.05),
        "blue block": ObjectProfile(shape="box", width=0.05, depth=0.05, height=0.05),
    }
    # the blue block sits squarely between the book and the red block
    layout = Layout(
        {"green book": (0.3, 0.0), "red block": (0.55, 0.0), "blue block": (0.42, 0.0)},
        [], profiles,
    )
    program = TaskProgram(
        name="t",
        steps=[Step(object="green book", action="push", target="red block", relation="in_front_of")],
    )
    world = build_world(layout, program)
    with pytest.raises(ExecutionError, match="blocked"):
        execute(program, world, PandaController(world), [])
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_executor.py -v`
Expected: new tests FAIL.

- [ ] **Step 3: Implement**

Add a corridor helper at module level in `src/showonce/sim/executor.py`:

```python
def _segment_clearance(
    start: XY, to: XY, point: XY
) -> float:
    """How far ``point`` is from the straight line ``start`` -> ``to`` (meters)."""
    sx, sy = start
    tx, ty = to
    px, py = point
    dx, dy = tx - sx, ty - sy
    length2 = dx * dx + dy * dy
    if length2 < 1e-9:
        return float(math.hypot(px - sx, py - sy))
    t = max(0.0, min(1.0, ((px - sx) * dx + (py - sy) * dy) / length2))
    return float(math.hypot(px - (sx + t * dx), py - (sy + t * dy)))
```

(`import math` at the top of `executor.py` if it is not there yet.)

In `execute`, add a `push` branch after `place_near`:

```python
        if step.action == "push":
            if step.target in by_name:
                region = by_name[step.target]
                to = slot_xy(region, placed[step.target], world.shape(step.object).radius)
                placed[step.target] += 1
            elif step.target in world.block_names:
                neighbour = where(step.target)
                others = [
                    (tuple(where(n)[:2]), world.shape(n).footprint)
                    for n in world.block_names
                    if n not in (step.object, step.target)
                ]
                keep_out = [(r.center, (r.size[0] + 0.05, r.size[1] + 0.05)) for r in regions]
                hx, hy, _ = world.shape(step.object).half
                unit = RELATION_UNIT.get(step.relation or "next_to")
                try:
                    to = free_spot(
                        (float(neighbour[0]), float(neighbour[1])), (hx, hy), others, keep_out, unit
                    )
                except ValueError as exc:
                    raise ExecutionError(f"No free spot to push '{step.object}' to: {exc}") from exc
            else:
                raise ExecutionError(f"Unknown push target '{step.target}' in step: {step}")
            src = (float(where(step.object)[0]), float(where(step.object)[1]))
            for n in world.block_names:
                if n in (step.object, step.target):
                    continue
                p = where(n)
                gap = _segment_clearance(src, to, (float(p[0]), float(p[1]))) - (
                    world.shape(step.object).radius + world.shape(n).radius
                )
                if gap < 0.01:
                    raise ExecutionError(
                        f"Cannot push '{step.object}': '{n}' blocks the way"
                    )
            controller.slide(step.object, to)
            if belief is not None:
                belief[step.object] = np.array([to[0], to[1], world.half_height(step.object)])
            if on_step_done is not None:
                on_step_done(index, str(step))
            continue
```

Also move the grasp-width guard: today it runs for everything after `open`/`wipe`. After
Tasks 7–12, it must run only for grasping actions. Wrap it:

```python
        if step.action in ("place_in", "place_near", "pour", "stir", "cut"):
            if world.shape(step.object).grasp_width > MAX_GRASP_WIDTH + 1e-6:
                raise ExecutionError(f"'{step.object}' is too wide for the gripper")
```

(Delete the old unguarded check.)

In `verify`, extend the `place_in` branch to cover `push` with a container target, and add
the object-target case. Replace the `elif step.action == "place_in":` branch with:

```python
        elif step.action in ("place_in", "push") and step.target in by_name:
            region = by_name[step.target]
            dx, dy = abs(pos[0] - region.center[0]), abs(pos[1] - region.center[1])
            ok = dx <= region.size[0] / 2 + 0.01 and dy <= region.size[1] / 2 + 0.01
            checks.append(
                StepCheck(str(step), bool(ok), f"offset ({dx * 1000:.0f}, {dy * 1000:.0f}) mm")
            )
        elif step.action == "push":
            near = world.block_pos(step.target)
            dx, dy = pos[0] - near[0], pos[1] - near[1]
            band = world.shape(step.object).radius + world.shape(step.target).radius + 0.05
            ok = (dx * dx + dy * dy) ** 0.5 <= band
            if ok and step.relation and step.relation != "next_to":
                ux, uy = RELATION_UNIT[step.relation]
                ok = dx * ux + dy * uy > 0
            checks.append(
                StepCheck(str(step), bool(ok), f"offset ({dx * 1000:.0f}, {dy * 1000:.0f}) mm")
            )
```

- [ ] **Step 4: Run the tests**

Run: `uv run pytest tests/test_executor.py tests/test_skills.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/showonce/sim/executor.py tests/test_executor.py
git commit -m "push: slide an ungraspable object beside a neighbour or into a container"
```

---

### Task 9: `pour` — skill, executor, verify

**Files:**
- Modify: `src/showonce/sim/skills.py`
- Modify: `src/showonce/sim/executor.py`
- Modify: `tests/test_skills.py`

**Interfaces:**
- Consumes: `controller.tilt` (Task 6), `world.pour_into`/`contents_of` (Task 4), `Region` from executor.
- Produces: `pour(world, controller, source: str, source_at: Vec, region: Region) -> None` in `skills.py`.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_skills.py`:

```python
@needs_panda
def test_pour_empties_the_cup_into_the_bowl() -> None:
    cup = ObjectProfile(shape="cylinder", width=0.06, depth=0.06, height=0.08, handle=True)
    profiles = {"red cup": cup}
    layout = Layout({"red cup": (0.4, -0.1)}, [Region("bowl", (0.5, 0.12), (0.16, 0.16))], profiles)
    program = TaskProgram(name="t", steps=[Step(object="red cup", action="pour", target="bowl")])
    world = build_world(layout, program)
    execute(program, world, PandaController(world), layout.regions)
    checks = verify(program, world, layout.regions)
    assert all(c.ok for c in checks), [c.detail for c in checks]
    assert world.contents_of("bowl") is not None and world.contents_of("red cup") is None
```

Add `Region` to the executor import line, and `execute`/`verify` are already imported.

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_skills.py::test_pour_empties_the_cup_into_the_bowl -v`
Expected: FAIL (executor has no `pour` branch).

- [ ] **Step 3: Implement**

In `src/showonce/sim/skills.py`, add `pour` (needs `Region` — import it from
`showonce.sim.executor` would be circular; instead define the motion to take plain
values. Use this signature to avoid the cycle):

```python
def pour(
    world: SimWorld,
    controller: PandaController,
    source: str,
    source_at: Vec,
    target_name: str,
    centre: XY,
) -> None:
    """Hold the cup over the target, tip it until it is empty, and set it back down.

    The contents are an abstraction (Task 4): the transfer happens in ``pour_into``, not
    in the physics.
    """
    over = np.array([centre[0], centre[1], TRAY_FLOOR + 0.14])
    controller.grasp(source, source_at)
    controller.move_to(over)
    controller.tilt(2.0)
    world.pour_into(source, target_name)
    controller.dwell(100)
    controller.tilt(0.0)
    controller.release(source, source_at + np.array([0.0, 0.0, 0.002]))
```

Import `TRAY_FLOOR` from `showonce.sim.scene` (extend the existing import at the top of
`skills.py`, which already pulls `STRIP_HALF, STRIP_TAIL, SimWorld, strip_offset`).

In `executor.py`, add a branch after `push`:

```python
        if step.action == "pour":
            region = by_name.get(step.target)
            if region is None:
                raise ExecutionError(f"Unknown container '{step.target}' in step: {step}")
            if world.contents_of(step.object) is None:
                raise ExecutionError(f"'{step.object}' has nothing to pour")
            pour(world, controller, step.object, where(step.object), step.target, region.center)
            if on_step_done is not None:
                on_step_done(index, str(step))
            continue
```

(Import `pour` in the executor's skills import line.)

In `verify`, add:

```python
        elif step.action == "pour":
            ok = world.contents_of(step.target) is not None and world.contents_of(step.object) is None
            checks.append(
                StepCheck(str(step), bool(ok), f"{step.target} holds the poured contents")
            )
```

- [ ] **Step 4: Run the tests**

Run: `uv run pytest tests/test_skills.py -v`
Expected: PASS. If the tilt tips the cup out of the weld (cup drops), reduce the tilt to
1.6 rad and re-run; the check only cares that contents moved and the cup came back.

- [ ] **Step 5: Commit**

```bash
git add src/showonce/sim/skills.py src/showonce/sim/executor.py tests/test_skills.py
git commit -m "pour: tip the cup over the bowl and move the contents"
```

---

### Task 10: `stir` — skill, executor, verify

**Files:**
- Modify: `src/showonce/sim/skills.py`
- Modify: `src/showonce/sim/executor.py`
- Modify: `tests/test_skills.py`

**Interfaces:**
- Consumes: `circle_path` (exists in `skills.py`), `world.stir`/`is_mixed`/`contents_of` (Task 4), `TRAY_FLOOR`, `RIM_THICKNESS` from `scene.py`.
- Produces: `stir(world, controller, tool: str, tool_at: Vec, target_name: str, centre: XY, half: XY) -> None`.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_skills.py`:

```python
@needs_panda
def test_stir_mixes_the_bowl() -> None:
    spoon = ObjectProfile(shape="box", width=0.025, depth=0.025, height=0.09)
    layout = Layout(
        {"yellow spoon": (0.4, -0.1)}, [Region("bowl", (0.5, 0.12), (0.16, 0.16))],
        {"yellow spoon": spoon},
    )
    program = TaskProgram(
        name="t", steps=[Step(object="yellow spoon", action="stir", target="bowl")]
    )
    world = build_world(layout, program)
    execute(program, world, PandaController(world), layout.regions)
    checks = verify(program, world, layout.regions)
    assert all(c.ok for c in checks), [c.detail for c in checks]
    assert world.is_mixed("bowl")
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_skills.py::test_stir_mixes_the_bowl -v`
Expected: FAIL.

- [ ] **Step 3: Implement**

In `skills.py`, add after `pour`:

```python
def stir(
    world: SimWorld,
    controller: PandaController,
    tool: str,
    tool_at: Vec,
    target_name: str,
    centre: XY,
    half: XY,
) -> None:
    """Swirl the spoon through the bowl's contents, inside the rim, and put it back."""
    hx, hy, hz = world.shape(tool).half
    z = TRAY_FLOOR + hz + CLEARANCE  # the tool rides just above the bowl's floor
    radius = max(0.01, min(half) - min(hx, hy) - 0.005)
    path = circle_path(centre, radius, (hx, hy))

    controller.grasp(tool, tool_at)
    start = path[0]
    controller.move_to(np.array([start[0], start[1], z + 0.06]))
    controller.move_to(np.array([start[0], start[1], z]))
    controller.sweep(path[1:], z)
    world.stir(target_name)
    controller.release(tool, tool_at + np.array([0.0, 0.0, 0.002]))
```

In `executor.py`, add after `pour`:

```python
        if step.action == "stir":
            region = by_name.get(step.target)
            if region is None:
                raise ExecutionError(f"Unknown container '{step.target}' in step: {step}")
            if world.contents_of(step.target) is None:
                raise ExecutionError(f"'{step.target}' has no contents to stir")
            stir(
                world,
                controller,
                step.object,
                where(step.object),
                step.target,
                region.center,
                (region.size[0] / 2 - RIM_THICKNESS, region.size[1] / 2 - RIM_THICKNESS),
            )
            if on_step_done is not None:
                on_step_done(index, str(step))
            continue
```

Import `stir` alongside `pour`. In `verify`:

```python
        elif step.action == "stir":
            ok = world.is_mixed(step.target)
            checks.append(StepCheck(str(step), bool(ok), "mixed" if ok else "not mixed"))
```

- [ ] **Step 4: Run the tests**

Run: `uv run pytest tests/test_skills.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/showonce/sim/skills.py src/showonce/sim/executor.py tests/test_skills.py
git commit -m "stir: swirl a tool through the bowl's contents"
```

---

### Task 11: `cut` — skill, executor, verify

**Files:**
- Modify: `src/showonce/sim/skills.py`
- Modify: `src/showonce/sim/executor.py`
- Modify: `tests/test_skills.py`

**Interfaces:**
- Consumes: `world.split`/`is_split` (Task 5).
- Produces: `cut(world, controller, knife: str, knife_at: Vec, target: str, centre: XY, half: XY) -> None`.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_skills.py`:

```python
@needs_panda
def test_cut_divides_the_bar_and_refuses_a_ball() -> None:
    knife = ObjectProfile(shape="box", width=0.02, depth=0.04, height=0.02)
    bar = ObjectProfile(shape="box", width=0.12, depth=0.05, height=0.04)
    layout = Layout(
        {"gray knife": (0.4, -0.15), "white bar": (0.5, 0.1)}, [], {"gray knife": knife, "white bar": bar}
    )
    program = TaskProgram(name="t", steps=[Step(object="gray knife", action="cut", target="white bar")])
    world = build_world(layout, program)
    execute(program, world, PandaController(world), [])
    assert all(c.ok for c in verify(program, world, []))

    ball_layout = Layout(
        {"gray knife": (0.4, -0.15), "red ball": (0.5, 0.1)},
        [],
        {"gray knife": knife, "red ball": ObjectProfile(shape="sphere", width=0.05, depth=0.05, height=0.05)},
    )
    bad = TaskProgram(name="t2", steps=[Step(object="gray knife", action="cut", target="red ball")])
    with pytest.raises(ExecutionError, match="round"):
        execute(bad, build_world(ball_layout, bad), PandaController(build_world(ball_layout, bad)), [])
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_skills.py::test_cut_divides_the_bar_and_refuses_a_ball -v`
Expected: FAIL.

- [ ] **Step 3: Implement**

In `skills.py`, add after `stir`:

```python
def cut(
    world: SimWorld,
    controller: PandaController,
    knife: str,
    knife_at: Vec,
    target: str,
    centre: XY,
    half: XY,
) -> None:
    """Draw the knife across the middle of ``target`` in one straight line and split it."""
    hz = world.shape(knife).half[2]
    top = float(world.block_pos(target)[2]) + world.shape(target).half[2]
    z = top + hz + 0.002
    y = half[1] + 0.03
    controller.grasp(knife, knife_at)
    controller.move_to(np.array([centre[0], centre[1] - y, z + 0.06]))
    controller.move_to(np.array([centre[0], centre[1] - y, z]))
    controller.move_to(np.array([centre[0], centre[1] + y, z]))  # one pass, edge to edge
    world.split(target)
    controller.release(knife, knife_at + np.array([0.0, 0.0, 0.002]))
```

In `executor.py`, add after `stir`:

```python
        if step.action == "cut":
            if step.target not in world.block_names:
                raise ExecutionError(f"Unknown cut target '{step.target}' in step: {step}")
            if world.shape(step.target).kind != "box":
                raise ExecutionError(f"Cannot cut '{step.target}': it is round")
            target_at = where(step.target)
            hx, hy, _ = world.shape(step.target).half
            cut(
                world,
                controller,
                step.object,
                where(step.object),
                step.target,
                (float(target_at[0]), float(target_at[1])),
                (hx, hy),
            )
            if on_step_done is not None:
                on_step_done(index, str(step))
            continue
```

Import `cut` in the executor's skills import line. In `verify`:

```python
        elif step.action == "cut":
            ok = world.is_split(step.target)
            checks.append(StepCheck(str(step), bool(ok), "in two halves" if ok else "still whole"))
```

- [ ] **Step 4: Run the tests**

Run: `uv run pytest tests/test_skills.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/showonce/sim/skills.py src/showonce/sim/executor.py tests/test_skills.py
git commit -m "cut: one straight pass with the knife and the box comes apart"
```

---

### Task 12: `press` — skill, executor, verify

**Files:**
- Modify: `src/showonce/sim/skills.py`
- Modify: `src/showonce/sim/executor.py`
- Modify: `tests/test_skills.py`

**Interfaces:**
- Consumes: `world.press`/`is_pressed` (Task 5), `Shape.pressable` (Task 5), `ObjectProfile.pressable` (Task 3).

- [ ] **Step 1: Write the failing test**

Append to `tests/test_skills.py`:

```python
@needs_panda
def test_press_latches_the_lamp_down() -> None:
    lamp = ObjectProfile(shape="cylinder", width=0.08, depth=0.08, height=0.03, pressable=True)
    layout = Layout({"orange lamp": (0.45, 0.0)}, [], {"orange lamp": lamp})
    program = TaskProgram(name="t", steps=[Step(object="orange lamp", action="press", target="orange lamp")])
    world = build_world(layout, program)
    execute(program, world, PandaController(world), [])
    assert all(c.ok for c in verify(program, world, []))


@needs_panda
def test_press_refuses_something_without_a_button() -> None:
    mug = ObjectProfile(shape="cylinder", width=0.064, depth=0.064, height=0.08, handle=True)
    layout = Layout({"red mug": (0.45, 0.0)}, [], {"red mug": mug})
    bad = TaskProgram(name="t", steps=[Step(object="red mug", action="press", target="red mug")])
    world = build_world(layout, bad)
    with pytest.raises(ExecutionError, match="press"):
        execute(bad, world, PandaController(world), [])
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_skills.py -v -k press`
Expected: FAIL.

- [ ] **Step 3: Implement**

In `skills.py`, add after `cut`:

```python
def press(world: SimWorld, controller: PandaController, target: str, at: Vec) -> None:
    """Push straight down on a button with the closed fingertips, hold, and back off."""
    controller.set_gripper(CLOSED, steps=60)
    controller.move_to(at + np.array([0.0, 0.0, 0.08]))
    controller.move_to(at + np.array([0.0, 0.0, 0.004]))
    world.press(target)
    controller.dwell(60)  # a firm moment on the button
    controller.move_to(at + np.array([0.0, 0.0, 0.08]))
```

Import `CLOSED` from `showonce.sim.controller` (extend the existing
`from showonce.sim.controller import PandaController` line).

In `executor.py`, add a `press` branch **before** the grasp-width guard (press never
grasps), next to `open`:

```python
        if step.action == "press":
            if not world.shape(step.object).pressable:
                raise ExecutionError(f"'{step.object}' has no button to press")
            press(world, controller, step.object, where(step.object))
            if on_step_done is not None:
                on_step_done(index, str(step))
            continue
```

Import `press` in the executor's skills import line. In `verify`:

```python
        elif step.action == "press":
            ok = world.is_pressed(step.object)
            checks.append(StepCheck(str(step), bool(ok), "pressed" if ok else "unpressed"))
```

- [ ] **Step 4: Run the tests**

Run: `uv run pytest tests/test_skills.py tests/test_executor.py -v`
Expected: PASS.

- [ ] **Step 5: Run the whole Python suite**

Run: `uv run pytest -q`
Expected: only the muse/chat/API/web-facing failures that later tasks fix (if any), everything else PASS. Note them.

- [ ] **Step 6: Commit**

```bash
git add src/showonce/sim/skills.py src/showonce/sim/executor.py tests/test_skills.py
git commit -m "press: push a button straight down and latch it"
```

---

### Task 13: Profile fitting for the new actions

**Files:**
- Modify: `src/showonce/demo.py` (`fit_profiles`)
- Modify: `tests/test_skills.py` (the existing `fit_profiles` test lives here)

**Interfaces:**
- Produces: `fit_profiles` keeps true size for `push`/`press` objects (never grasped), sets `pressable` for pressed objects, `openable`+box for opened ones (unchanged), and gripper-fits everything else it picks up (`place_in`, `place_near`, `pour`, `stir`, `cut`).

- [ ] **Step 1: Extend the failing test**

In `tests/test_skills.py`, extend `test_only_grasped_objects_are_fitted_to_the_gripper` — add to its program's steps and assertions:

```python
    program = TaskProgram(
        name="t",
        steps=[
            Step(object="sponge", action="wipe", target="plate"),
            Step(object="chips", action="open", target="chips"),
            Step(object="book", action="push", target="block"),
            Step(object="lamp", action="press", target="lamp"),
        ],
    )
    wide_book = ObjectProfile(shape="box", width=0.2, depth=0.14, height=0.03)
    lamp = ObjectProfile(shape="cylinder", width=0.08, depth=0.08, height=0.03)
    fitted = fit_profiles(
        {"sponge": wide_sponge, "plate": PLATE, "chips": wide_chips, "book": wide_book, "lamp": lamp, "block": ObjectProfile()},
        program,
    )
    assert fitted["book"].width == 0.2  # pushed, never grasped: true size
    assert fitted["lamp"].pressable  # a press marks the object pressable
    assert not fitted["book"].pressable
```

(Rewrite the existing test body to include the two new steps and three new assertions; keep its current assertions about sponge/plate/chips.)

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_skills.py::test_only_grasped_objects_are_fitted_to_the_gripper -v`
Expected: FAIL (`book` shrunk, `lamp.pressable` False).

- [ ] **Step 3: Implement**

In `src/showonce/demo.py`, replace the body of `fit_profiles`'s loop:

```python
    fitted = dict(profiles)
    for step in program.steps:
        profile = fitted.get(step.object)
        if profile is None:
            continue
        if step.action == "open":
            fitted[step.object] = profile.model_copy(update={"shape": "box", "openable": True})
        elif step.action == "push":
            pass  # slid, never grasped: it keeps its true size
        elif step.action == "press":
            fitted[step.object] = profile.model_copy(update={"pressable": True})
        else:
            fitted[step.object] = fit_to_gripper(profile)
    return fitted
```

- [ ] **Step 4: Run the tests**

Run: `uv run pytest tests/test_skills.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/showonce/demo.py tests/test_skills.py
git commit -m "Fit profiles to the new actions: pushed and pressed things keep their size"
```

---

### Task 14: Muse Spark prompt and schema

**Files:**
- Modify: `src/showonce/meta/muse.py`
- Modify: `tests/test_muse.py`

**Interfaces:**
- Produces: `PROMPT` describing all ten actions; `step_schema` with the ten-entry enum and optional `relation`; `DESCRIBE_PROMPT` asking for `pressable`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_muse.py` (mirror its imports — it already tests `step_schema`):

```python
def test_step_schema_knows_all_ten_actions_and_the_relation() -> None:
    schema = step_schema(["red cup"], ["bowl"])
    item = schema["properties"]["steps"]["items"]
    assert set(item["properties"]["action"]["enum"]) == {
        "place_in", "stack_on", "wipe", "open",
        "place_near", "push", "pour", "stir", "cut", "press",
    }
    assert item["properties"]["relation"]["enum"] == [
        "next_to", "left_of", "right_of", "in_front_of", "behind"
    ]
    assert "relation" not in item["required"]


def test_prompt_names_every_action() -> None:
    for action in ("place_near", "push", "pour", "stir", "cut", "press"):
        assert f'"{action}"' in PROMPT
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_muse.py -v`
Expected: new tests FAIL.

- [ ] **Step 3: Implement**

In `src/showonce/meta/muse.py`, extend the action list in `PROMPT` (keep the existing four
lines exactly as they are, add after them):

```python
  "place_near": an object ended up on the table beside another object, not in or on it
  "push": an object was slid across the table without ever being lifted
  "pour": a cup or bottle was tipped so its contents went into a container
  "stir": a spoon or tool was stirred round and round through a container's contents
  "cut": something was cut into two pieces with a knife
  "press": a button, pump or push-light was pressed straight down
```

and extend the field guidance lines:

```python
- object: the object that was moved; for "wipe" the cleaning tool; for "open" the thing opened;
  for "pour" the cup poured; for "stir" the spoon; for "cut" the knife; for "push" the thing slid
- target: for "place_in" the container, for "stack_on" the object underneath, for "wipe" the
  thing being cleaned, for "open" the same as object, for "place_near" the object it ended up
  beside, for "push" where it was pushed to (container or object), for "pour" the container
  poured into, for "stir" the container stirred, for "cut" the thing cut, for "press" the
  same as object
- relation: only for "place_near" (and "push" toward an object): one of "next_to", "left_of",
  "right_of", "in_front_of", "behind", from the camera's point of view
```

In `step_schema`, extend the action enum and add `relation`:

```python
                        "action": {
                            "type": "string",
                            "enum": [
                                "place_in", "stack_on", "wipe", "open",
                                "place_near", "push", "pour", "stir", "cut", "press",
                            ],
                        },
                        "relation": {
                            "type": "string",
                            "enum": ["next_to", "left_of", "right_of", "in_front_of", "behind"],
                        },
```

(`required` stays `["object", "action", "target"]`.)

In `DESCRIBE_PROMPT`, add one line to the bullet list describing each object:

```python
- pressable: true only if it is a button, pump or push-light (something you press straight down)
```

- [ ] **Step 4: Run the tests**

Run: `uv run pytest tests/test_muse.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/showonce/meta/muse.py tests/test_muse.py
git commit -m "Muse Spark reads the six new actions and can name a relation"
```

---

### Task 15: Chat — plain words and plan validation

**Files:**
- Modify: `src/showonce/chat.py`
- Modify: `tests/test_chat.py`

**Interfaces:**
- Produces: `how_it_will_do` covers all ten actions; `clean_steps` accepts the six new actions under the rules below and keeps `press` self-targeted like `open`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_chat.py` (mirror its imports — it tests `clean_steps` with objects/containers lists):

```python
def test_clean_steps_keeps_the_new_actions_that_make_sense() -> None:
    steps = [
        Step(object="red block", action="place_near", target="blue block", relation="left_of"),
        Step(object="green book", action="push", target="bin"),
        Step(object="red cup", action="pour", target="bowl"),
        Step(object="yellow spoon", action="stir", target="bowl"),
        Step(object="gray knife", action="cut", target="white bar"),
        Step(object="orange lamp", action="press", target="orange lamp"),
        Step(object="red cup", action="pour", target="blue block"),  # pour target not a container
        Step(object="gray knife", action="cut", target="ghost"),  # not on the table
    ]
    kept = clean_steps(steps, ["red block", "blue block", "green book", "red cup", "yellow spoon", "gray knife", "white bar", "orange lamp"], ["bin", "bowl"])
    assert kept == steps[:6]


def test_how_it_will_do_words_the_new_actions() -> None:
    assert "beside" in how_it_will_do(Step(object="a", action="place_near", target="b", relation="next_to"))
    assert "push" in how_it_will_do(Step(object="a", action="push", target="bin"))
    assert "pour" in how_it_will_do(Step(object="a", action="pour", target="bowl")).lower()
    assert "stir" in how_it_will_do(Step(object="a", action="stir", target="bowl")).lower()
    assert "cut" in how_it_will_do(Step(object="a", action="cut", target="b")).lower()
    assert "press" in how_it_will_do(Step(object="a", action="press", target="a")).lower()
```

Add `how_it_will_do` to the file's imports from `showonce.chat` if missing.

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_chat.py -v`
Expected: new tests FAIL.

- [ ] **Step 3: Implement**

In `src/showonce/chat.py`, extend `how_it_will_do`'s match:

```python
        case "place_near":
            rel = (step.relation or "next_to").replace("_", " ")
            return f"I'll pick up the {step.object} and set it down {rel} the {step.target}."
        case "push":
            rel = step.relation.replace("_", " ") if step.relation else None
            where = f"{rel} the {step.target}" if rel else f"into the {step.target}"
            return f"I'll put my fingers behind the {step.object} and push it {where}, without lifting it."
        case "pour":
            return f"I'll hold the {step.object} over the {step.target} and tip it until it is empty."
        case "stir":
            return f"I'll stir the {step.target} round and round with the {step.object} until it is mixed."
        case "cut":
            return f"I'll draw the {step.object} across the {step.target} and lay the two halves flat."
        case "press":
            return f"I'll press the {step.object} straight down, once and firmly."
```

Replace `clean_steps`'s condition chain with:

```python
    for step in steps:
        if step.object not in known:
            continue
        if step.action in ("open", "press"):
            out.append(Step(object=step.object, action=step.action, target=step.object))
        elif (
            (step.action == "place_in" and step.target in containers)
            or (step.action == "stack_on" and step.target in known and step.target != step.object)
            or (
                step.action == "wipe"
                and step.target != step.object
                and (step.target in known or step.target in containers)
            )
            or (step.action == "place_near" and step.target in known and step.target != step.object)
            or (
                step.action == "push"
                and (step.target in containers or (step.target in known and step.target != step.object))
            )
            or (step.action == "pour" and step.target in containers)
            or (step.action == "stir" and step.target in containers and step.target != step.object)
            or (step.action == "cut" and step.target in known and step.target != step.object)
        ):
            out.append(step)
```

- [ ] **Step 4: Run the tests**

Run: `uv run pytest tests/test_chat.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/showonce/chat.py tests/test_chat.py
git commit -m "Chat understands the six new actions and words them plainly"
```

---

### Task 16: Web API schemas

**Files:**
- Modify: `src/showonce/api/schemas.py`
- Modify: `tests/test_api.py`

**Interfaces:**
- Produces: `Action` (10 entries) and `StepModel.relation: Literal[...] | None = None` (serialized as `relation`, camelCase unaffected).

- [ ] **Step 1: Write the failing test**

Append to `tests/test_api.py`:

```python
def test_step_model_accepts_the_new_actions_and_relation() -> None:
    step = StepModel(object="a", action="place_near", target="b", relation="left_of")
    assert step.relation == "left_of"
    data = StepModel(object="c", action="press", target="c").model_dump(by_alias=True)
    assert data["action"] == "press" and data.get("relation") is None
```

Import `StepModel` from `showonce.api.schemas` if missing.

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_api.py -v`
Expected: FAIL (Action literal rejects `place_near`).

- [ ] **Step 3: Implement**

In `src/showonce/api/schemas.py`:

```python
Action = Literal[
    "place_in", "stack_on", "wipe", "open", "place_near", "push", "pour", "stir", "cut", "press"
]
Relation = Literal["next_to", "left_of", "right_of", "in_front_of", "behind"]
```

and on `StepModel`, after `target`:

```python
    relation: Relation | None = None
```

Also find where the API converts a `StepModel` to a `program.Step` (search
`src/showonce/api/` for `Step(`) and pass `relation=step.relation` through, and where a
`program.Step` becomes a `StepModel` (search for `StepModel(`) and back again — both
directions must carry `relation`.

- [ ] **Step 4: Run the tests**

Run: `uv run pytest tests/test_api.py -v && uv run mypy src`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/showonce/api/schemas.py src/showonce/api tests/test_api.py
git commit -m "API steps carry the new actions and their relation"
```

---

### Task 17: Web frontend — labels, targets, relation picker

**Files:**
- Modify: `web/src/api/schemas.ts` (Action union, Step type, new Relation type)
- Modify: `web/src/lib/format.ts` (`describeStep`, `targetsFor`, export `RELATIONS`)
- Modify: `web/src/features/program/StepRow.tsx` (relation `<select>` for place_near/push)
- Modify: `web/src/lib/format.test.ts`

**Interfaces:**
- Consumes: the API from Task 16 (`relation` on steps).

- [ ] **Step 1: Write the failing tests**

Append to `web/src/lib/format.test.ts` (mirror its imports/describe blocks):

```typescript
describe('describeStep for the new actions', () => {
  it('words place_near with and without a relation', () => {
    expect(describeStep({ object: 'red block', action: 'place_near', target: 'blue block', relation: 'left_of' })).toBe(
      'put red block left of blue block',
    )
    expect(describeStep({ object: 'red block', action: 'place_near', target: 'blue block' })).toBe(
      'put red block next to blue block',
    )
  })

  it('words the other five', () => {
    expect(describeStep({ object: 'green book', action: 'push', target: 'bin' })).toBe('push green book into bin')
    expect(describeStep({ object: 'red cup', action: 'pour', target: 'bowl' })).toBe('pour red cup into bowl')
    expect(describeStep({ object: 'yellow spoon', action: 'stir', target: 'bowl' })).toBe('stir bowl with yellow spoon')
    expect(describeStep({ object: 'gray knife', action: 'cut', target: 'white bar' })).toBe('cut white bar with gray knife')
    expect(describeStep({ object: 'orange lamp', action: 'press', target: 'orange lamp' })).toBe('press orange lamp')
  })

  it('targets the new actions', () => {
    const objects = ['red block', 'blue block']
    const containers = ['bin']
    expect(targetsFor('place_near', 'red block', objects, containers)).toEqual(['blue block'])
    expect(targetsFor('push', 'red block', objects, containers)).toEqual(['blue block', 'bin'])
    expect(targetsFor('pour', 'red cup', objects, containers)).toEqual(['bin'])
    expect(targetsFor('stir', 'red cup', objects, containers)).toEqual(['bin'])
    expect(targetsFor('cut', 'red block', objects, containers)).toEqual(['blue block'])
    expect(targetsFor('press', 'red block', objects, containers)).toEqual(['red block'])
  })
})
```

- [ ] **Step 2: Run to verify failure**

Run: `cd web && pnpm test`
Expected: new tests FAIL (exhaustive switch errors / wrong strings).

- [ ] **Step 3: Implement**

In `web/src/api/schemas.ts`, extend the `Action` union with the six new strings (same
order as Python) and add:

```typescript
export type Relation = 'next_to' | 'left_of' | 'right_of' | 'in_front_of' | 'behind'
```

and to the `Step` interface add `relation?: Relation | null` (find the interface that
`format.ts` imports `Step` from — extend exactly that one).

In `web/src/lib/format.ts`:

```typescript
export const RELATIONS: Relation[] = ['next_to', 'left_of', 'right_of', 'in_front_of', 'behind']

export function describeRelation(relation?: Relation | null): string {
  return (relation ?? 'next_to').replaceAll('_', ' ')
}
```

Rewrite `describeStep`'s switch, adding the six cases (mirroring `Step.__str__` in
Python exactly — the test strings above are the contract):

```typescript
    case 'place_near':
      return `put ${step.object} ${describeRelation(step.relation)} ${step.target}`
    case 'push':
      return step.relation
        ? `push ${step.object} ${describeRelation(step.relation)} ${step.target}`
        : `push ${step.object} into ${step.target}`
    case 'pour':
      return `pour ${step.object} into ${step.target}`
    case 'stir':
      return `stir ${step.target} with ${step.object}`
    case 'cut':
      return `cut ${step.target} with ${step.object}`
    case 'press':
      return `press ${step.object}`
```

Extend `targetsFor`:

```typescript
    case 'place_near':
      return others
    case 'push':
      return [...others, ...containers]
    case 'pour':
    case 'stir':
      return containers
    case 'cut':
      return others
    case 'press':
      return [object]
```

In `web/src/features/program/StepRow.tsx`, render a relation picker when the action uses
one — add below the target select (copy the target select's markup and classes):

```tsx
{(step.action === 'place_near' || step.action === 'push') && (
  <select
    aria-label={`Relation for step ${index + 1}`}
    className={selectClass}
    value={step.relation ?? 'next_to'}
    onChange={(e) => onEdit({ relation: e.target.value as Relation })}
  >
    {RELATIONS.map((r) => (
      <option key={r} value={r}>
        {describeRelation(r)}
      </option>
    ))}
  </select>
)}
```

Extend the edit patch so `relation` can flow through `onEdit`: in
`web/src/features/program/StepRow.tsx` the `Props.onEdit` type is
`Partial<Pick<EditableStep, 'object' | 'action' | 'target'>>` — add `'relation'` to that
`Pick`, and make sure `EditableStep` (in `web/src/features/workbench.ts`) carries
`relation?: Relation | null` (it is likely `Step` from the API plus UI fields, in which
case Task 17's schemas.ts change already covers it — check, and only add the field if
`EditableStep` re-declares it). Import `Relation`, `RELATIONS`, `describeRelation` where
needed.

- [ ] **Step 4: Run the web checks**

Run: `cd web && pnpm test && pnpm typecheck && pnpm lint`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add web/src
git commit -m "Web: edit and display the six new actions and their relation"
```

---

### Task 18: Sample clips — scene files and generator prompts

**Files:**
- Create: `samples/cup_pour.json`, `samples/bowl_stir.json`, `samples/book_push_aside.json`, `samples/bar_cut.json`, `samples/lamp_press.json`
- Modify: `scripts/chore_prompts.json`
- Create: `tests/test_samples.py`

**Interfaces:**
- Consumes: `Action` from Task 1. The mp4s themselves are generated later by the (paid, key-gated) dev tool; this task ships everything else.

- [ ] **Step 1: Write the failing test**

Create `tests/test_samples.py`:

```python
"""Every sample scene file must describe a program the system can actually express."""

from pathlib import Path

import pytest

from showonce.program import SEMANTIC_ACTIONS, Step
from showonce.scene_spec import SceneSpec

SAMPLES = Path(__file__).resolve().parent.parent / "samples"


@pytest.mark.parametrize("path", sorted(SAMPLES.glob("*.json")), ids=lambda p: p.stem)
def test_scene_files_parse_and_name_real_things(path: Path) -> None:
    scene = SceneSpec.model_validate_json(path.read_text())
    assert scene.prompts, "a scene with no objects cannot show anything"
    names = set(scene.prompts) | set(scene.containers)
    for step in scene.steps:
        assert isinstance(step, Step)
        assert step.object in names, f"{step.object} is not on the table in {path.name}"
        assert (
            step.target in names or step.target == step.object
        ), f"{step.target} is not on the table in {path.name}"


def test_the_new_clips_exist() -> None:
    for name in ("cup_pour", "bowl_stir", "book_push_aside", "bar_cut", "lamp_press"):
        assert (SAMPLES / f"{name}.json").exists()
```

Check `SceneSpec`'s field names first (`src/showonce/scene_spec.py`) — if the parsed
`steps` are plain dicts rather than `Step` objects, validate them with
`Step.model_validate(s)` inside the loop and assert on that instead.

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_samples.py -v`
Expected: `test_the_new_clips_exist` FAILs.

- [ ] **Step 3: Create the five scene files**

`samples/cup_pour.json`:

```json
{
  "name": "cup_pour",
  "notes": "AI-generated footage (anchored step). Step hand-labeled from the final video.",
  "size": [1280, 720],
  "prompts": {"red cup": "red cup"},
  "container_prompts": {"bowl": "white bowl"},
  "steps": [{"object": "red cup", "action": "pour", "target": "bowl"}]
}
```

`samples/bowl_stir.json`:

```json
{
  "name": "bowl_stir",
  "notes": "AI-generated footage (anchored step). Step hand-labeled from the final video.",
  "size": [1280, 720],
  "prompts": {"yellow spoon": "yellow spoon"},
  "container_prompts": {"bowl": "white bowl with flour"},
  "steps": [{"object": "yellow spoon", "action": "stir", "target": "bowl"}]
}
```

`samples/book_push_aside.json`:

```json
{
  "name": "book_push_aside",
  "notes": "AI-generated footage (anchored step). Step hand-labeled from the final video.",
  "size": [1280, 720],
  "prompts": {"green book": "large green book", "red block": "red block"},
  "container_prompts": {},
  "steps": [{"object": "green book", "action": "push", "target": "red block", "relation": "behind"}]
}
```

`samples/bar_cut.json`:

```json
{
  "name": "bar_cut",
  "notes": "AI-generated footage (anchored step). Step hand-labeled from the final video.",
  "size": [1280, 720],
  "prompts": {"gray knife": "gray knife", "white bar": "white dough bar"},
  "container_prompts": {},
  "steps": [{"object": "gray knife", "action": "cut", "target": "white bar"}]
}
```

`samples/lamp_press.json`:

```json
{
  "name": "lamp_press",
  "notes": "AI-generated footage (anchored step). Step hand-labeled from the final video.",
  "size": [1280, 720],
  "prompts": {"orange lamp": "orange push light"},
  "container_prompts": {},
  "steps": [{"object": "orange lamp", "action": "press", "target": "orange lamp"}]
}
```

In `scripts/chore_prompts.json`, add five entries under `clips` mirroring the exact shape
of the existing entries (`scene` string + however `steps` are spelled there — read the
file first and copy its field names verbatim). Content, in the file's `_style`/`_motion`
voice:

- `cup_pour`: "A red cup full of dry cereal sits on the left. An empty white bowl sits on the
  right. The hand picks up the red cup, holds it over the white bowl, tips it and pours all
  the cereal out, then sets the empty cup down beside the bowl."
- `bowl_stir`: "A white bowl filled with white flour sits on the right. A yellow spoon lies on
  the left. The hand picks up the spoon, stirs it round and round through the flour several
  times, then lays the spoon across the bowl."
- `book_push_aside`: "A large flat green book lies flat in the center. A small red block sits
  behind it. The hand pushes the green book across the table without ever lifting it, until
  it rests behind the red block, then leaves the frame."
- `bar_cut`: "A white dough bar and a gray knife lie side by side in the center. The hand
  picks up the knife, draws it straight across the middle of the bar cutting it into two
  pieces, then lays the knife down beside the halves."
- `lamp_press`: "An orange push light sits in the center of the table. The hand presses it
  straight down once with two fingertips, the light clicks on, and the hand leaves."

- [ ] **Step 4: Run the tests**

Run: `uv run pytest tests/test_samples.py -v`
Expected: PASS (all scene files, old and new).

- [ ] **Step 5: Commit**

```bash
git add samples/*.json scripts/chore_prompts.json tests/test_samples.py
git commit -m "Five new sample scenes: pour, stir, push, cut, press"
```

Generating the mp4s is a separate, paid, key-gated step the human runs when ready:
`uv run --group tools python scripts/generate_videos.py --only cup_pour` (same for the
other four). Do not run it from this plan.

---

### Task 19: README

**Files:**
- Modify: `README.md`

**Interfaces:**
- Consumes: everything above.

- [ ] **Step 1: Update the four sections**

1. **How it works** — the sentence "The steps compile into a symbolic task program" stays;
   no change needed unless it names the action count. It does not.
2. **Skills table** — add six rows after the existing four, same three columns:

```markdown
| `place_near` | put an object on the table beside another | pick, carry, set down at a clear spot next to the target (`relation`: next_to, left_of, right_of, in_front_of, behind) |
| `push` | slide something too big or flat to grasp | drive it with closed fingertips, never lifting; a push target can also be a container |
| `pour` | empty a cup into a container | hold the cup over the target, tip the wrist; contents are an abstract disc, not a fluid |
| `stir` | mix a container's contents with a spoon | swirl the tool in rings inside the rim until the world marks it mixed |
| `cut` | divide a box in two with a knife | one straight pass; the object is replaced by its two halves |
| `press` | push a button or push-light straight down | a firm downward press; the object latches |
```

3. Under the table, extend the honesty paragraph: wipes and tears are not visible to
   tracking, and neither are pours, stirs, cuts or presses — Muse Spark's reading is used
   for all of `SEMANTIC_ACTIONS`. Say that pour/stir contents are abstractions with no
   fluid physics, and that a push keeps an object's true size because it is never grasped.
4. **Sample clips** — add the five new names with one-line descriptions and mark them
   "scene file ready; footage generates on demand" (the mp4s are not generated yet).

- [ ] **Step 2: Verify nothing else drifts**

Run: `uv run pytest -q && cd web && pnpm test && cd .. && uv run ruff check . && uv run mypy src`
Expected: PASS.

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "README: the six new skills and their abstractions"
```

---

## Final verification

Run, in order, from the repo root:

```bash
uv run pytest -q          # the whole Python suite, offline
uv run ruff check .
uv run mypy src
cd web && pnpm test && pnpm typecheck && pnpm lint
```

All green = plan complete. `make check` runs the same set.

Manual, optional, human-triggered (needs `GEMINI_API_KEY` and budget, ~$0.10/s):
generate the five new clips, then `uv run showonce eval-demo` and
`uv run showonce eval-replay` to score them end to end.
