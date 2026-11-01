"""Render the two pictures of the robot the web app ships: a looping demo and an idle poster.

Development tool. Both come from the simulator and need no API key (the arm reads true object
positions), and the results are committed under web/public/ so the app does not need them at
run time:

    uv run python scripts/render_site_assets.py
"""

from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

import imageio.v2 as imageio

from showonce.program import Step, TaskProgram
from showonce.replay import replay, shuffled_layout
from showonce.scene_spec import SceneSpec
from showonce.sim.controller import PandaController
from showonce.sim.executor import Layout, build_world
from showonce.sim.record import SimRecorder

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "web" / "public"
SCENE = ROOT / "samples" / "dishes_wash.json"


def scene_with_profiles() -> SceneSpec:
    """The dish-wash scene, with the plates and sponge the robot learned from that clip."""
    learned = ROOT / "runs" / "scenes" / "dishes_wash.json"
    return SceneSpec.load(learned if learned.is_file() else SCENE)


def render_demo(scene: SceneSpec) -> None:
    program = TaskProgram(
        name="wash",
        steps=[
            Step(object="yellow sponge", action="wipe", target="white plate"),
            Step(object="yellow sponge", action="wipe", target="blue plate"),
        ],
    )
    with tempfile.TemporaryDirectory() as tmp:
        raw = Path(tmp) / "run.mp4"
        replay(None, program, scene, seed=5, record_to=raw, oracle=True)
        subprocess.run(
            [
                "ffmpeg", "-loglevel", "error", "-y", "-i", str(raw),
                "-vf", "setpts=PTS/1.6,scale=960:-2", "-an", "-c:v", "libx264",
                "-crf", "30", "-pix_fmt", "yuv420p", "-movflags", "+faststart",
                str(OUT / "robot-demo.mp4"),
            ],
            check=True,
        )  # fmt: skip


def render_poster(scene: SceneSpec) -> None:
    """The cell at rest: the arm at home, a table to work on, nothing moving."""
    program = TaskProgram(
        name="wash",
        steps=[Step(object="yellow sponge", action="wipe", target="white plate")],
    )
    truth = shuffled_layout(list(scene.prompts), [], 5, scene.profiles)
    world = build_world(Layout(truth, [], scene.profiles), program)
    PandaController(world).reset_to_home()
    recorder = SimRecorder(world, width=1600, height=900)
    recorder.capture()
    imageio.imwrite(OUT / "robot-cell.jpg", recorder.frames[0], quality=88)


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    spec = scene_with_profiles()
    render_poster(spec)
    render_demo(spec)
    for name in ("robot-cell.jpg", "robot-demo.mp4"):
        print(name, f"{(OUT / name).stat().st_size / 1e3:.0f} kB")
