"""Turn an observation (object moves in pixels) into a symbolic task program."""

from __future__ import annotations

import math

from showonce.perception.moves import Move, Rest
from showonce.program import Step, TaskProgram
from showonce.scene_spec import ContainerSpec

STACK_RADIUS_PX = 45.0
NEAR_RADIUS_PX = 90.0  # how close to another object a "put it beside that" landing counts


class LearnError(RuntimeError):
    """Raised when a move cannot be explained as a supported action."""


def _rest_near(rests: list[Rest], frame: int) -> Rest | None:
    """The rest closest in time to ``frame``."""
    if not rests:
        return None
    return min(
        rests,
        key=lambda r: (
            0
            if r.start_frame <= frame <= r.end_frame
            else min(abs(r.start_frame - frame), abs(r.end_frame - frame))
        ),
    )


def _pixel_relation(dx: float, dy: float) -> str:
    """Which side of the target an object landed on, in the clip's image frame.

    Image x runs right and image y runs down; the hand enters from the bottom edge, so
    dy > 0 is toward the person (in front).
    """
    if abs(dx) >= abs(dy):
        return "left_of" if dx < 0 else "right_of"
    return "in_front_of" if dy > 0 else "behind"


def classify_move(
    move: Move,
    all_rests: dict[str, list[Rest]],
    containers: list[ContainerSpec],
    heights: dict[str, int] | None = None,
) -> Step:
    """Decide whether a move put an object in a container or on another object.

    ``heights`` is how many objects each object currently sits above. When several objects
    overlap at the destination (a stack), the highest one is the one to stack on.
    """
    heights = heights or {}
    for container in containers:
        if container.contains(move.dst):
            return Step(object=move.label, action="place_in", target=container.name)
    best: tuple[int, float, str] | None = None
    nearest: tuple[float, str, Rest] | None = None
    for label, rests in all_rests.items():
        if label == move.label:
            continue
        rest = _rest_near(rests, move.end_frame)
        if rest is None:
            continue
        distance = math.dist(rest.center, move.dst)
        if nearest is None or distance < nearest[0]:
            nearest = (distance, label, rest)
        if distance > STACK_RADIUS_PX:
            continue
        candidate = (-heights.get(label, 0), distance, label)
        if best is None or candidate < best:
            best = candidate
    if best is not None:
        return Step(object=move.label, action="stack_on", target=best[2])
    if nearest is not None and nearest[0] <= NEAR_RADIUS_PX:
        distance, label, rest = nearest
        dx, dy = move.dst[0] - rest.center[0], move.dst[1] - rest.center[1]
        return Step(
            object=move.label,
            action="place_near",
            target=label,
            relation=_pixel_relation(dx, dy),  # type: ignore[arg-type]
        )
    raise LearnError(
        f"Cannot explain move of {move.label} to {tuple(round(v) for v in move.dst)}: "
        "not inside a container, not on another object and not beside one."
    )


def learn_program(
    name: str,
    moves: list[Move],
    all_rests: dict[str, list[Rest]],
    containers: list[ContainerSpec],
) -> TaskProgram:
    steps: list[Step] = []
    heights: dict[str, int] = {}
    last: dict[str, Step] = {}
    for move in moves:
        step = classify_move(move, all_rests, containers, heights)
        if last.get(step.object) == step:
            continue  # nudged inside the container it is already in: not a new action
        last[step.object] = step
        heights[step.object] = heights.get(step.target, 0) + 1 if step.action == "stack_on" else 0
        steps.append(step)
    return TaskProgram(name=name, steps=steps)


def compare_plans(geometry: list[Step], semantic: list[Step]) -> list[str]:
    """Describe where two step lists disagree. An empty list means they match exactly."""
    problems: list[str] = []
    if len(geometry) != len(semantic):
        problems.append(f"step count differs: geometry {len(geometry)}, Muse Spark {len(semantic)}")
    for i, (a, b) in enumerate(zip(geometry, semantic, strict=False), 1):
        if a != b:
            problems.append(f"step {i}: geometry '{a}', Muse Spark '{b}'")
    return problems
