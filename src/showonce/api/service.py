"""Workflows behind the web API: learn a task from a clip, then run it in the simulator."""

from __future__ import annotations

import json
import multiprocessing
import uuid
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from pathlib import Path
from typing import Any

from showonce.api.jobs import Job, JobStore
from showonce.api.questions import build_questions, step_model
from showonce.api.schemas import (
    CheckOut,
    ContainerOut,
    LearnResultOut,
    MoveOut,
    RestOut,
    RunResultOut,
    SampleOut,
    StepModel,
)
from showonce.config import Settings
from showonce.demo import Learned, frame_size, learn_from_video
from showonce.meta.client import MetaClient
from showonce.perception.pipeline import video_fps
from showonce.program import Step, TaskProgram
from showonce.scene_spec import SceneSpec
from showonce.sim.record import SIM_FPS

SAMPLE_URL = "/media/samples"
RUN_URL = "/media/runs"


class NotFoundError(LookupError):
    """Raised for an unknown sample or a run requested before the task was learned."""


def _duration(video: Path) -> float:
    import cv2

    capture = cv2.VideoCapture(str(video))
    try:
        frames, fps = capture.get(cv2.CAP_PROP_FRAME_COUNT), capture.get(cv2.CAP_PROP_FPS)
    finally:
        capture.release()
    return round(frames / fps, 2) if fps > 0 else 0.0


def run_worker(
    scene_json: str, steps: list[dict[str, str]], seed: int, oracle: bool, out: str
) -> dict[str, Any]:
    """Replay on a shuffled table in a child process (the renderer needs a main thread)."""
    from showonce.config import get_settings
    from showonce.replay import replay

    scene = SceneSpec.model_validate_json(scene_json)
    program = TaskProgram(name=scene.name, steps=[Step(**s) for s in steps])
    out_path = Path(out)
    if oracle:
        result = replay(None, program, scene, seed, record_to=out_path, oracle=True)
    else:
        with MetaClient(get_settings()) as client:
            result = replay(client, program, scene, seed, record_to=out_path)
    return {
        "checks": [{"step": c.step, "ok": c.ok, "detail": c.detail} for c in result.checks],
        "errors": result.perception_error_mm,
        "frames": result.step_frames,
    }


class Workspace:
    """Owns the sample folder, the run folder and the job pools."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.samples_dir = settings.samples_dir
        self.runs_dir = settings.runs_dir
        self.jobs = JobStore()
        self._threads = ThreadPoolExecutor(max_workers=4, thread_name_prefix="job")
        self._procs: ProcessPoolExecutor | None = None
        self._uploads: dict[str, tuple[Path, Path]] = {}

    # -- samples -------------------------------------------------------------------------

    def _sample_files(self, sample_id: str) -> tuple[Path, Path]:
        if sample_id in self._uploads:
            return self._uploads[sample_id]
        video = self.samples_dir / f"{sample_id}.mp4"
        scene = self.samples_dir / f"{sample_id}.json"
        known = (
            {p.stem for p in self.samples_dir.glob("*.json")}
            if self.samples_dir.is_dir()
            else set()
        )
        if sample_id not in known or not video.is_file():
            raise NotFoundError(f"Unknown sample '{sample_id}'")
        return video, scene

    def _video_url(self, sample_id: str) -> str:
        if sample_id in self._uploads:
            return f"{RUN_URL}/uploads/{sample_id}/video.mp4"
        return f"{SAMPLE_URL}/{sample_id}.mp4"

    def list_samples(self) -> list[SampleOut]:
        out: list[SampleOut] = []
        if not self.samples_dir.is_dir():
            return out
        for scene_path in sorted(self.samples_dir.glob("*.json")):
            video = scene_path.with_suffix(".mp4")
            if not video.is_file():
                continue
            scene = SceneSpec.load(scene_path)
            out.append(
                SampleOut(
                    id=scene_path.stem,
                    name=scene_path.stem.replace("_", " "),
                    video_url=self._video_url(scene_path.stem),
                    objects=list(scene.prompts),
                    containers=[*scene.container_prompts, *[c.name for c in scene.containers]],
                    duration_s=_duration(video),
                )
            )
        return out

    def add_upload(self, video: bytes, scene: SceneSpec) -> str:
        upload_id = f"upload-{uuid.uuid4().hex[:8]}"
        folder = self.runs_dir / "uploads" / upload_id
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "video.mp4").write_bytes(video)
        (folder / "scene.json").write_text(scene.model_dump_json(indent=2))
        self._uploads[upload_id] = (folder / "video.mp4", folder / "scene.json")
        return upload_id

    # -- learn ---------------------------------------------------------------------------

    def _resolved_scene_path(self, sample_id: str) -> Path:
        return self.runs_dir / "scenes" / f"{sample_id}.json"

    def start_learn(self, sample_id: str) -> Job:
        video, scene_path = self._sample_files(sample_id)
        scene = SceneSpec.load(scene_path)

        def work(progress: Any) -> LearnResultOut:
            progress("Watching the clip with SAM 3.1 and Muse Spark")
            with MetaClient(self.settings) as client:
                learned = learn_from_video(client, video, scene)
            path = self._resolved_scene_path(sample_id)
            path.parent.mkdir(parents=True, exist_ok=True)
            assert learned.scene is not None
            path.write_text(learned.scene.model_dump_json(indent=2))
            return self._learn_result(sample_id, video, learned)

        return self.jobs.submit("learn", self._threads, work)

    def _learn_result(self, sample_id: str, video: Path, learned: Learned) -> LearnResultOut:
        fps = learned.observation.fps
        width, height = frame_size(video)
        assert learned.scene is not None
        steps = learned.program.steps
        source = "geometry" if learned.source == "geometry" else "muse_spark"
        return LearnResultOut(
            sample_id=sample_id,
            video_url=self._video_url(sample_id),
            width=width,
            height=height,
            duration_s=_duration(video),
            source=source,
            steps=[step_model(s) for s in steps],
            questions=build_questions(steps, learned.semantic, learned.source),
            discrepancies=learned.discrepancies,
            rests=[
                RestOut(
                    object=name,
                    start_s=round(r.start_frame / fps, 2),
                    end_s=round(r.end_frame / fps, 2),
                    x=r.center[0],
                    y=r.center[1],
                )
                for name, rests in learned.observation.rests.items()
                for r in rests
            ],
            moves=[
                MoveOut(
                    object=m.label,
                    start_s=round(m.start_frame / fps, 2),
                    end_s=round(m.end_frame / fps, 2),
                    from_x=m.src[0],
                    from_y=m.src[1],
                    to_x=m.dst[0],
                    to_y=m.dst[1],
                )
                for m in learned.observation.moves
            ],
            containers=[
                ContainerOut(
                    name=c.name,
                    x1=c.center[0] - c.size[0] / 2,
                    y1=c.center[1] - c.size[1] / 2,
                    x2=c.center[0] + c.size[0] / 2,
                    y2=c.center[1] + c.size[1] / 2,
                )
                for c in learned.scene.containers
            ],
        )

    # -- run -----------------------------------------------------------------------------

    def start_run(self, sample_id: str, steps: list[StepModel], seed: int, oracle: bool) -> Job:
        scene_path = self._resolved_scene_path(sample_id)
        if not scene_path.is_file():
            raise NotFoundError("Learn the task from the video before running it")
        scene_json = scene_path.read_text()
        run_id = uuid.uuid4().hex[:10]
        out = self.runs_dir / "web" / run_id / "sim.mp4"
        out.parent.mkdir(parents=True, exist_ok=True)
        payload = [{"object": s.object, "action": s.action, "target": s.target} for s in steps]

        def work(progress: Any) -> RunResultOut:
            progress("Shuffling the table and running the arm")
            if self._procs is None:
                self._procs = ProcessPoolExecutor(
                    max_workers=1, mp_context=multiprocessing.get_context("spawn")
                )
            data = self._procs.submit(
                run_worker, scene_json, payload, seed, oracle, str(out)
            ).result()
            checks = [CheckOut(**c) for c in data["checks"]]
            return RunResultOut(
                video_url=f"{RUN_URL}/web/{run_id}/sim.mp4",
                success=all(c.ok for c in checks),
                seed=seed,
                checks=checks,
                step_times_s=[round(f / SIM_FPS, 2) for f in data["frames"]],
                perception_error_mm={k: round(v, 1) for k, v in data["errors"].items()},
            )

        return self.jobs.submit("run", self._threads, work)

    def dump_debug(self) -> str:  # pragma: no cover - handy in a REPL
        return json.dumps([s.model_dump(by_alias=True) for s in self.list_samples()], indent=2)


__all__ = ["NotFoundError", "Workspace", "run_worker", "video_fps"]
