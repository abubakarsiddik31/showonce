"""End to end: demo video in, robot execution out."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import cv2

from showonce.geometry import Calibration
from showonce.learn import learn_program
from showonce.meta.client import MetaClient
from showonce.perception.pipeline import Observation, observe
from showonce.program import TaskProgram
from showonce.scene_spec import SceneSpec
from showonce.sim.controller import PandaController
from showonce.sim.executor import Layout, Region, StepCheck, build_world, execute, verify
from showonce.sim.record import SimRecorder


@dataclass(frozen=True, slots=True)
class Learned:
    program: TaskProgram
    layout: Layout  # where objects started in the video, in table coordinates
    observation: Observation


@dataclass(frozen=True, slots=True)
class RunResult:
    checks: list[StepCheck]

    @property
    def success(self) -> bool:
        return all(c.ok for c in self.checks)


def frame_size(video: Path) -> tuple[int, int]:
    capture = cv2.VideoCapture(str(video))
    try:
        return int(capture.get(cv2.CAP_PROP_FRAME_WIDTH)), int(
            capture.get(cv2.CAP_PROP_FRAME_HEIGHT)
        )
    finally:
        capture.release()


def regions_from_scene(scene: SceneSpec, calibration: Calibration) -> list[Region]:
    regions = []
    for c in scene.containers:
        center, size = calibration.rect_to_table(c.center, c.size)
        regions.append(Region(c.name, center, size))
    return regions


def learn_from_video(client: MetaClient, video: Path, scene: SceneSpec) -> Learned:
    """Watch the clip: find what moved where, then compile a task program."""
    width, height = scene.size or frame_size(video)
    calibration = Calibration.for_frame(width, height)
    obs = observe(client, video, scene.prompts)
    program = learn_program(scene.name, obs.moves, obs.rests, scene.containers)
    objects = {
        name: calibration.to_table(rests[0].center) for name, rests in obs.rests.items() if rests
    }
    return Learned(program, Layout(objects, regions_from_scene(scene, calibration)), obs)


def run_in_sim(program: TaskProgram, layout: Layout, record_to: Path | None = None) -> RunResult:
    """Execute the program on a layout. Optionally record a video of the run."""
    world = build_world(layout)
    recorder = SimRecorder(world) if record_to else None
    controller = PandaController(world, on_step=recorder.capture if recorder else None)
    execute(program, world, controller, layout.regions)
    if recorder and record_to:
        recorder.save(record_to)
    return RunResult(verify(program, world, layout.regions))
