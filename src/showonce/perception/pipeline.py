"""Video in, ordered list of object moves out."""

from __future__ import annotations

from collections.abc import Mapping
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path

import cv2

from showonce.meta.client import MetaClient
from showonce.perception.moves import (
    Move,
    Rest,
    best_per_frame,
    find_rests,
    moves_from_rests,
)


def video_fps(path: Path) -> float:
    capture = cv2.VideoCapture(str(path))
    try:
        fps = float(capture.get(cv2.CAP_PROP_FPS))
    finally:
        capture.release()
    if fps <= 0:
        raise ValueError(f"Could not read frame rate from {path}")
    return fps


@dataclass(frozen=True, slots=True)
class Observation:
    """Everything perception learned from one clip, keyed by object label."""

    fps: float
    rests: dict[str, list[Rest]]
    moves: list[Move]


def observe(
    client: MetaClient, video: Path, prompts: Mapping[str, str], *, workers: int = 3
) -> Observation:
    """Segment each object with SAM 3.1, then find resting positions and moves.

    ``prompts`` maps an object name to the short noun phrase sent to SAM.
    """
    fps = video_fps(video)
    file_id = client.upload_video(video)
    names = list(prompts)

    def one(name: str) -> list[Rest]:
        return find_rests(best_per_frame(client.segment_video(file_id, prompts[name])), fps)

    with ThreadPoolExecutor(max_workers=workers) as pool:
        per_name = list(pool.map(one, names))
    rests = dict(zip(names, per_name, strict=True))
    moves = sorted(
        (m for name, r in rests.items() for m in moves_from_rests(name, r)),
        key=lambda m: m.start_frame,
    )
    return Observation(fps, rests, moves)


def extract_moves(
    client: MetaClient, video: Path, prompts: Mapping[str, str], *, workers: int = 3
) -> list[Move]:
    """Return all detected moves, ordered by time."""
    return observe(client, video, prompts, workers=workers).moves
