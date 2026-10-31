"""Run a symbolic task program on a concrete layout in the simulator."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

import numpy as np

from showonce.program import TaskProgram
from showonce.sim.controller import PandaController
from showonce.sim.scene import BLOCK_HALF, SimWorld, ZoneDef, block_def

SLOT_PITCH = 0.05  # spacing between blocks placed in the same container (4 cm blocks)
_SLOTS = ((-0.5, -0.5), (0.5, -0.5), (-0.5, 0.5), (0.5, 0.5), (0.0, 0.0))

XY = tuple[float, float]


@dataclass(frozen=True, slots=True)
class Region:
    """A container on the table, in table coordinates (meters)."""

    name: str
    center: XY
    size: XY


@dataclass(slots=True)
class Layout:
    """Where everything is on the table: block centers and container regions."""

    objects: dict[str, XY]
    regions: list[Region] = field(default_factory=list)


def build_world(layout: Layout) -> SimWorld:
    """Create a world with one block per object and one flat zone per region."""
    world = SimWorld(
        [block_def(name) for name in layout.objects],
        [ZoneDef(r.name, r.center, r.size) for r in layout.regions],
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
        belief = {n: np.array([x, y, BLOCK_HALF]) for n, (x, y) in perceived.items()}

    def where(name: str) -> np.ndarray:
        return belief[name].copy() if belief is not None else world.block_pos(name)

    for index, step in enumerate(program.steps):
        if step.object not in world.block_names:
            raise ExecutionError(f"Unknown object '{step.object}' in step: {step}")
        if belief is not None and step.object not in belief:
            raise ExecutionError(f"'{step.object}' was not found by perception")
        if step.action == "stack_on":
            if step.target not in world.block_names:
                raise ExecutionError(f"Unknown stack target '{step.target}' in step: {step}")
            below = where(step.target)
            target_xy: XY = (float(below[0]), float(below[1]))
            surface_z = float(below[2]) + BLOCK_HALF
        else:
            region = by_name.get(step.target)
            if region is None:
                raise ExecutionError(f"Unknown container '{step.target}' in step: {step}")
            sx, sy = _SLOTS[placed[step.target] % len(_SLOTS)]
            placed[step.target] += 1
            target_xy = (region.center[0] + sx * SLOT_PITCH, region.center[1] + sy * SLOT_PITCH)
            surface_z = 0.0
        controller.pick_place(
            step.object, target_xy, surface_z, pick_at=where(step.object) if belief else None
        )
        if belief is not None:
            belief[step.object] = np.array([target_xy[0], target_xy[1], surface_z + BLOCK_HALF])
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
        if step.action == "place_in":
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
            ok = xy < 0.02 and abs(dz - 2 * BLOCK_HALF) < 0.008
            checks.append(
                StepCheck(str(step), bool(ok), f"xy {xy * 1000:.0f} mm, dz {dz * 1000:.0f} mm")
            )
    return checks
