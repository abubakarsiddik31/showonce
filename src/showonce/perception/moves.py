"""Turn per-frame SAM detections into resting positions and moves.

A hand hides an object while it moves, so continuous paths are unreliable. Instead we find
frames where the object is clearly visible and stays put (a rest), and call any jump between
two consecutive rests a move.
"""

from __future__ import annotations

import math
import statistics
from dataclasses import dataclass
from itertools import pairwise

from showonce.meta.sam import Detection

Point = tuple[float, float]


@dataclass(frozen=True, slots=True)
class Rest:
    start_frame: int
    end_frame: int
    center: Point


@dataclass(frozen=True, slots=True)
class Move:
    label: str
    start_frame: int  # last frame of the previous rest
    end_frame: int  # first frame of the next rest
    src: Point
    dst: Point


def best_per_frame(detections: list[Detection]) -> dict[int, Detection]:
    """Keep the largest detection per frame.

    SAM can give the same object a new track id after occlusion, so ids are ignored here
    and one detection per frame is used for a single-object prompt.
    """
    best: dict[int, Detection] = {}
    for det in detections:
        current = best.get(det.frame)
        if current is None or det.box.area > current.box.area:
            best[det.frame] = det
    return best


def _percentile(values: list[float], q: float) -> float:
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(q * len(ordered)))]


def find_rests(
    series: dict[int, Detection],
    fps: float,
    *,
    min_rest_s: float = 0.3,
    tol_px: float = 12.0,
    visible_ratio: float = 0.7,
) -> list[Rest]:
    """Find stretches where the object is fully visible and stays within ``tol_px``."""
    if not series:
        return []
    reference = _percentile([d.box.area for d in series.values()], 0.9)
    visible = [f for f in sorted(series) if series[f].box.area >= visible_ratio * reference]
    min_frames = max(2, round(min_rest_s * fps))

    rests: list[Rest] = []
    group: list[int] = []

    def centers(frames: list[int]) -> Point:
        return (
            statistics.median(series[f].box.center[0] for f in frames),
            statistics.median(series[f].box.center[1] for f in frames),
        )

    def flush() -> None:
        if len(group) >= min_frames:
            rests.append(Rest(group[0], group[-1], centers(group)))

    for frame in visible:
        if group and math.dist(series[frame].box.center, centers(group)) > tol_px:
            flush()
            group = []
        group.append(frame)
    flush()
    return rests


def moves_from_rests(label: str, rests: list[Rest], min_move_px: float = 30.0) -> list[Move]:
    """A move is a jump larger than ``min_move_px`` between two consecutive rests."""
    return [
        Move(label, prev.end_frame, nxt.start_frame, prev.center, nxt.center)
        for prev, nxt in pairwise(rests)
        if math.dist(prev.center, nxt.center) > min_move_px
    ]
