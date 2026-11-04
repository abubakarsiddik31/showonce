"""See the simulated table: SAM 3.1 on the top camera frame gives object positions."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor

import cv2
import numpy as np
from numpy.typing import NDArray

from showonce.geometry import WORK_CENTER_X, Calibration
from showonce.meta.client import MetaClient
from showonce.meta.sam import Detection
from showonce.sim.record import top_view
from showonce.sim.scene import CAMERA_HEIGHT, SimWorld

XY = tuple[float, float]

COLOR_TOLERANCE = 0.3  # a pixel counts as an object's colour when this close (RGB, 0 to 1.7)
MIN_SHARE = 0.1  # a match must be at least this much its own colour


class NotFoundError(RuntimeError):
    """Raised when SAM cannot find an object in the camera frame."""


def _correct_parallax(table_xy: XY, height: float) -> XY:
    """Undo the perspective shift of a point seen at ``height`` above the table.

    The calibration maps pixels to the table plane. A point above the plane projects farther
    from the camera axis, so it is pulled back toward the axis.
    """
    scale = (CAMERA_HEIGHT - height) / CAMERA_HEIGHT
    return (
        WORK_CENTER_X + (table_xy[0] - WORK_CENTER_X) * scale,
        table_xy[1] * scale,
    )


def _share(image: NDArray[np.uint8], det: Detection, color: tuple[float, float, float]) -> float:
    """The fraction of the middle of a detection's box that is ``color``.

    A stained white plate is still mostly white, and a mug is mostly its own colour, so this
    holds up where an average colour would not.
    """
    box = det.box
    w, h = box.x2 - box.x1, box.y2 - box.y1
    crop = image[
        max(0, int(box.y1 + 0.15 * h)) : int(box.y2 - 0.15 * h),
        max(0, int(box.x1 + 0.15 * w)) : int(box.x2 - 0.15 * w),
    ]
    if crop.size == 0:
        return 0.0
    gap = np.linalg.norm(crop.reshape(-1, 3) / 255 - np.array(color), axis=1)
    return float(np.mean(gap <= COLOR_TOLERANCE))


def perceive_blocks(
    client: MetaClient,
    world: SimWorld,
    prompts: Mapping[str, Sequence[str]],
    *,
    workers: int = 3,
) -> dict[str, XY]:
    """Render the top camera (arm must already be parked) and locate each object with SAM."""
    image = top_view(world)
    # The sim camera's own frame, whatever size the demo clip was: pixels here are not the clip's.
    calibration = Calibration.for_frame(image.shape[1], image.shape[0])
    ok, encoded = cv2.imencode(".png", cv2.cvtColor(image, cv2.COLOR_RGB2BGR))
    if not ok:
        raise RuntimeError("Could not encode the camera frame")
    png = encoded.tobytes()

    def locate(name: str) -> tuple[str, XY]:
        expected = world.color(name)
        rivals = [world.color(n) for n in prompts if n != name]
        best: Detection | None = None
        for phrase in prompts[name]:  # SAM is picky about wording, so try each in turn
            # A loose phrase can match another object too, so drop a match that is mostly
            # some other object's colour. One that is clearly this object's colour stays: a
            # cup full of cereal is also partly the colour of a gray knife.
            scored = [
                (own, d)
                for d in client.segment_image(png, phrase)
                if (own := _share(image, d, expected)) >= MIN_SHARE
                or own >= max((_share(image, d, r) for r in rivals), default=0)
            ]
            if scored:
                share, best = max(scored, key=lambda item: (item[0] >= MIN_SHARE, item[1].box.area))
                if share >= MIN_SHARE:
                    break
        if best is None:
            raise NotFoundError(f"SAM found no '{prompts[name][0]}' for {name}")
        shape = world.shape(name)
        table_xy = calibration.to_table(best.box.center)
        table_xy = (table_xy[0] - shape.bbox_offset[0], table_xy[1] - shape.bbox_offset[1])
        return name, _correct_parallax(table_xy, shape.half_height * 1.5)

    with ThreadPoolExecutor(max_workers=workers) as pool:
        return dict(pool.map(locate, prompts))
