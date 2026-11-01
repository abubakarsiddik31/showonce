"""Check the finished table with SAM, not the simulator, and fix what is off.

The simulator can say where everything really is, but a judge can fairly call that circular.
Here the robot parks its arm, looks at the table with SAM 3.1 like any camera would, compares
what it sees with each step's goal, and runs the steps that missed once more from what it
saw. Steps that a picture cannot show (a stir, a cut, a press) still use simulator state.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass

from showonce.geometry import RELATION_UNIT
from showonce.program import Step, TaskProgram
from showonce.sim.controller import PandaController
from showonce.sim.executor import (
    ExecutionError,
    Region,
    StepCheck,
    execute,
    first_free_slot,
    verify,
)
from showonce.sim.perceive import NotFoundError
from showonce.sim.scene import SimWorld

XY = tuple[float, float]
Perceiver = Callable[[list[str]], dict[str, XY]]

# What a top-down picture can show: where things ended up. The rest is simulator state.
SEEN_ACTIONS: frozenset[str] = frozenset({"place_in", "stack_on", "place_near", "push"})
CONTAINER_SLACK = 0.01
NEIGHBOUR_SLACK = {"place_near": 0.04, "push": 0.05}
STACK_SLACK = 0.02


@dataclass(frozen=True, slots=True)
class FixReport:
    """What SAM saw before and after the robot's one corrective try."""

    before: list[StepCheck]
    after: list[StepCheck]
    retried: list[str]  # the steps that were run again
    error: str | None = None  # why the retry could not run, if it could not

    @property
    def missed(self) -> bool:
        return any(not c.ok for c in self.before)

    @property
    def fixed(self) -> bool:
        return self.missed and all(c.ok for c in self.after)


def _look(perceive: Perceiver, names: list[str]) -> dict[str, XY]:
    """SAM positions for ``names``; an object SAM cannot find is left out, not fatal."""
    try:
        return perceive(names)
    except NotFoundError:
        seen: dict[str, XY] = {}
        for name in names:
            try:
                seen.update(perceive([name]))
            except NotFoundError:
                continue
        return seen


def _judge(
    step: Step, seen: dict[str, XY], by_name: dict[str, Region], world: SimWorld
) -> StepCheck | None:
    """Does the picture show the step's goal reached? None when the picture cannot say."""
    if step.action not in SEEN_ACTIONS or step.object not in seen:
        return None
    x, y = seen[step.object]
    if step.action in ("place_in", "push") and step.target in by_name:
        region = by_name[step.target]
        dx, dy = abs(x - region.center[0]), abs(y - region.center[1])
        ok = (
            dx <= region.size[0] / 2 + CONTAINER_SLACK
            and dy <= region.size[1] / 2 + CONTAINER_SLACK
        )
        return StepCheck(str(step), ok, f"SAM: offset ({dx * 1000:.0f}, {dy * 1000:.0f}) mm")
    if step.target not in seen:
        return None
    dx, dy = x - seen[step.target][0], y - seen[step.target][1]
    if step.action == "stack_on":
        ok = math.hypot(dx, dy) < STACK_SLACK
    else:
        band = (
            world.shape(step.object).radius
            + world.shape(step.target).radius
            + NEIGHBOUR_SLACK[step.action]
        )
        ok = math.hypot(dx, dy) <= band
        if ok and step.relation and step.relation != "next_to":
            ux, uy = RELATION_UNIT[step.relation]
            ok = dx * ux + dy * uy > 0  # on the side the relation names
    return StepCheck(str(step), ok, f"SAM: offset ({dx * 1000:.0f}, {dy * 1000:.0f}) mm")


def covered_objects(program: TaskProgram) -> set[str]:
    """Objects something gets stacked on: the camera looks down and cannot see them."""
    return {s.target for s in program.steps if s.action == "stack_on"}


def verify_with_sam(
    program: TaskProgram,
    world: SimWorld,
    regions: list[Region],
    perceive: Perceiver,
    reference: Mapping[str, XY] | None = None,
) -> tuple[list[StepCheck], dict[str, XY]]:
    """One check per step, judged from what SAM sees; simulator state for what it cannot show.

    A covered object cannot be seen, so a step that needs one is judged against where it was
    first seen (``reference``) if nothing has moved it since, and from simulator state if not.
    """
    by_name = {r.name: r for r in regions}
    hidden = covered_objects(program)
    wanted = sorted(
        {
            name
            for step in program.steps
            if step.action in SEEN_ACTIONS
            for name in (step.object, step.target)
            if name in world.block_names and name not in hidden
        }
    )
    seen = _look(perceive, wanted) if wanted else {}
    truth = verify(program, world, regions)
    checks: list[StepCheck] = []
    moved: set[str] = set()
    for step, fallback in zip(program.steps, truth, strict=True):
        anchors = dict(seen)
        for name in hidden - moved:
            if reference is not None and name in reference:
                anchors[name] = reference[name]
        judged = _judge(step, anchors, by_name, world) if step.object not in hidden else None
        checks.append(judged or StepCheck(fallback.step, fallback.ok, f"sim: {fallback.detail}"))
        moved.add(step.object)
    return checks, seen


def _slots_used(
    failed: Sequence[Step],
    seen: dict[str, XY],
    regions: list[Region],
    world: SimWorld,
) -> dict[str, int]:
    """Where to start filling each container the repair run puts things into."""
    redo = {step.object for step in failed}
    start: dict[str, int] = {}
    for step in failed:
        region = next((r for r in regions if r.name == step.target), None)
        if region is None or region.name in start:
            continue
        inside = [
            p
            for name, p in seen.items()
            if name not in redo
            and abs(p[0] - region.center[0]) <= region.size[0] / 2
            and abs(p[1] - region.center[1]) <= region.size[1] / 2
        ]
        start[region.name] = first_free_slot(region, world.shape(step.object).radius, inside)
    return start


def fix_misses(
    program: TaskProgram,
    world: SimWorld,
    controller: PandaController,
    regions: list[Region],
    perceive: Perceiver,
    names: Sequence[str],
    reference: Mapping[str, XY] | None = None,
    *,
    on_step_done: Callable[[int, str], None] | None = None,
) -> FixReport:
    """Look at the table with SAM; run the steps it shows as missed once more from that view."""
    controller.park()
    before, _ = verify_with_sam(program, world, regions, perceive, reference)
    failed = [s for s, c in zip(program.steps, before, strict=True) if not c.ok]
    if not failed or any(s.action not in SEEN_ACTIONS for s in failed):
        # Nothing to redo, or a miss a picture cannot explain: report it, do not guess.
        return FixReport(before, before, [])
    beliefs = {
        n: (float(world.block_pos(n)[0]), float(world.block_pos(n)[1])) for n in world.block_names
    }
    hidden = covered_objects(program)
    beliefs.update(
        _look(perceive, [n for n in names if n in world.block_names and n not in hidden])
    )
    beliefs.update({n: p for n, p in (reference or {}).items() if n in hidden})
    controller.reset_to_home()
    try:
        execute(
            TaskProgram(name=f"{program.name} (retry)", steps=failed),
            world,
            controller,
            regions,
            beliefs,
            on_step_done,
            _slots_used(failed, beliefs, regions, world),
        )
    except ExecutionError as exc:
        controller.park()
        return FixReport(before, before, [str(s) for s in failed], error=str(exc))
    controller.park()
    after, _ = verify_with_sam(program, world, regions, perceive, reference)
    return FixReport(before, after, [str(s) for s in failed])
