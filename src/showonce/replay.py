"""Replay a saved task program on a freshly shuffled layout, finding objects with SAM 3.1."""

from __future__ import annotations

import math
import random
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from showonce.demo import regions_from_scene
from showonce.geometry import Calibration
from showonce.meta.client import MetaClient
from showonce.objects import ObjectProfile
from showonce.program import TaskProgram
from showonce.scene_spec import SceneSpec
from showonce.sim.controller import PandaController
from showonce.sim.executor import Layout, Region, StepCheck, build_world, execute, verify
from showonce.sim.perceive import perceive_blocks
from showonce.sim.record import SimRecorder
from showonce.sim.scene import Shape, SimWorld, block_def
from showonce.verify import FixReport, fix_misses

XY = tuple[float, float]
# Where object centers may go, before keeping their footprint inside the top camera's view.
X_EDGE, Y_EDGE = (0.34, 0.60), (-0.24, 0.24)
MIN_SEPARATION = 0.09
HAND_CLEARANCE = 0.055  # hand body height above the fingertips
HAND_ROOM = 0.1  # free space a tall neighbour needs so the hand does not hit it
SEPARATION_GAP = 0.01  # free space between two objects' footprints
REGION_GAP = 0.03  # free space between an object's footprint and a container
HAND_WIDTH = 0.1  # how far the hand body reaches to each side of the gripper along y
HAND_THICKNESS = 0.03  # and along x
GRIP_ROOM = 0.02  # free space each side of an object along x, for the open fingers


@dataclass(frozen=True, slots=True)
class ReplayResult:
    checks: list[StepCheck]
    perception_error_mm: dict[str, float]
    step_frames: list[int] = field(default_factory=list)  # recorded frame count after each step
    fixes: FixReport | None = None  # what SAM saw at the end, and the one corrective try

    @property
    def success(self) -> bool:
        return all(c.ok for c in self.checks)


def _needs_hand_room(a: Shape, b: Shape) -> bool:
    """Does the wide hand, gripping one of these, reach up to the other's top?

    The hand body sits about 6 cm above the fingertips and is 20 cm wide, so something much
    taller than what is being gripped is in its way.
    """
    return any(
        tall.half_height * 2 > held.half_height + HAND_CLEARANCE for held, tall in ((a, b), (b, a))
    )


def _apart(a: Shape, pa: XY, b: Shape, pb: XY, tight: bool) -> bool:
    """Are two objects far enough apart for the robot to work on either?

    Normally each is treated as a circle of its footprint. In ``tight`` mode a long thin thing
    (a knife, a bar) counts as the box it is, so it can sit close beside another along its
    short side, with finger room along x.
    """
    if not tight:
        if _needs_hand_room(a, b):
            return math.dist(pa, pb) > a.footprint + b.footprint + HAND_ROOM
        return math.dist(pa, pb) > max(MIN_SEPARATION, a.footprint + b.footprint + SEPARATION_GAP)
    gap_x = abs(pa[0] - pb[0]) - (a.half[0] + b.half[0] + a.handle + b.handle)
    gap_y = abs(pa[1] - pb[1]) - (a.half[1] + b.half[1] + a.handle + b.handle)
    if _needs_hand_room(a, b):  # the hand is wide along y and thin along x
        return gap_x > HAND_THICKNESS + SEPARATION_GAP or gap_y > HAND_WIDTH + SEPARATION_GAP
    return gap_x > 2 * GRIP_ROOM + SEPARATION_GAP or gap_y > SEPARATION_GAP + 2 * GRIP_ROOM


def _place_all(
    names: list[str],
    regions: list[Region],
    rng: random.Random,
    shapes: dict[str, Shape],
    tight: bool = False,
) -> dict[str, XY] | None:
    """One greedy attempt at a layout. None if some object has no free spot left."""
    placed: dict[str, XY] = {}
    for name in names:
        shape = shapes[name]
        fp = shape.footprint
        reach_x, reach_y = (
            (shape.half[0] + shape.handle, shape.half[1] + shape.handle) if tight else (fp, fp)
        )
        for _ in range(200):
            candidate = (
                rng.uniform(X_EDGE[0] + reach_x, X_EDGE[1] - reach_x),
                rng.uniform(Y_EDGE[0] + reach_y, Y_EDGE[1] - reach_y),
            )
            clear_of_objects = all(
                _apart(shapes[name], candidate, shapes[other], p, tight)
                for other, p in placed.items()
            )
            clear_of_regions = all(
                abs(candidate[0] - r.center[0]) > r.size[0] / 2 + reach_x + REGION_GAP
                or abs(candidate[1] - r.center[1]) > r.size[1] / 2 + reach_y + REGION_GAP
                for r in regions
            )
            if clear_of_objects and clear_of_regions:
                placed[name] = candidate
                break
        else:
            return None
    return placed


def shuffled_layout(
    names: list[str],
    regions: list[Region],
    seed: int,
    profiles: dict[str, ObjectProfile] | None = None,
) -> dict[str, XY]:
    """Random object positions that do not overlap each other or any container."""
    rng = random.Random(seed)
    profiles = profiles or {}
    shapes = {name: block_def(name, profiles.get(name)).shape for name in names}
    for tight, tries in ((False, 50), (True, 1000)):  # roomy first: old layouts stay the same
        for _ in range(tries):
            placed = _place_all(names, regions, rng, shapes, tight)
            if placed is not None:
                return placed
    raise RuntimeError("Could not find a free layout; the table is too crowded")


def slip_spot(world: SimWorld, regions: list[Region], name: str, seed: int) -> XY:
    """A free spot on open table to drop ``name``, as if it had slipped from the gripper."""
    others = [n for n in world.block_names if n != name]
    shapes = {n: world.shape(n) for n in [name, *others]}
    rng = random.Random(seed)
    fp = shapes[name].footprint
    for _ in range(500):
        candidate = (
            rng.uniform(X_EDGE[0] + fp, X_EDGE[1] - fp),
            rng.uniform(Y_EDGE[0] + fp, Y_EDGE[1] - fp),
        )
        clear_of_objects = all(
            math.dist(candidate, (float(p[0]), float(p[1]))) > fp + shapes[n].footprint + 0.03
            for n in others
            for p in [world.block_pos(n)]
            if p[2] > 0
        )
        clear_of_regions = all(
            abs(candidate[0] - r.center[0]) > r.size[0] / 2 + fp + REGION_GAP
            or abs(candidate[1] - r.center[1]) > r.size[1] / 2 + fp + REGION_GAP
            for r in regions
        )
        if clear_of_objects and clear_of_regions:
            return candidate
    raise RuntimeError("No free spot to drop the object")


def replay(
    client: MetaClient | None,
    program: TaskProgram,
    scene: SceneSpec,
    seed: int,
    *,
    record_to: Path | None = None,
    oracle: bool = False,
    on_step_done: Callable[[int, str], None] | None = None,
    sam_verify: bool = False,
    slip: str | None = None,
) -> ReplayResult:
    """Shuffle the table, find the objects, and run the program.

    With ``oracle`` the robot reads true positions from the simulator instead of using SAM.
    With ``sam_verify`` it finally parks the arm, looks at the table with SAM and runs once more
    any step that picture shows as missed. ``slip`` names an object to drop on open table after
    the run, to stage a miss for it to catch.
    """
    calibration = Calibration.for_frame(*(scene.size or (1280, 720)))
    regions = regions_from_scene(scene, calibration)
    truth = shuffled_layout(list(scene.prompts), regions, seed, scene.profiles)
    layout = Layout(truth, regions, scene.profiles)
    world: SimWorld = build_world(layout, program)
    recorder = SimRecorder(world) if record_to else None
    try:
        controller = PandaController(world)
        controller.park()  # out of the top camera's view; none of this is recorded
        perceived = None
        errors: dict[str, float] = {}
        if not oracle:
            if client is None:
                raise ValueError("A Meta client is required unless oracle=True")
            perceived = perceive_blocks(client, world, scene.sim_prompt_options)
            errors = {n: math.dist(perceived[n], truth[n]) * 1000 for n in truth}
        controller.reset_to_home()  # the video opens on the arm ready, not swinging in
        if recorder:
            controller.on_step = recorder.capture
            recorder.capture()
        step_frames: list[int] = []

        def step_done(index: int, text: str) -> None:
            step_frames.append(len(recorder.frames) if recorder else 0)
            if on_step_done is not None:
                on_step_done(index, text)

        execute(program, world, controller, regions, perceived, step_done)
        if slip is not None:
            world.set_block(slip, slip_spot(world, regions, slip, seed))
            if recorder:
                recorder.capture()
        fixes: FixReport | None = None
        if sam_verify:
            if client is None:
                raise ValueError("A Meta client is required for sam_verify")
            sam_client = client

            def look(names: list[str]) -> dict[str, XY]:
                return perceive_blocks(
                    sam_client,
                    world,
                    {n: scene.sim_prompt_options[n] for n in names},
                )

            fixes = fix_misses(
                program, world, controller, regions, look, list(truth), on_step_done=None
            )
        if recorder and record_to:
            controller.park()  # step away, so the finished table can be seen
            controller.dwell(150)
            recorder.save(record_to)
        return ReplayResult(verify(program, world, regions), errors, step_frames, fixes)
    finally:
        if recorder:
            recorder.close()
