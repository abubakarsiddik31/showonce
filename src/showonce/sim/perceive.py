"""See the simulated table: SAM 3.1 on the top camera frame gives object positions."""

from __future__ import annotations

import itertools
import math
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
    reference: Mapping[str, XY] | None = None,
) -> dict[str, XY]:
    """Render the top camera (arm must already be parked) and locate each object with SAM.

    Objects that look alike share one search. Which detection is which lemon is arbitrary, so
    with ``reference`` (the true layout, known to a test harness) each name takes the detection
    nearest its own true spot, which keeps the per-step checks about the right object. The
    robot only ever acts on the positions SAM reports.
    """
    image = top_view(world)
    # The sim camera's own frame, whatever size the demo clip was: pixels here are not the clip's.
    calibration = Calibration.for_frame(image.shape[1], image.shape[0])
    ok, encoded = cv2.imencode(".png", cv2.cvtColor(image, cv2.COLOR_RGB2BGR))
    if not ok:
        raise RuntimeError("Could not encode the camera frame")
    png = encoded.tobytes()

    def candidates(name: str) -> list[Detection]:
        """Every detection of this object's colour, best first, for the first phrase that works."""
        expected = world.color(name)
        rivals = [world.color(n) for n in prompts if n != name]
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
                scored.sort(key=lambda item: (item[0] >= MIN_SHARE, item[1].box.area), reverse=True)
                if scored[0][0] >= MIN_SHARE:
                    return [d for _, d in scored]
        return []

    def position(name: str, found: Detection) -> XY:
        shape = world.shape(name)
        table_xy = calibration.to_table(found.box.center)
        table_xy = (table_xy[0] - shape.bbox_offset[0], table_xy[1] - shape.bbox_offset[1])
        return _correct_parallax(table_xy, shape.half_height * 1.5)

    # Objects that look alike (three lemons) share one search; each takes a different detection.
    # Which lemon is which does not matter, so the largest detections go out in name order.
    groups: dict[tuple[str, ...], list[str]] = {}
    for name in prompts:
        groups.setdefault(tuple(prompts[name]), []).append(name)

    def locate_group(names: list[str]) -> list[tuple[str, XY]]:
        found = candidates(names[0])
        if len(found) < len(names):
            raise NotFoundError(
                f"SAM found {len(found)} '{prompts[names[0]][0]}', needed {len(names)}"
            )
        spots = [position(names[0], d) for d in found]
        if reference is None or len(names) == 1:
            return list(zip(names, spots, strict=False))
        best = min(
            itertools.permutations(range(len(spots)), len(names)),
            key=lambda pick: sum(
                math.dist(spots[i], reference[n]) for n, i in zip(names, pick, strict=True)
            ),
        )
        return [(n, spots[i]) for n, i in zip(names, best, strict=True)]

    with ThreadPoolExecutor(max_workers=workers) as pool:
        located = pool.map(locate_group, groups.values())
    return {name: xy for group in located for name, xy in group}
