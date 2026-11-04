"""End to end: demo video in, robot execution out."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

import cv2

from showonce.chat import (
    clean_steps,
    describe_plan,
    drop_setting_down,
    repair_advice,
    understand,
)
from showonce.geometry import Calibration
from showonce.learn import LearnError, compare_plans, learn_program
from showonce.meta.client import MetaAPIError, MetaClient
from showonce.objects import ObjectProfile, fit_to_gripper, fit_to_table
from showonce.perception.pipeline import Observation, observe
from showonce.perception.profiles import encode_png, first_frame, profile_objects
from showonce.program import SEMANTIC_ACTIONS, Step, TaskProgram
from showonce.scene_spec import ContainerSpec, SceneSpec
from showonce.sim.controller import PandaController
from showonce.sim.executor import (
    Layout,
    Region,
    StepCheck,
    build_world,
    execute,
    execute_with_repair,
    verify,
)
from showonce.sim.perceive import NotFoundError
from showonce.sim.record import SimRecorder
from showonce.unposed import unposed_layout

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
    understanding: str = ""  # what the robot would say it saw, in its own words


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


def video_fps(video: Path) -> float:
    capture = cv2.VideoCapture(str(video))
    try:
        return float(capture.get(cv2.CAP_PROP_FPS) or 25.0)
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
    """Muse Spark's reading of the clip, with any step that makes no sense on this table dropped.

    The model sometimes turns a detail into a step of its own, such as laying down a torn-off
    seal becoming "put the bag beside the bag". Those would send the robot off to do nonsense.
    """
    containers = [c.name for c in scene.containers]
    try:
        raw = client.plan_video(client.upload_video(video), list(scene.prompts), containers)
    except (MetaAPIError, ValueError, KeyError) as exc:
        log.warning("Muse Spark could not read %s: %s", video.name, exc)
        return None
    steps = drop_setting_down(clean_steps(raw, list(scene.prompts), containers))
    for dropped in (s for s in raw if s not in steps):
        log.warning("Dropped a step that makes no sense on this table: %s", dropped)
    return steps


def _understand(client: MetaClient, video: Path, steps: list[Step]) -> str:
    try:
        file_id = client.upload_video(video)
    except (MetaAPIError, ValueError, KeyError) as exc:
        log.warning("Could not upload %s to narrate it: %s", video.name, exc)
        return describe_plan(steps)
    return understand(client, file_id, steps)


def fit_profiles(
    profiles: dict[str, ObjectProfile], program: TaskProgram
) -> dict[str, ObjectProfile]:
    """Make each object fit what the program does with it.

    Anything the gripper picks up is scaled to fit its fingers; what is only wiped or acted on
    keeps its real size. A packet that gets opened becomes a sealed box with a lid. A knife
    and the thing it cuts are shortened, so both fit on the table beside everything else.
    """
    fitted = dict(profiles)
    for step in program.steps:
        if step.action == "wipe" and (target := fitted.get(step.target)) is not None:
            # Its stains are simulated, so a picture with real stains would never look clean.
            fitted[step.target] = target.model_copy(update={"texture": None})
        profile = fitted.get(step.object)
        if profile is None:
            continue
        if step.action == "open":
            fitted[step.object] = profile.model_copy(update={"shape": "box", "openable": True})
        elif step.action == "push":
            pass  # slid, never grasped: it keeps its true size
        elif step.action == "press":
            fitted[step.object] = profile.model_copy(update={"pressable": True})
        else:
            fitted[step.object] = fit_to_gripper(profile)
    cut = {
        name
        for step in program.steps
        if step.action == "cut"
        for name in (step.object, step.target)
    }
    for step in program.steps:
        # A cut target splits in two, and halves are boxes: model it as one.
        # (Mirrors the open coercion above; the executor still refuses round
        # targets for programs that did not come from a learned cut.)
        if step.action == "cut":
            target = fitted.get(step.target)
            if target is not None and target.shape not in ("box", "log"):
                fitted[step.target] = target.model_copy(update={"shape": "box"})
    return {name: fit_to_table(p) if name in cut else p for name, p in fitted.items()}


def learn_from_video(
    client: MetaClient, video: Path, scene: SceneSpec, texture_dir: Path | None = None
) -> Learned:
    """Watch the clip with SAM 3.1 and Muse Spark, then compile a task program.

    SAM geometry is the primary signal. Muse Spark's independent reading is cross-checked
    against it, and is used instead only if the geometry cannot explain a move.
    """
    width, height = scene.size or frame_size(video)
    calibration = Calibration.for_frame(width, height)
    scene = scene.model_copy(update={"containers": resolve_containers(client, video, scene)})
    profiles = profile_objects(client, first_frame(video), scene, texture_dir)
    try:
        obs = observe(client, video, scene.prompts)
    except Exception as exc:  # any tracking failure means no geometry
        log.warning("SAM could not track %s: %s", video.name, exc)
        obs = Observation(fps=video_fps(video), rests={}, moves=[])
    semantic = _read_with_muse_spark(client, video, scene)
    source = "geometry"
    unposed = not obs.rests and not obs.moves
    if unposed:
        # No trackable geometry (an angled close-up has no overhead mapping), so the
        # reading decides and the objects start from a default arrangement.
        if semantic is None:
            raise LearnError(f"SAM tracked nothing in {video.name} and Muse Spark did not answer")
        program = TaskProgram(name=scene.name, steps=semantic)
        problems = ["no trackable geometry; using Muse Spark's steps on a default layout"]
        source = "muse_spark"
    elif semantic and any(s.action in SEMANTIC_ACTIONS for s in semantic):
        # Where things ended up cannot show a wipe or a tear, so the video reading decides.
        program = TaskProgram(name=scene.name, steps=semantic)
        problems = ["geometry cannot see wiping or opening; using Muse Spark's steps"]
        source = "muse_spark"
    else:
        try:
            program = learn_program(scene.name, obs.moves, obs.rests, scene.containers)
            problems = compare_plans(program.steps, semantic) if semantic is not None else []
            if not program.steps and semantic:
                # Nothing resting changed (the object arrived in a hand): trust the reading.
                program = TaskProgram(name=scene.name, steps=semantic)
                problems = ["geometry saw no move; using Muse Spark's steps"]
                source = "muse_spark"
        except LearnError:
            if semantic is None:
                raise
            program = TaskProgram(name=scene.name, steps=semantic)
            problems = ["geometry could not explain a move; using Muse Spark's steps"]
            source = "muse_spark"
    scene = scene.model_copy(update={"profiles": fit_profiles(profiles, program)})
    if unposed:
        layout = unposed_layout(program, scene.profiles, [c.name for c in scene.containers])
    else:
        objects = {
            name: calibration.to_table(rests[0].center)
            for name, rests in obs.rests.items()
            if rests
        }
        layout = Layout(objects, regions_from_scene(scene, calibration), scene.profiles)
    understanding = _understand(client, video, program.steps)
    return Learned(program, layout, obs, source, semantic, problems, scene, understanding)


def run_in_sim(
    program: TaskProgram,
    layout: Layout,
    record_to: Path | None = None,
    *,
    repair: bool = False,
    client: MetaClient | None = None,
) -> RunResult:
    """Execute the program on a layout. Optionally record a video of the run.

    With ``repair`` and a client, the first failed spatial step gets one
    Muse-advised retry before the checks are returned.
    """
    world = build_world(layout, program)
    recorder = SimRecorder(world) if record_to else None
    controller = PandaController(world, on_step=recorder.capture if recorder else None)
    try:
        if repair and client is not None:
            checks = execute_with_repair(
                program,
                world,
                controller,
                layout.regions,
                lambda step, detail: repair_advice(client, step, detail),
            )
        else:
            execute(program, world, controller, layout.regions)
            checks = verify(program, world, layout.regions)
        if recorder and record_to:
            controller.park()  # step away, so the finished table can be seen
            controller.dwell(150)
            recorder.save(record_to)
    finally:
        if recorder:
            recorder.close()
    return RunResult(checks)
