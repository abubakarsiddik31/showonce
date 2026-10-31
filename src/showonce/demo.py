"""End to end: demo video in, robot execution out."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

import cv2

from showonce.geometry import Calibration
from showonce.learn import LearnError, compare_plans, learn_program
from showonce.meta.client import MetaAPIError, MetaClient
from showonce.perception.pipeline import Observation, observe
from showonce.perception.profiles import encode_png, first_frame, profile_objects
from showonce.program import Step, TaskProgram
from showonce.scene_spec import ContainerSpec, SceneSpec
from showonce.sim.controller import PandaController
from showonce.sim.executor import Layout, Region, StepCheck, build_world, execute, verify
from showonce.sim.perceive import NotFoundError
from showonce.sim.record import SimRecorder

log = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class Learned:
    program: TaskProgram
    layout: Layout  # where objects started in the video, in table coordinates
    observation: Observation
    source: str = "geometry"  # "geometry", or "muse_spark" when geometry could not explain a move
    semantic: list[Step] | None = None  # Muse Spark's independent reading, if it answered
    discrepancies: list[str] = field(default_factory=list)
    scene: SceneSpec | None = None  # the scene with containers resolved to pixel rectangles


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


def resolve_containers(client: MetaClient, video: Path, scene: SceneSpec) -> list[ContainerSpec]:
    """Fixed containers plus any located by SAM on the first frame (before a hand appears)."""
    found = list(scene.containers)
    if not scene.container_prompts:
        return found
    png = encode_png(first_frame(video))
    for name, prompt in scene.container_prompts.items():
        detections = client.segment_image(png, prompt)
        if not detections:
            raise NotFoundError(f"SAM found no '{prompt}' for container {name}")
        box = max(detections, key=lambda d: d.box.area).box
        found.append(
            ContainerSpec(
                name=name,
                center=box.center,
                size=(box.x2 - box.x1, box.y2 - box.y1),
            )
        )
    return found


def _read_with_muse_spark(client: MetaClient, video: Path, scene: SceneSpec) -> list[Step] | None:
    try:
        return client.plan_video(
            client.upload_video(video), list(scene.prompts), [c.name for c in scene.containers]
        )
    except (MetaAPIError, ValueError, KeyError) as exc:
        log.warning("Muse Spark could not read %s: %s", video.name, exc)
        return None


def learn_from_video(client: MetaClient, video: Path, scene: SceneSpec) -> Learned:
    """Watch the clip with SAM 3.1 and Muse Spark, then compile a task program.

    SAM geometry is the primary signal. Muse Spark's independent reading is cross-checked
    against it, and is used instead only if the geometry cannot explain a move.
    """
    width, height = scene.size or frame_size(video)
    calibration = Calibration.for_frame(width, height)
    scene = scene.model_copy(update={"containers": resolve_containers(client, video, scene)})
    scene = scene.model_copy(
        update={"profiles": profile_objects(client, first_frame(video), scene)}
    )
    obs = observe(client, video, scene.prompts)
    semantic = _read_with_muse_spark(client, video, scene)
    source = "geometry"
    try:
        program = learn_program(scene.name, obs.moves, obs.rests, scene.containers)
        problems = compare_plans(program.steps, semantic) if semantic is not None else []
    except LearnError:
        if semantic is None:
            raise
        program = TaskProgram(name=scene.name, steps=semantic)
        problems = ["geometry could not explain a move; using Muse Spark's steps"]
        source = "muse_spark"
    objects = {
        name: calibration.to_table(rests[0].center) for name, rests in obs.rests.items() if rests
    }
    layout = Layout(objects, regions_from_scene(scene, calibration))
    return Learned(program, layout, obs, source, semantic, problems, scene)


def run_in_sim(program: TaskProgram, layout: Layout, record_to: Path | None = None) -> RunResult:
    """Execute the program on a layout. Optionally record a video of the run."""
    world = build_world(layout)
    recorder = SimRecorder(world) if record_to else None
    controller = PandaController(world, on_step=recorder.capture if recorder else None)
    execute(program, world, controller, layout.regions)
    if recorder and record_to:
        recorder.save(record_to)
    return RunResult(verify(program, world, layout.regions))
