"""See the simulated table: SAM 3.1 on the top camera frame gives object positions."""

from __future__ import annotations

from collections.abc import Mapping
from concurrent.futures import ThreadPoolExecutor

import cv2

from showonce.geometry import WORK_CENTER_X, Calibration
from showonce.meta.client import MetaClient
from showonce.sim.record import top_view
from showonce.sim.scene import BLOCK_HALF, CAMERA_HEIGHT, SimWorld

XY = tuple[float, float]


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


def perceive_blocks(
    client: MetaClient,
    world: SimWorld,
    prompts: Mapping[str, str],
    calibration: Calibration,
    *,
    workers: int = 3,
) -> dict[str, XY]:
    """Render the top camera (arm must already be parked) and locate each object with SAM."""
    image = top_view(world)
    ok, encoded = cv2.imencode(".png", cv2.cvtColor(image, cv2.COLOR_RGB2BGR))
    if not ok:
        raise RuntimeError("Could not encode the camera frame")
    png = encoded.tobytes()

    def locate(name: str) -> tuple[str, XY]:
        detections = client.segment_image(png, prompts[name])
        if not detections:
            raise NotFoundError(f"SAM found no '{prompts[name]}' for {name}")
        best = max(detections, key=lambda d: d.box.area)
        table_xy = calibration.to_table(best.box.center)
        return name, _correct_parallax(table_xy, BLOCK_HALF * 1.5)

    with ThreadPoolExecutor(max_workers=workers) as pool:
        return dict(pool.map(locate, prompts))
