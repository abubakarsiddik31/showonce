"""Run a symbolic task program on a concrete layout in the simulator."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

import numpy as np

from showonce.objects import MAX_GRASP_WIDTH, ObjectProfile
from showonce.program import TaskProgram
from showonce.sim.controller import PandaController
from showonce.sim.scene import RIM_THICKNESS, TRAY_FLOOR, SimWorld, ZoneDef, block_def
from showonce.sim.skills import open_package, wipe

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


@dataclass(slots=True)
class Layout:
    """Where everything is on the table: object centers and container regions."""

    objects: dict[str, XY]
    regions: list[Region] = field(default_factory=list)
    profiles: dict[str, ObjectProfile] = field(default_factory=dict)  # name -> shape; else guessed


def dirty_surfaces(program: TaskProgram) -> set[str]:
    """Whatever the program wipes starts out dirty: that is the point of wiping it."""
    return {s.target for s in program.steps if s.action == "wipe"}


def build_world(layout: Layout, program: TaskProgram | None = None) -> SimWorld:
    """Create a world with one object per name and one tray per region."""
    world = SimWorld(
        [block_def(name, layout.profiles.get(name)) for name in layout.objects],
        [ZoneDef(r.name, r.center, r.size) for r in layout.regions],
        dirty=dirty_surfaces(program) if program else (),
    )
    for name, xy in layout.objects.items():
        world.set_block(name, xy)
    return world


class ExecutionError(RuntimeError):
    """Raised when a step cannot be carried out."""


def execute(
    program: TaskProgram,
    world: SimWorld,
    controller: PandaController,
    regions: list[Region],
    perceived: dict[str, XY] | None = None,
    on_step_done: Callable[[int, str], None] | None = None,
) -> None:
    """Carry out each step in order.

    If ``perceived`` (object centers from vision) is given, the robot acts on those beliefs and
    updates them with where it intends to leave each object. Otherwise it reads the
    simulator's ground truth.
    """
    by_name = {r.name: r for r in regions}
    placed: dict[str, int] = {r.name: 0 for r in regions}
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
        if world.shape(step.object).grasp_width > MAX_GRASP_WIDTH + 1e-6:
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
            wipe(world, controller, step.object, where(step.object), step.target, centre, half, top)
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
        controller.pick_place(
            step.object, target_xy, surface_z, pick_at=where(step.object) if belief else None
        )
        if belief is not None:
            belief[step.object] = np.array(
                [target_xy[0], target_xy[1], surface_z + world.half_height(step.object)]
            )
        if on_step_done is not None:
            on_step_done(index, str(step))


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
        elif step.action == "place_in":
            region = by_name[step.target]
            dx, dy = abs(pos[0] - region.center[0]), abs(pos[1] - region.center[1])
            ok = dx <= region.size[0] / 2 + 0.01 and dy <= region.size[1] / 2 + 0.01
            checks.append(
                StepCheck(str(step), bool(ok), f"offset ({dx * 1000:.0f}, {dy * 1000:.0f}) mm")
            )
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
