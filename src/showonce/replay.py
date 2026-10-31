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
from showonce.sim.scene import SimWorld, block_def

XY = tuple[float, float]
# Where object centers may go, before keeping their footprint inside the top camera's view.
X_EDGE, Y_EDGE = (0.34, 0.60), (-0.24, 0.24)
MIN_SEPARATION = 0.09
SEPARATION_GAP = 0.01  # free space between two objects' footprints
REGION_GAP = 0.03  # free space between an object's footprint and a container


@dataclass(frozen=True, slots=True)
class ReplayResult:
    checks: list[StepCheck]
    perception_error_mm: dict[str, float]
    step_frames: list[int] = field(default_factory=list)  # recorded frame count after each step

    @property
    def success(self) -> bool:
        return all(c.ok for c in self.checks)


def _place_all(
    names: list[str], regions: list[Region], rng: random.Random, footprint: dict[str, float]
) -> dict[str, XY] | None:
    """One greedy attempt at a layout. None if some object has no free spot left."""
    placed: dict[str, XY] = {}
    for name in names:
        fp = footprint[name]
        for _ in range(200):
            candidate = (
                rng.uniform(X_EDGE[0] + fp, X_EDGE[1] - fp),
                rng.uniform(Y_EDGE[0] + fp, Y_EDGE[1] - fp),
            )
            clear_of_objects = all(
                math.dist(candidate, p)
                > max(MIN_SEPARATION, fp + footprint[other] + SEPARATION_GAP)
                for other, p in placed.items()
            )
            margin = fp + REGION_GAP
            clear_of_regions = all(
                abs(candidate[0] - r.center[0]) > r.size[0] / 2 + margin
                or abs(candidate[1] - r.center[1]) > r.size[1] / 2 + margin
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
    footprint = {name: block_def(name, profiles.get(name)).shape.footprint for name in names}
    for _ in range(50):
        placed = _place_all(names, regions, rng, footprint)
        if placed is not None:
            return placed
    raise RuntimeError("Could not find a free layout; the table is too crowded")


def replay(
    client: MetaClient | None,
    program: TaskProgram,
    scene: SceneSpec,
    seed: int,
    *,
    record_to: Path | None = None,
    oracle: bool = False,
    on_step_done: Callable[[int, str], None] | None = None,
) -> ReplayResult:
    """Shuffle the table, find the objects, and run the program.

    With ``oracle`` the robot reads true positions from the simulator instead of using SAM.
    """
    calibration = Calibration.for_frame(*(scene.size or (1280, 720)))
    regions = regions_from_scene(scene, calibration)
    truth = shuffled_layout(list(scene.prompts), regions, seed, scene.profiles)
    layout = Layout(truth, regions, scene.profiles)
    world: SimWorld = build_world(layout)
    recorder = SimRecorder(world) if record_to else None
    controller = PandaController(world, on_step=recorder.capture if recorder else None)
    controller.park()
    perceived = None
    errors: dict[str, float] = {}
    if not oracle:
        if client is None:
            raise ValueError("A Meta client is required unless oracle=True")
        perceived = perceive_blocks(client, world, scene.prompts_for_sim, calibration)
        errors = {n: math.dist(perceived[n], truth[n]) * 1000 for n in truth}
    controller.go_home()
    step_frames: list[int] = []

    def step_done(index: int, text: str) -> None:
        step_frames.append(len(recorder.frames) if recorder else 0)
        if on_step_done is not None:
            on_step_done(index, text)

    execute(program, world, controller, regions, perceived, step_done)
    if recorder and record_to:
        recorder.save(record_to)
    return ReplayResult(verify(program, world, regions), errors, step_frames)
