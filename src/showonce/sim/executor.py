"""Run a symbolic task program on a concrete layout in the simulator."""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass, field

import numpy as np

from showonce.geometry import RELATION_UNIT
from showonce.objects import MAX_GRASP_WIDTH, ObjectProfile
from showonce.program import Step, TaskProgram
from showonce.sim.controller import PandaController
from showonce.sim.scene import RIM_THICKNESS, TRAY_FLOOR, SimWorld, ZoneDef, block_def
from showonce.sim.skills import cut, free_spot, open_package, pour, press, stir, wipe

SLOT_MARGIN = 0.004  # clearance between a placed object and the rim
# Where objects go in a container, as fractions of the free half-width: corners, then center.
_SLOTS = ((-1.0, -1.0), (1.0, -1.0), (-1.0, 1.0), (1.0, 1.0), (0.0, 0.0))

XY = tuple[float, float]


@dataclass(frozen=True, slots=True)
class Region:
    """A container on the table, in table coordinates (meters)."""

    name: str
    center: XY
    size: XY


def slot_xy(region: Region, index: int, radius: float) -> XY:
    """Where the ``index``-th object of ``radius`` rests inside ``region``, clear of the rim."""
    sx, sy = _SLOTS[index % len(_SLOTS)]
    reach_x = max(0.0, region.size[0] / 2 - RIM_THICKNESS - SLOT_MARGIN - radius)
    reach_y = max(0.0, region.size[1] / 2 - RIM_THICKNESS - SLOT_MARGIN - radius)
    return (region.center[0] + sx * reach_x, region.center[1] + sy * reach_y)


def first_free_slot(region: Region, radius: float, occupied: list[XY]) -> int:
    """The first slot in ``region`` that no object in ``occupied`` is already resting on."""
    for index in range(len(_SLOTS)):
        slot = slot_xy(region, index, radius)
        if all(math.dist(slot, other) > radius * 1.5 for other in occupied):
            return index
    return 0


@dataclass(slots=True)
class Layout:
    """Where everything is on the table: object centers and container regions."""

    objects: dict[str, XY]
    regions: list[Region] = field(default_factory=list)
    profiles: dict[str, ObjectProfile] = field(default_factory=dict)  # name -> shape; else guessed


def dirty_surfaces(program: TaskProgram) -> set[str]:
    """Whatever the program wipes starts out dirty: that is the point of wiping it."""
    return {s.target for s in program.steps if s.action == "wipe"}


def contents_for(program: TaskProgram) -> tuple[set[str], set[str]]:
    """(what starts holding contents, what starts empty but will be poured into).

    Like ``dirty_surfaces``: the program itself says what the world must start with, so a
    pour source starts full and a stirred bowl starts unmixed-but-full.
    """
    full = {s.object for s in program.steps if s.action == "pour"}
    full |= {s.target for s in program.steps if s.action == "stir"}
    targets = {s.target for s in program.steps if s.action == "pour"}
    return full, targets


def _half_profiles(layout: Layout, program: TaskProgram | None) -> dict[str, ObjectProfile]:
    """A half-profile for every box the program cuts: half the width, everything else the same."""
    halves: dict[str, ObjectProfile] = {}
    if not program:
        return halves
    for step in program.steps:
        if step.action != "cut" or f"{step.target} half a" in halves:
            continue
        parent = layout.profiles.get(step.target)
        if parent is None:
            continue
        for suffix in ("a", "b"):
            halves[f"{step.target} half {suffix}"] = parent.model_copy(
                update={"width": parent.width / 2}
            )
    return halves


def build_world(layout: Layout, program: TaskProgram | None = None) -> SimWorld:
    """Create a world with one object per name and one tray per region."""
    full, pour_targets = contents_for(program) if program else (set(), set())
    blocks = [block_def(name, layout.profiles.get(name)) for name in layout.objects] + [
        block_def(name, profile) for name, profile in _half_profiles(layout, program).items()
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
    return world


def _segment_clearance(start: XY, to: XY, point: XY) -> float:
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


class ExecutionError(RuntimeError):
    """Raised when a step cannot be carried out."""


def execute(
    program: TaskProgram,
    world: SimWorld,
    controller: PandaController,
    regions: list[Region],
    perceived: dict[str, XY] | None = None,
    on_step_done: Callable[[int, str], None] | None = None,
    slots_used: dict[str, int] | None = None,
    nudges: dict[int, XY] | None = None,
) -> None:
    """Carry out each step in order.

    If ``perceived`` (object centers from vision) is given, the robot acts on those beliefs and
    updates them with where it intends to leave each object. Otherwise it reads the
    simulator's ground truth. ``slots_used`` says which slot of a container to start filling
    from, for a repair run into a container that already holds things. ``nudges`` shifts a
    step's destination by (dx, dy) meters, for one advised retry of a miss.
    """
    by_name = {r.name: r for r in regions}
    placed: dict[str, int] = {r.name: (slots_used or {}).get(r.name, 0) for r in regions}
    belief: dict[str, np.ndarray] | None = None
    if perceived is not None:
        belief = {n: np.array([x, y, world.half_height(n)]) for n, (x, y) in perceived.items()}

    def where(name: str) -> np.ndarray:
        return belief[name].copy() if belief is not None else world.block_pos(name)

    for index, step in enumerate(program.steps):
        if step.object not in world.block_names:
            raise ExecutionError(f"Unknown object '{step.object}' in step: {step}")
        if belief is not None and step.object not in belief:
            raise ExecutionError(f"'{step.object}' was not found by perception")
        if step.action == "open":
            if not world.shape(step.object).openable:
                raise ExecutionError(f"'{step.object}' is not something that can be opened")
            others = [
                (tuple(where(n)[:2]), world.shape(n).footprint)
                for n in world.block_names
                if n != step.object
            ]
            keep_out = [(r.center, (r.size[0] + 0.1, r.size[1] + 0.1)) for r in regions]
            bag = where(step.object)
            open_package(
                world, controller, step.object, (float(bag[0]), float(bag[1])), others, keep_out
            )
            if on_step_done is not None:
                on_step_done(index, str(step))
            continue
        if step.action == "press":
            if not world.shape(step.object).pressable:
                raise ExecutionError(f"'{step.object}' has no button to press")
            press(world, controller, step.object, where(step.object))
            if on_step_done is not None:
                on_step_done(index, str(step))
            continue
        if step.action in ("place_in", "place_near", "pour", "stir", "cut") and (
            world.shape(step.object).grasp_width > MAX_GRASP_WIDTH + 1e-6
        ):
            raise ExecutionError(f"'{step.object}' is too wide for the gripper")
        if step.action == "wipe":
            if step.target in world.block_names:
                below = where(step.target)
                centre, (ex, ey, ez) = (
                    (float(below[0]), float(below[1])),
                    world.shape(step.target).half,
                )
                half, top = (ex, ey), float(below[2]) + ez
            elif step.target in by_name:
                surface = by_name[step.target]
                centre = surface.center
                half = (surface.size[0] / 2 - RIM_THICKNESS, surface.size[1] / 2 - RIM_THICKNESS)
                top = TRAY_FLOOR
            else:
                raise ExecutionError(f"Unknown surface '{step.target}' in step: {step}")
            round_surface = (
                step.target in world.block_names and world.shape(step.target).kind != "box"
            )
            wipe(
                world,
                controller,
                step.object,
                where(step.object),
                step.target,
                centre,
                half,
                top,
                round_surface=round_surface,
            )
            if on_step_done is not None:
                on_step_done(index, str(step))
            continue
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
                near_xy = free_spot(
                    (float(neighbour[0]), float(neighbour[1])), (hx, hy), others, keep_out, unit
                )
            except ValueError as exc:
                raise ExecutionError(f"No free spot for '{step.object}': {exc}") from exc
            nudge = (nudges or {}).get(index, (0.0, 0.0))
            near_xy = (near_xy[0] + nudge[0], near_xy[1] + nudge[1])
            controller.pick_place(
                step.object, near_xy, 0.0, pick_at=where(step.object) if belief else None
            )
            if belief is not None:
                belief[step.object] = np.array(
                    [near_xy[0], near_xy[1], world.half_height(step.object)]
                )
            if on_step_done is not None:
                on_step_done(index, str(step))
            continue
        if step.action == "push":
            if step.target in by_name:
                container = by_name[step.target]
                to = slot_xy(container, placed[step.target], world.shape(step.object).radius)
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
            nudge = (nudges or {}).get(index, (0.0, 0.0))
            to = (to[0] + nudge[0], to[1] + nudge[1])
            src = (float(where(step.object)[0]), float(where(step.object)[1]))
            for n in world.block_names:
                if n in (step.object, step.target):
                    continue
                p = where(n)
                gap = _segment_clearance(src, to, (float(p[0]), float(p[1]))) - (
                    world.shape(step.object).radius + world.shape(n).radius
                )
                if gap < 0.01:
                    raise ExecutionError(f"Cannot push '{step.object}': '{n}' blocked the path")
            if step.target in by_name and math.dist(src, to) > 0.05:
                # A single long slide tips the object over the container rim and
                # flings it past the bin; staging most of the way first, then
                # re-approaching for the final push, lands it inside instead.
                mid = (src[0] + (to[0] - src[0]) * 0.7, src[1] + (to[1] - src[1]) * 0.7)
                controller.slide(step.object, mid)
            controller.slide(step.object, to)
            if belief is not None:
                belief[step.object] = np.array([to[0], to[1], world.half_height(step.object)])
            if on_step_done is not None:
                on_step_done(index, str(step))
            continue
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
        if step.action == "stack_on":
            if step.target not in world.block_names:
                raise ExecutionError(f"Unknown stack target '{step.target}' in step: {step}")
            if world.shape(step.target).kind == "sphere":
                raise ExecutionError(f"Cannot stack on '{step.target}': it is round")
            below = where(step.target)
            target_xy: XY = (float(below[0]), float(below[1]))
            surface_z = float(below[2]) + world.half_height(step.target)
        else:
            region = by_name.get(step.target)
            if region is None:
                raise ExecutionError(f"Unknown container '{step.target}' in step: {step}")
            target_xy = slot_xy(region, placed[step.target], world.shape(step.object).radius)
            placed[step.target] += 1
            surface_z = TRAY_FLOOR
        nudge = (nudges or {}).get(index, (0.0, 0.0))
        target_xy = (target_xy[0] + nudge[0], target_xy[1] + nudge[1])
        controller.pick_place(
            step.object, target_xy, surface_z, pick_at=where(step.object) if belief else None
        )
        if belief is not None:
            belief[step.object] = np.array(
                [target_xy[0], target_xy[1], surface_z + world.half_height(step.object)]
            )
        if on_step_done is not None:
            on_step_done(index, str(step))


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
    """Run once; retry the first failed spatial step with an advised nudge."""
    execute(program, world, controller, regions, perceived, on_step_done)
    checks = verify(program, world, regions)
    for step, check in zip(program.steps, checks, strict=True):
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


@dataclass(frozen=True, slots=True)
class StepCheck:
    step: str
    ok: bool
    detail: str


def verify(program: TaskProgram, world: SimWorld, regions: list[Region]) -> list[StepCheck]:
    """Check the final sim state against each step, using simulator ground truth."""
    by_name = {r.name: r for r in regions}
    checks: list[StepCheck] = []
    for step in program.steps:
        pos = world.block_pos(step.object)
        if step.action == "open":
            ok = world.is_open(step.object)
            checks.append(StepCheck(str(step), ok, "seal torn off" if ok else "seal still on"))
        elif step.action == "wipe":
            left, total = world.dirt_left(step.target)
            ok = total > 0 and left <= 0.05 * total
            checks.append(StepCheck(str(step), ok, f"{total - left} of {total} stains wiped"))
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
        elif step.action == "pour":
            ok = (
                world.contents_of(step.target) is not None
                and world.contents_of(step.object) is None
            )
            checks.append(
                StepCheck(str(step), bool(ok), f"{step.target} holds the poured contents")
            )
        elif step.action == "stir":
            ok = world.is_mixed(step.target)
            checks.append(StepCheck(str(step), bool(ok), "mixed" if ok else "not mixed"))
        elif step.action == "cut":
            ok = world.is_split(step.target)
            checks.append(StepCheck(str(step), bool(ok), "in two halves" if ok else "still whole"))
        elif step.action == "press":
            ok = world.is_pressed(step.object)
            checks.append(StepCheck(str(step), bool(ok), "pressed" if ok else "unpressed"))
        else:
            below = world.block_pos(step.target)
            xy = float(((pos[0] - below[0]) ** 2 + (pos[1] - below[1]) ** 2) ** 0.5)
            dz = float(pos[2] - below[2])
            stacked = world.half_height(step.object) + world.half_height(step.target)
            ok = xy < 0.02 and abs(dz - stacked) < 0.008
            checks.append(
                StepCheck(str(step), bool(ok), f"xy {xy * 1000:.0f} mm, dz {dz * 1000:.0f} mm")
            )
    return checks
