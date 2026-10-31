"""Video in, ordered list of object moves out."""

from __future__ import annotations

from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import cv2

from showonce.meta.client import MetaClient
from showonce.perception.moves import Move, best_per_frame, find_rests, moves_from_rests


def video_fps(path: Path) -> float:
    capture = cv2.VideoCapture(str(path))
    try:
        fps = float(capture.get(cv2.CAP_PROP_FPS))
    finally:
        capture.release()
    if fps <= 0:
        raise ValueError(f"Could not read frame rate from {path}")
    return fps


def extract_moves(
    client: MetaClient, video: Path, labels: Sequence[str], *, workers: int = 3
) -> list[Move]:
    """Segment each label with SAM 3.1 and return all detected moves, ordered by time."""
    fps = video_fps(video)
    file_id = client.upload_video(video)

    def one(label: str) -> list[Move]:
        series = best_per_frame(client.segment_video(file_id, label))
        return moves_from_rests(label, find_rests(series, fps))

    with ThreadPoolExecutor(max_workers=workers) as pool:
        per_label = list(pool.map(one, labels))
    return sorted((m for moves in per_label for m in moves), key=lambda m: m.start_frame)
