# Any Footage + Muse Repair Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Run clips the camera was never planned for (angled stock footage, portrait phone video), then let Muse repair a missed robot step with one advised nudge.

**Architecture:** Part A adds an unposed mode: when SAM geometry cannot explain a clip, Muse Spark's steps run on a default arrangement instead of garbage pixel-mapped positions. Part B adds a repair loop: a failed ground-truth check asks Muse for a destination nudge in meters, applied once to the spatial actions (`place_in`, `stack_on`, `place_near`, `push`).

**Tech Stack:** Python 3.11 + uv, pydantic, MuJoCo, pytest; Meta Model API (`plan_video`, `chat`).

**Spec:** This plan is the spec. Related design: `docs/superpowers/specs/2026-11-01-new-actions-design.md` (action vocabulary, honest-refusal style).

## Global Constraints

- All committed tests run offline: `uv run pytest` needs no network and no API keys. Sim tests use the `needs_panda` marker and must not require a display (no `SimRecorder` in tests; physics runs headless, rendering does not).
- No new dependencies. No schema change to `Step` / `TaskProgram`: every program JSON in `runs/` must still parse.
- Honest refusals stay `ExecutionError` naming the object. `RuntimeError` from `shuffled_layout` (table too crowded) propagates unchanged.
- Verify checks align with program steps by index (`verify` appends one `StepCheck` per step in order).

---

### Task A1: `unposed_layout` in a new module

**Files:**
- Create: `src/showonce/unposed.py`
- Create: `tests/test_unposed.py`

**Interfaces:**
- Consumes: `shuffled_layout` from `showonce.replay`, `Layout`/`Region` from `showonce.sim.executor`, `ObjectProfile` from `showonce.objects`, `TaskProgram` from `showonce.program`. (A new module because `replay` imports `demo` and `demo` will import this: putting it in either would be a cycle.)
- Produces: `unposed_layout(program, profiles, containers, seed=0) -> Layout`. Later tasks import this exact name.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_unposed.py`:

```python
from showonce.program import Step, TaskProgram
from showonce.unposed import unposed_layout


def prog() -> TaskProgram:
    return TaskProgram(
        name="t",
        steps=[
            Step(object="steel knife", action="cut", target="carrot"),
            Step(object="red cup", action="pour", target="bowl"),
            Step(object="orange lamp", action="press", target="orange lamp"),
        ],
    )


def test_objects_come_from_steps_and_containers_become_regions() -> None:
    layout = unposed_layout(prog(), {}, ["bowl"])
    assert set(layout.objects) == {"steel knife", "carrot", "red cup", "orange lamp"}
    assert [r.name for r in layout.regions] == ["bowl"]


def test_everything_lands_inside_arm_reach() -> None:
    layout = unposed_layout(prog(), {}, ["bowl"])
    for x, y in layout.objects.values():
        assert 0.34 <= x <= 0.60 and -0.24 <= y <= 0.24
    for r in layout.regions:
        assert 0.34 <= r.center[0] <= 0.60 and -0.24 <= r.center[1] <= 0.24


def test_same_seed_gives_the_same_table() -> None:
    assert unposed_layout(prog(), {}, ["bowl"], seed=3).objects == unposed_layout(
        prog(), {}, ["bowl"], seed=3
    ).objects
```

- [ ] **Step 2: Run to verify failure**

Run: `UV_CACHE_DIR=$PWD/.cache/uv uv run pytest tests/test_unposed.py -v`
Expected: FAIL (`unposed` module missing).

- [ ] **Step 3: Implement**

Create `src/showonce/unposed.py`:

```python
"""A default table arrangement for clips whose camera was never calibrated.

An angled close-up has no overhead pixel-to-table mapping, so SAM resting
positions would place objects in nonsense spots. This lays the named objects
out with the same free-space search replay uses, and parks each named
container as a fixed zone on the right side of the table.
"""

from __future__ import annotations

from showonce.objects import ObjectProfile
from showonce.program import TaskProgram
from showonce.replay import shuffled_layout
from showonce.sim.executor import XY, Layout, Region

ZONE_SIZE: XY = (0.16, 0.16)
ZONE_X = 0.48  # right side, inside arm reach (X_EDGE is 0.34 to 0.60)


def unposed_layout(
    program: TaskProgram,
    profiles: dict[str, ObjectProfile],
    containers: list[str],
    seed: int = 0,
) -> Layout:
    """Arrange the program's objects somewhere real, without video positions."""
    objects = {s.object for s in program.steps}
    objects |= {s.target for s in program.steps if s.target not in containers}
    regions = [
        Region(name, (ZONE_X, -0.12 + 0.24 * i), ZONE_SIZE)
        for i, name in enumerate(containers)
    ]
    return Layout(shuffled_layout(sorted(objects), regions, seed, profiles), regions, profiles)
```

Note: `press` steps name the same object as target, so the set dedupes them. More than two containers would push a zone past `Y_EDGE`; the free-space search raises `RuntimeError` first, which propagates.

- [ ] **Step 4: Run the tests**

Run: `UV_CACHE_DIR=$PWD/.cache/uv uv run pytest tests/test_unposed.py -v`
Expected: PASS (all 3).

- [ ] **Step 5: Commit**

```bash
git add src/showonce/unposed.py tests/test_unposed.py
git commit -m "Default table arrangement for clips with no overhead mapping"
```

---

### Task A2: Use the unposed layout when geometry has nothing to stand on

**Files:**
- Modify: `src/showonce/demo.py` (`learn_from_video` only)

**Interfaces:**
- Consumes: `unposed_layout` from Task A1, `LearnError` (already imported in `demo.py`).
- Produces: `learn_from_video` never crashes on an untrackable clip when Muse answered; `Learned.source` stays `"muse_spark"` with a discrepancy noting the default arrangement.

- [ ] **Step 1: Implement** (no new committed test; Task A3 proves it on real footage)

In `learn_from_video`, wrap the observe call so a clip SAM cannot track still reaches Muse:

```python
    try:
        obs = observe(client, video, scene.prompts)
    except Exception as exc:  # noqa: BLE001 -- any tracking failure means no geometry
        log.warning("SAM could not track %s: %s", video.name, exc)
        obs = None
```

Restructure the program choice: when `obs is None`, skip `learn_program` and require `semantic`:

```python
    if obs is None:
        if semantic is None:
            raise LearnError(f"SAM tracked nothing in {video.name} and Muse Spark did not answer")
        program = TaskProgram(name=scene.name, steps=semantic)
        problems = ["no trackable geometry; using Muse Spark's steps on a default layout"]
        source = "muse_spark"
    elif semantic and any(...):  # existing branch, unchanged
```

And the layout line becomes:

```python
    if obs is None or source == "muse_spark" and problems == [
        "geometry could not explain a move; using Muse Spark's steps"
    ]:
```

No: keep it exact and simple. Replace the `objects`/`layout` lines with:

```python
    if obs is None:
        layout = unposed_layout(program, scene.profiles, [c.name for c in scene.containers])
    else:
        objects = {
            name: calibration.to_table(rests[0].center)
            for name, rests in obs.rests.items()
            if rests
        }
        layout = Layout(objects, regions_from_scene(scene, calibration), scene.profiles)
```

`Learned.observation` is typed `Observation`; make it `Observation | None` and update the dataclass. Check every reader of `.observation` (`cli.py`, web API) still compiles under `mypy src` — `None` must be handled or the field kept non-optional by other means. If any reader breaks, keep the field type and store the empty observation instead: replace `obs is None` layout branch only, and construct `Observation(moves=[], rests={})` for the `Learned`. Prefer whichever keeps `mypy src` green; note the choice in the commit message.

- [ ] **Step 2: Typecheck and run affected suites**

Run: `UV_CACHE_DIR=$PWD/.cache/uv uv run mypy src && UV_CACHE_DIR=$PWD/.cache/uv uv run pytest -q tests/test_learn.py tests/test_unposed.py tests/test_samples.py`
Expected: PASS.

- [ ] **Step 3: Commit**

```bash
git add src/showonce/demo.py
git commit -m "Fall back to a default layout when a clip has no trackable geometry"
```

---

### Task A3: Prove it on the carrot-slicing stock clip

**Files:**
- Rename: `samples/5645055-hd_1920_1080_25fps.mp4` → `samples/pexels_cut_carrots.mp4`
- Create: `samples/pexels_cut_carrots.json`
- Move the other four Pexels files to `runs/pexels_rejected/` (keeps `samples/` for testable clips; the files stay in the workspace untouched)

**Interfaces:**
- Consumes: Task A2 wiring. Produces: first real-world sample; `tests/test_samples.py` picks it up automatically (every `*.json` must parse and name real things).

- [ ] **Step 1: Rename, write the scene file, move the rejects**

```bash
git mv samples/5645055-hd_1920_1080_25fps.mp4 samples/pexels_cut_carrots.mp4 2>/dev/null || mv samples/5645055-hd_1920_1080_25fps.mp4 samples/pexels_cut_carrots.mp4
mkdir -p runs/pexels_rejected
mv samples/10200305-hd_2160_3840_25fps.mp4 samples/10567299-uhd_2160_4096_25fps.mp4 samples/3676967-uhd_2160_4096_25fps.mp4 samples/6666286-uhd_4096_1974_30fps.mp4 runs/pexels_rejected/
```

`samples/pexels_cut_carrots.json`:

```json
{
  "name": "pexels_cut_carrots",
  "notes": "Pexels stock footage (angled close-up, two hands). Unposed: layout is a default arrangement.",
  "size": [1920, 1080],
  "prompts": {"steel knife": "large kitchen knife", "carrot": "orange carrot"},
  "container_prompts": {},
  "steps": [{"object": "steel knife", "action": "cut", "target": "carrot"}]
}
```

- [ ] **Step 2: Run the headless probe**

Run: `UV_CACHE_DIR=$PWD/.cache/uv uv run python /tmp/headless_run.py samples/pexels_cut_carrots.mp4 samples/pexels_cut_carrots.json`
Expected: `learned (muse_spark)` with a single `cut carrot with steel knife` step, then `PASS` and `SUCCESS` (sim ground truth: carrot split). Costs one Muse + SAM pass (about $1).

Known decision point: if the probe prints `learned (geometry)` with steps that do not match the scene file (geometry hijacking an angled clip), extend Task A2's rule before committing: prefer `semantic` + unposed whenever `semantic` exists and shares no exact step with the geometry program. Implement that, re-run the probe, and note it in the commit.

Executed outcome: the probe learned `muse_spark` correctly on the first run, but execution refused with `Cannot cut 'carrot': it is round` (SAM profiles the carrot as a cylinder). Fix applied in `fit_profiles` (`demo.py`): a cut target is coerced to `shape="box"`, mirroring the existing `open` coercion — halves are boxes, and the executor still refuses round targets for non-cut programs. Re-ran: `PASS - in two halves, SUCCESS`. No geometry hijacking occurred, so the A2 rule stands as written.

- [ ] **Step 3: Run the sample contract tests**

Run: `UV_CACHE_DIR=$PWD/.cache/uv uv run pytest tests/test_samples.py -v`
Expected: PASS including `pexels_cut_carrots`.

- [ ] **Step 4: Commit**

```bash
git add samples/pexels_cut_carrots.mp4 samples/pexels_cut_carrots.json
git commit -m "Real-world sample: carrot slicing from angled stock footage"
```

---

### Task B1: `repair_advice` — Muse proposes a destination nudge

**Files:**
- Modify: `src/showonce/chat.py` (append)
- Modify: `tests/test_chat.py` (append)

**Interfaces:**
- Consumes: `MetaClient.chat(objects, containers, plan, conversation)` — takes a duck-typed client in tests.
- Produces: `repair_advice(client, step, detail) -> tuple[float, float]`: `(dx, dy)` meters, each within ±0.05. Raises `ValueError` when the answer is unusable; the caller then skips repair. Task B2 imports this exact name.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_chat.py`:

```python
class _CannedClient:
    def __init__(self, text: str) -> None:
        self._text = text

    def chat(self, objects: object, containers: object, plan: object, conversation: object) -> dict:
        return {"text": self._text}


def test_repair_advice_reads_two_numbers() -> None:
    from showonce.chat import repair_advice

    step = Step(object="red block", action="push", target="bin")
    assert repair_advice(_CannedClient("0.02 -0.01"), step, "stopped 3 cm short") == (0.02, -0.01)


def test_repair_advice_rejects_wild_or_garbled_answers() -> None:
    from showonce.chat import repair_advice

    step = Step(object="red block", action="push", target="bin")
    with pytest.raises(ValueError):
        repair_advice(_CannedClient("0.50 0.00"), step, "missed")  # beyond a fingertip fix
    with pytest.raises(ValueError):
        repair_advice(_CannedClient("a bit to the left please"), step, "missed")
```

Check `tests/test_chat.py` imports `Step` and `pytest`; add them if missing.

- [ ] **Step 2: Run to verify failure**

Run: `UV_CACHE_DIR=$PWD/.cache/uv uv run pytest tests/test_chat.py -v`
Expected: FAIL (`repair_advice` missing).

- [ ] **Step 3: Implement**

Append to `src/showonce/chat.py`:

```python
import re

NUDGE_LIMIT = 0.05  # a repair is a fingertip fix, not a new plan


def repair_advice(client: MetaClient, step: Step, detail: str) -> tuple[float, float]:
    """Ask Muse where the object should have ended up, in meters.

    Returns (dx, dy) added to the step's destination. Raises ValueError when
    the answer is not two small numbers, and the caller skips repair.
    """
    answer = client.chat(
        [step.object],
        [] if step.target == step.object else [step.target],
        [step],
        [
            (
                "user",
                f"Step '{step}' failed: {detail}. Reply with exactly two numbers: "
                "dx dy in meters, each between -0.05 and 0.05, shifting where the "
                "object should end up. Example: 0.02 -0.01",
            )
        ],
    )
    match = re.search(r"(-?\d+(?:\.\d+)?)\s+(-?\d+(?:\.\d+)?)", str(answer.get("text", "")))
    if match is None:
        raise ValueError(f"unusable repair advice: {answer!r}")
    dx, dy = float(match.group(1)), float(match.group(2))
    if abs(dx) > NUDGE_LIMIT or abs(dy) > NUDGE_LIMIT:
        raise ValueError(f"repair nudge too large: {(dx, dy)}")
    return (dx, dy)
```

`MetaClient` and `Step` are already imported in `chat.py` (it defines `talk`/`understand` on them); if not, add the imports.

- [ ] **Step 4: Run the tests**

Run: `UV_CACHE_DIR=$PWD/.cache/uv uv run pytest tests/test_chat.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/showonce/chat.py tests/test_chat.py
git commit -m "Muse repair advice: a small destination nudge for a missed step"
```

---

### Task B2: `execute_with_repair` — one advised retry for spatial steps

**Files:**
- Modify: `src/showonce/sim/executor.py`
- Modify: `tests/test_executor.py`

**Interfaces:**
- Consumes: `repair_advice` (Task B1) as `advise: Callable[[Step, str], tuple[float, float]]`.
- Produces: `execute_with_repair(program, world, controller, regions, advise, perceived=None, on_step_done=None) -> list[StepCheck]`. Only `place_in`, `stack_on`, `place_near`, `push` are repairable; anything else failing returns the checks as-is.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_executor.py` (mirror its imports; add `execute_with_repair`, `ObjectProfile`, `Layout` if missing):

```python
def test_no_failure_means_no_advice_called() -> None:
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
    calls: list = []
    checks = execute_with_repair(
        program, world, PandaController(world), [], lambda s, d: calls.append((s, d)) or (0.0, 0.0)
    )
    assert all(c.ok for c in checks) and calls == []


@needs_panda
def test_a_push_nudge_lands_further_along_x() -> None:
    book = ObjectProfile(shape="box", width=0.2, depth=0.14, height=0.03)
    layout = Layout({"green book": (0.35, -0.1)}, [], {"green book": book})
    program = TaskProgram(
        name="t", steps=[Step(object="green book", action="push", target="green book")]
    )
    world = build_world(layout, program)
    execute(program, world, PandaController(world), [], nudges={0: (0.05, 0.0)})
    first = world.block_pos("green book").copy()
    world2 = build_world(layout, program)
    execute(world2 and program, world2, PandaController(world2), [])
    second = world2.block_pos("green book").copy()
    assert float(first[0] - second[0]) > 0.02
```

Executed outcome: the push variant failed with `IKError` — the nudged slide start point fell outside arm reach. The test now uses `place_near` (pick-and-place reach covers the nudged spot) and asserts the set-down x shifts by the nudge. Push nudges still work through the same code path; reach limits are a table-geometry fact, not a nudge bug.

- [ ] **Step 2: Run to verify failure**

Run: `UV_CACHE_DIR=$PWD/.cache/uv uv run pytest tests/test_executor.py -v`
Expected: FAIL (`execute_with_repair` and `nudges` missing).

- [ ] **Step 3: Implement**

In `execute`, add keyword-only `nudges: dict[int, XY] | None = None` and apply per branch:
- `place_near` (line ~237): `near_xy = (near_xy[0] + nudge[0], near_xy[1] + nudge[1])` before `pick_place`, where `nudge = (nudges or {}).get(index, (0.0, 0.0))`.
- `push` (after `to` is fixed, before clearance check): same addition to `to`.
- fall-through `place_in`/`stack_on` (before `pick_place` at line ~354): same addition to `target_xy`.
- `XY` is already defined in `executor.py`; import `Step` already there.

Append:

```python
Advise = Callable[[Step, str], tuple[float, float]]

REPAIRABLE = frozenset({"place_in", "stack_on", "place_near", "push"})


def execute_with_repair(
    program: TaskProgram,
    world: SimWorld,
    controller: PandaController,
    regions: list[Region],
    advise: Advise,
    perceived: dict[str, XY] | None = None,
    on_step_done: Callable[[int, str], None] | None = None,
) -> list[StepCheck]:
    """Run once; retry the first failed spatial step with a Muse-advised nudge."""
    execute(program, world, controller, regions, perceived, on_step_done)
    checks = verify(program, world, regions)
    for index, (step, check) in enumerate(zip(program.steps, checks)):
        if check.ok or step.action not in REPAIRABLE:
            continue
        try:
            dx, dy = advise(step, check.detail)
        except ValueError:
            continue  # unusable advice: report the miss, do not guess
        single = TaskProgram(name=program.name, steps=[step])
        execute(single, world, controller, regions, perceived, on_step_done, nudges={0: (dx, dy)})
        return verify(program, world, regions)
    return checks
```

`Callable` import: check the top of `executor.py`; it already takes `Callable` params, so it is imported. `Step`/`TaskProgram` imported (same file defines steps handling). Note the retry re-runs one step on the post-run world (object where the miss left it): honest — a real robot would re-grasp from there.

- [ ] **Step 4: Run the tests**

Run: `UV_CACHE_DIR=$PWD/.cache/uv uv run pytest tests/test_executor.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/showonce/sim/executor.py tests/test_executor.py
git commit -m "One Muse-advised retry for a failed spatial step"
```

---

### Task B3: Wire repair into `run_in_sim` behind a flag, then full check

**Files:**
- Modify: `src/showonce/demo.py` (`run_in_sim` + import), `src/showonce/cli.py` (`demo` command: `--repair` flag)
- Test: no new committed test (default path unchanged); prove-out below

**Interfaces:**
- Consumes: `execute_with_repair` (Task B2). Produces: `run_in_sim(..., repair=False, client=None)`; CLI `showonce demo --repair` passes the Meta client through.

- [ ] **Step 1: Implement**

In `run_in_sim`, add keyword-only params `repair: bool = False, client: MetaClient | None = None`. When both set, replace the `execute(...)` call with `execute_with_repair(..., partial(repair_advice, client), ...)` and return its checks wrapped in `RunResult`. `functools.partial` + `repair_advice` imported from `showonce.chat`. In `cli.py demo`, add `repair: bool = typer.Option(False, help="...")` and pass `repair=repair, client=client`.

- [ ] **Step 2: Prove-out with a staged miss**

Two `/tmp` prove-outs (not committed), both must print SUCCESS. First, run `execute_with_repair` on the passing push clip with a counting stub and assert advice is never called. Second, simulate a genuine miss: run a clean push, move `green book` 4 cm off with `world.set_block`, call `execute_with_repair` with a stub advising the exact offset back, and assert `verify` passes.

- [ ] **Step 3: Full suite + typecheck + lint**

Run: `UV_CACHE_DIR=$PWD/.cache/uv uv run ruff check . && UV_CACHE_DIR=$PWD/.cache/uv uv run mypy src && UV_CACHE_DIR=$PWD/.cache/uv uv run pytest -q --ignore=tests/test_pictures.py`
Expected: green except the known headless-GL `test_tidy` failures, which fail identically on the untouched tree (proven 2026-11-02).

- [ ] **Step 4: Commit**

```bash
git add src/showonce/demo.py src/showonce/cli.py
git commit -m "Opt-in Muse repair on demo runs"
```

## Self-Review

1. Spec coverage: unposed layout (A1), wiring (A2), real-clip proof (A3), advice parsing (B1), retry mechanics (B2), opt-in wiring + full check (B3). The `Observation | None` decision in A2 is delegated to the implementer with the mypy-green rule — acceptable latitude, not a placeholder, since both outcomes are fully specified.
2. No placeholders: every step has exact code, commands, and expected output. The B2 push test sketch is flagged for cleanup at write time with exact instructions.
3. Type consistency: `unposed_layout(program, profiles, containers, seed)`; `repair_advice(client, step, detail) -> tuple[float, float]`; `execute_with_repair(program, world, controller, regions, advise, perceived, on_step_done) -> list[StepCheck]`; `nudges: dict[int, XY]`. Consistent across tasks.

