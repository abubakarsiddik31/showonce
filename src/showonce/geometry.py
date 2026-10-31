"""Pixel to table-plane mapping shared by the demo video and the simulated top camera.

The default calibration maps a full camera frame onto a fixed rectangle of the table. The
simulated top camera is placed to view exactly that rectangle, so pixel coordinates from a
phone clip and from the sim camera mean the same thing. Real clips can pass four clicked
corner points instead.
"""

from __future__ import annotations

from collections.abc import Sequence

import cv2
import numpy as np

Point = tuple[float, float]

WORK_CENTER_X = 0.465  # table-plane x of the viewed rectangle's center (meters)
WORK_WIDTH_Y = 0.52  # extent along the image horizontal, which runs along world -y


class Calibration:
    """A planar homography between image pixels and table coordinates (x, y in meters)."""

    def __init__(self, image_points: Sequence[Point], table_points: Sequence[Point]) -> None:
        if len(image_points) != 4 or len(table_points) != 4:
            raise ValueError("Calibration needs exactly four point pairs.")
        src = np.array(image_points, dtype=np.float32)
        dst = np.array(table_points, dtype=np.float32)
        self._to_table = cv2.getPerspectiveTransform(src, dst)
        self._to_image = cv2.getPerspectiveTransform(dst, src)

    @classmethod
    def for_frame(cls, width: int, height: int) -> Calibration:
        """Map a whole frame onto the default table rectangle (image right is world -y)."""
        half_w = WORK_WIDTH_Y / 2
        half_h = half_w * height / width
        x_top, x_bottom = WORK_CENTER_X + half_h, WORK_CENTER_X - half_h
        return cls(
            [(0, 0), (width, 0), (width, height), (0, height)],
            [(x_top, half_w), (x_top, -half_w), (x_bottom, -half_w), (x_bottom, half_w)],
        )

    @classmethod
    def from_corners(
        cls, image_corners: Sequence[Point], table_corners: Sequence[Point]
    ) -> Calibration:
        return cls(image_corners, table_corners)

    @staticmethod
    def _apply(matrix: np.ndarray, point: Point) -> Point:
        out = cv2.perspectiveTransform(np.array([[point]], dtype=np.float32), matrix)
        return (float(out[0, 0, 0]), float(out[0, 0, 1]))

    def to_table(self, pixel: Point) -> Point:
        return self._apply(self._to_table, pixel)

    def to_pixel(self, table_xy: Point) -> Point:
        return self._apply(self._to_image, table_xy)

    def rect_to_table(
        self, center: Point, size: tuple[float, float]
    ) -> tuple[Point, tuple[float, float]]:
        """Map a pixel rectangle to its table-plane bounding box (center, size)."""
        cx, cy = center
        w, h = size
        corners = [
            self.to_table((cx + sx * w / 2, cy + sy * h / 2)) for sx in (-1, 1) for sy in (-1, 1)
        ]
        xs, ys = [c[0] for c in corners], [c[1] for c in corners]
        return (
            ((min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2),
            (max(xs) - min(xs), max(ys) - min(ys)),
        )
