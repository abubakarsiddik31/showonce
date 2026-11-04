"""Render the simulation to video frames and to the top-camera still used for replay."""

from __future__ import annotations

from pathlib import Path

import imageio.v2 as imageio
import mujoco
import numpy as np
from numpy.typing import NDArray

from showonce.sim.scene import CAMERA_ASPECT, CAMERA_NAME, SimWorld

Image = NDArray[np.uint8]
SIM_FPS = 50


class SimRecorder:
    """Collects frames from a 3/4 view of the table while the arm works."""

    def __init__(self, world: SimWorld, width: int = 960, height: int = 540) -> None:
        self.world = world
        self.renderer = mujoco.Renderer(world.model, height, width)
        self.frames: list[Image] = []
        self.closed = False
        self.camera = mujoco.MjvCamera()
        self.camera.lookat[:] = [0.4, 0.0, 0.2]
        self.camera.distance = 1.4
        self.camera.azimuth = 100
        self.camera.elevation = -45

    def capture(self) -> None:
        self.renderer.update_scene(self.world.data, camera=self.camera)
        self.frames.append(self.renderer.render().copy())

    def close(self) -> None:
        """Release the renderer. The simulator process lives on and runs clip after clip, and an
        open renderer keeps the last model's drawing state, so one run's pictures could end up
        on the next run's objects."""
        if not self.closed:
            self.closed = True
            self.renderer.close()

    def save(self, path: Path, fps: int = SIM_FPS) -> None:
        """Write the video. The frames are already captured, so this is also the end of the run."""
        self.close()
        path.parent.mkdir(parents=True, exist_ok=True)
        with imageio.get_writer(
            path, fps=fps, codec="libx264", pixelformat="yuv420p", macro_block_size=2
        ) as writer:
            for frame in self.frames:
                writer.append_data(frame)  # type: ignore[attr-defined]


def top_view(world: SimWorld, width: int = 1280) -> Image:
    """Render the fixed top camera. Park the arm out of view before calling this."""
    height = round(width / CAMERA_ASPECT)
    renderer = mujoco.Renderer(world.model, height, width)
    renderer.update_scene(world.data, camera=CAMERA_NAME)
    image: Image = renderer.render().copy()
    renderer.close()
    return image
