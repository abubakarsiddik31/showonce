"""Score detected moves against the ground-truth json written by the synthetic generator."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from showonce.perception.moves import Move

POSITION_TOL_PX = 30.0


@dataclass(frozen=True, slots=True)
class MoveScore:
    clip: str
    expected: int
    detected: int
    correct: int  # expected steps matched in order, by object and position
    exact: bool  # same number of moves and every one correct


def load_truth(path: Path) -> dict[str, Any]:
    data: dict[str, Any] = json.loads(path.read_text())
    return data


def score_moves(clip: str, truth: dict[str, Any], moves: list[Move]) -> MoveScore:
    steps = truth["steps"]
    correct = 0
    for step, move in zip(steps, moves, strict=False):
        if (
            move.label == step["object"]
            and math.dist(move.src, step["from"]) <= POSITION_TOL_PX
            and math.dist(move.dst, step["to"]) <= POSITION_TOL_PX
        ):
            correct += 1
    return MoveScore(
        clip=clip,
        expected=len(steps),
        detected=len(moves),
        correct=correct,
        exact=correct == len(steps) == len(moves),
    )
