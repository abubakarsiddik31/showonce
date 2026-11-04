"""Tidy mode: no demo. Look at a messy table, ask Muse Spark how to organise it, and do it.

The same pieces as replay, in a different order: SAM 3.1 finds every object on the table, Muse
Spark plans the tidy-up in the same ten-verb language a learned demo compiles to, the arm
carries it out, and SAM checks the result and corrects a miss once.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Collection
from dataclasses import dataclass, field
from pathlib import Path

import cv2
import numpy as np

from showonce.demo import regions_from_scene
from showonce.geometry import Calibration
from showonce.meta.client import MetaClient
from showonce.meta.muse import TIDY_ACTIONS
from showonce.perception.profiles import encode_png
from showonce.program import Step, TaskProgram
from showonce.replay import shuffled_layout, slip_spot
from showonce.scene_spec import SceneSpec
from showonce.sim.controller import PandaController
from showonce.sim.executor import Layout, StepCheck, build_world, execute, verify
from showonce.sim.perceive import perceive_blocks
from showonce.sim.record import SimRecorder, top_view
from showonce.sim.scene import SimWorld
from showonce.verify import FixReport, fix_misses

XY = tuple[float, float]
DEFAULT_GOAL = "Put everything away and leave the table tidy."
Planner = Callable[[bytes, str, dict[str, XY], list[str]], list[Step]]


class TidyError(RuntimeError):
    """Raised when there is nothing sensible to do."""


@dataclass(frozen=True, slots=True)
class TidyResult:
    program: TaskProgram
    checks: list[StepCheck]
    dropped: list[str] = field(default_factory=list)  # planned steps the robot cannot do
    perception_error_mm: dict[str, float] = field(default_factory=dict)
    step_frames: list[int] = field(default_factory=list)
    fixes: FixReport | None = None

    @property
    def success(self) -> bool:
        return bool(self.checks) and all(c.ok for c in self.checks)


def clean_plan(
    steps: list[Step],
    objects: Collection[str],
    containers: Collection[str],
    round_objects: Collection[str] = (),
) -> tuple[list[Step], list[str]]:
    """Keep the steps the robot can carry out; say why each of the others was dropped.

    The model sees a picture and may plan something the hands cannot do: move a thing twice,
    move what has something stacked on it, or stack on a ball. Those are dropped here, before
    anything moves.
    """
    kept: list[Step] = []
    dropped: list[str] = []
    moved: set[str] = set()
    covered: set[str] = set()  # objects something has been stacked on

    for step in steps:
        why: str | None = None
        if step.action not in TIDY_ACTIONS:
            why = "not a tidy-up action"
        elif step.object not in objects:
            why = f"no object called {step.object}"
        elif step.object in moved:
            why = f"{step.object} already moved"
        elif step.object in covered:
            why = f"{step.object} has something stacked on it"
        elif step.object == step.target:
            why = "an object cannot go onto itself"
        elif step.action == "place_in" and step.target not in containers:
            why = f"{step.target} is not a container"
        elif step.action in ("stack_on", "place_near") and step.target not in objects:
            why = f"{step.target} is not an object"
        elif step.action == "stack_on" and step.target in round_objects:
            why = f"{step.target} is round"
        elif step.action == "push" and step.target not in {*objects, *containers}:
            why = f"nowhere called {step.target}"
        if why is not None:
            dropped.append(f"{step}: {why}")
            continue
        kept.append(step)
        moved.add(step.object)
        if step.action == "stack_on":
            covered.add(step.target)
    return kept, dropped


def run_tidy(
    client: MetaClient,
    scene: SceneSpec,
    seed: int,
    *,
    goal: str = DEFAULT_GOAL,
    record_to: Path | None = None,
    oracle: bool = False,
    sam_verify: bool = True,
    slip: str | None = None,
    planner: Planner | None = None,
    on_step_done: Callable[[int, str], None] | None = None,
) -> TidyResult:
    """Scatter the scene's objects, look, plan the tidy-up, do it, and check it with SAM.

    ``oracle`` reads positions from the simulator rather than SAM. ``slip`` drops one object
    on open table after the run, to stage a miss for verification to catch.
    """
    calibration = Calibration.for_frame(*(scene.size or (1280, 720)))
    regions = regions_from_scene(scene, calibration)
    names = list(scene.prompts)
    truth = shuffled_layout(names, regions, seed, scene.profiles)
    empty = TaskProgram(name=f"tidy {scene.name}")
    world: SimWorld = build_world(Layout(truth, regions, scene.profiles), empty)
    recorder = SimRecorder(world) if record_to else None
    controller = PandaController(world)
    controller.park()

    perceived: dict[str, XY] | None = None
    errors: dict[str, float] = {}
    if not oracle:
        perceived = perceive_blocks(client, world, scene.sim_prompt_options)
        errors = {n: math.dist(perceived[n], truth[n]) * 1000 for n in truth}
    seen = perceived if perceived is not None else truth
    png = encode_png(np.ascontiguousarray(cv2.cvtColor(top_view(world), cv2.COLOR_RGB2BGR)))
    container_names = [r.name for r in regions]
    plan = planner or client.plan_tidy
    steps, dropped = clean_plan(
        plan(png, goal, dict(seen), container_names),
        names,
        container_names,
        {n for n in names if world.shape(n).kind == "sphere"},
    )
    if not steps:
        raise TidyError("Muse Spark found nothing it could tidy")
    program = TaskProgram(name=empty.name, steps=steps)

    controller.reset_to_home()
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
    if sam_verify and not oracle:

        def look(wanted: list[str]) -> dict[str, XY]:
            return perceive_blocks(client, world, {n: scene.sim_prompt_options[n] for n in wanted})

        fixes = fix_misses(program, world, controller, regions, look, names, seen)
    if recorder and record_to:
        recorder.save(record_to)
    return TidyResult(program, verify(program, world, regions), dropped, errors, step_frames, fixes)
