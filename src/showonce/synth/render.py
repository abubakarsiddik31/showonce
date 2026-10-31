"""Render synthetic top-down demo clips with a moving "hand" and ground-truth labels."""

from __future__ import annotations

import json
import math
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import cv2
import imageio.v2 as imageio
import numpy as np
from numpy.typing import NDArray

from showonce.synth.scene import FPS, HEIGHT, WIDTH, Container, ObjectSpec, Point, Scenario

Image = NDArray[np.uint8]

TABLE_COLOR = (190, 205, 222)
BLOCK_SIZE = 76
CUP_RADIUS = 44
SKIN = (125, 160, 215)
SKIN_DARK = (100, 135, 190)
CARRY_LEVEL = 99
# Offsets (relative to a container center) for the 1st, 2nd, ... object placed inside it.
SLOT_OFFSETS: tuple[Point, ...] = ((-50, -70), (50, -70), (-50, 30), (50, 30), (0, 100))


@dataclass(slots=True)
class Frame:
    positions: dict[str, Point]
    levels: dict[str, int]
    hand: Point | None


def _lerp(a: Point, b: Point, u: float) -> Point:
    return (a[0] + (b[0] - a[0]) * u, a[1] + (b[1] - a[1]) * u)


def _ease(u: float) -> float:
    return u * u * (3 - 2 * u)


def _initial_layout(sc: Scenario) -> dict[str, Point]:
    """Place objects on a jittered grid in the left part of the table, clear of containers."""
    rng = random.Random(sc.seed)
    slots = [(x, y) for x in (180.0, 380.0, 580.0) for y in (150.0, 360.0, 570.0)]
    rng.shuffle(slots)
    return {
        obj.name: (slot[0] + rng.uniform(-30, 30), slot[1] + rng.uniform(-30, 30))
        for obj, slot in zip(sc.objects, slots, strict=False)
    }


def _entry_point(target: Point) -> Point:
    return (WIDTH / 2 + (target[0] - WIDTH / 2) * 0.3, HEIGHT + 170.0)


def build_frames(sc: Scenario) -> tuple[list[Frame], list[dict[str, Any]]]:
    """Simulate the whole clip. Returns the frames and per-step event times for ground truth."""
    pos = _initial_layout(sc)
    levels = {name: 0 for name in pos}
    containers = {c.name: c for c in sc.containers}
    inside: dict[str, int] = {c.name: 0 for c in sc.containers}
    frames: list[Frame] = []
    events: list[dict[str, Any]] = []
    s = 1.0 / sc.speed

    def push(hand: Point | None) -> None:
        frames.append(Frame(dict(pos), dict(levels), hand))

    def hold(seconds: float, hand: Point | None = None) -> None:
        for _ in range(max(1, round(seconds * FPS))):
            push(hand)

    def move(seconds: float, a: Point, b: Point, carry: str | None = None) -> None:
        n = max(1, round(seconds * FPS))
        for i in range(1, n + 1):
            h = _lerp(a, b, _ease(i / n))
            if carry:
                pos[carry] = h
            push(h)

    hold(1.0)
    for step in sc.steps:
        start = pos[step.object]
        if step.action == "stack_on":
            goal = pos[step.target]
            level = levels[step.target] + 1
        else:
            box = containers[step.target]
            offset = SLOT_OFFSETS[inside[step.target] % len(SLOT_OFFSETS)]
            goal = (box.center[0] + offset[0], box.center[1] + offset[1])
            inside[step.target] += 1
            level = 0
        entry = _entry_point(start)
        move(0.9 * s, entry, start)
        t_grasp = len(frames) / FPS
        hold(0.25 * s, start)
        levels[step.object] = CARRY_LEVEL
        move(1.1 * s, start, goal, carry=step.object)
        hold(0.25 * s, goal)
        t_release = len(frames) / FPS
        levels[step.object] = level
        move(0.6 * s, goal, _entry_point(goal))
        hold(0.8 * s)
        events.append(
            {
                "object": step.object,
                "action": step.action,
                "target": step.target,
                "t_grasp": round(t_grasp, 3),
                "t_release": round(t_release, 3),
                "from": [round(start[0], 1), round(start[1], 1)],
                "to": [round(goal[0], 1), round(goal[1], 1)],
            }
        )
    hold(1.0)
    return frames, events


def _draw_container(img: Image, c: Container) -> None:
    w, h = c.size
    x1, y1 = int(c.center[0] - w / 2), int(c.center[1] - h / 2)
    x2, y2 = x1 + w, y1 + h
    if c.kind == "box":
        cv2.rectangle(img, (x1, y1), (x2, y2), (55, 75, 105), -1)
        cv2.rectangle(img, (x1 + 14, y1 + 14), (x2 - 14, y2 - 14), (95, 120, 155), -1)
        cv2.rectangle(img, (x1, y1), (x2, y2), (35, 50, 75), 4)
    else:
        for x in range(x1, x2, 24):
            cv2.line(img, (x, y1), (min(x + 12, x2), y1), (110, 110, 110), 3)
            cv2.line(img, (x, y2), (min(x + 12, x2), y2), (110, 110, 110), 3)
        for y in range(y1, y2, 24):
            cv2.line(img, (x1, y), (x1, min(y + 12, y2)), (110, 110, 110), 3)
            cv2.line(img, (x2, y), (x2, min(y + 12, y2)), (110, 110, 110), 3)
        cv2.putText(img, c.name, (x1 + 8, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (90, 90, 90), 2)


def _shade(color: tuple[int, int, int], f: float) -> tuple[int, int, int]:
    return (
        int(min(255, color[0] * f)),
        int(min(255, color[1] * f)),
        int(min(255, color[2] * f)),
    )


def _draw_object(img: Image, spec: ObjectSpec, p: Point, level: int) -> None:
    lift = min(level, 3) if level != CARRY_LEVEL else 4
    cx, cy = int(p[0]), int(p[1])
    scale = 1.0 - 0.08 * min(level, 3) if level != CARRY_LEVEL else 1.05
    sx, sy = cx + 6 + 3 * lift, cy + 8 + 3 * lift
    if spec.kind == "block":
        half = int(BLOCK_SIZE * scale / 2)
        cv2.rectangle(img, (sx - half, sy - half), (sx + half, sy + half), (120, 130, 140), -1)
        cv2.rectangle(
            img, (cx - half, cy - half), (cx + half, cy + half), _shade(spec.color, 0.7), -1
        )
        inner = int(half * 0.78)
        cv2.rectangle(img, (cx - inner, cy - inner), (cx + inner, cy + inner), spec.color, -1)
    else:
        r = int(CUP_RADIUS * scale)
        cv2.circle(img, (sx, sy), r, (120, 130, 140), -1)
        cv2.circle(img, (cx, cy), r, _shade(spec.color, 0.7), -1)
        cv2.circle(img, (cx, cy), int(r * 0.78), spec.color, -1)
        cv2.circle(img, (cx, cy), int(r * 0.55), _shade(spec.color, 0.55), -1)


def _draw_hand(img: Image, hand: Point) -> None:
    entry = _entry_point(hand)
    dx, dy = entry[0] - hand[0], entry[1] - hand[1]
    norm = math.hypot(dx, dy) or 1.0
    ux, uy = dx / norm, dy / norm
    palm = (int(hand[0] + ux * 22), int(hand[1] + uy * 22))
    cv2.line(img, palm, (int(entry[0]), int(entry[1])), SKIN_DARK, 104)
    cv2.line(img, palm, (int(entry[0]), int(entry[1])), SKIN, 96)
    cv2.circle(img, palm, 58, SKIN, -1)
    px, py = -uy, ux
    for k in (-1.5, -0.5, 0.5, 1.5):
        tip = (int(hand[0] - ux * 18 + px * k * 24), int(hand[1] - uy * 18 + py * k * 24))
        cv2.circle(img, tip, 15, SKIN, -1)
    cv2.circle(img, palm, 58, SKIN_DARK, 3)


def render_frame(sc: Scenario, frame: Frame, rng: np.random.Generator) -> Image:
    img: Image = np.full((HEIGHT, WIDTH, 3), TABLE_COLOR, dtype=np.uint8)
    for c in sc.containers:
        _draw_container(img, c)
    specs = {o.name: o for o in sc.objects}
    for name in sorted(frame.positions, key=lambda n: frame.levels[n]):
        _draw_object(img, specs[name], frame.positions[name], frame.levels[name])
    if frame.hand is not None:
        _draw_hand(img, frame.hand)
    out = img.astype(np.float32) * sc.light
    out += rng.normal(0.0, sc.noise, out.shape)
    result: Image = np.clip(out, 0, 255).astype(np.uint8)
    return result


def write_clip(sc: Scenario, out_dir: Path) -> Path:
    """Render one scenario to ``<name>.mp4`` and ``<name>.json`` in ``out_dir``."""
    out_dir.mkdir(parents=True, exist_ok=True)
    frames, events = build_frames(sc)
    rng = np.random.default_rng(sc.seed)
    video = out_dir / f"{sc.name}.mp4"
    with imageio.get_writer(
        video,
        fps=FPS,
        codec="libx264",
        pixelformat="yuv420p",
        macro_block_size=16,
        ffmpeg_params=["-movflags", "+faststart"],
    ) as writer:
        for frame in frames:
            rgb = cv2.cvtColor(render_frame(sc, frame, rng), cv2.COLOR_BGR2RGB)
            writer.append_data(rgb)  # type: ignore[attr-defined]
    final = frames[-1]
    truth = {
        "name": sc.name,
        "notes": sc.notes,
        "fps": FPS,
        "size": [WIDTH, HEIGHT],
        "duration_s": round(len(frames) / FPS, 2),
        "prompts": {o.name: o.prompt or o.name for o in sc.objects},
        # In the simulator every object is a cube, so prompt by color and "block".
        "sim_prompts": {o.name: f"{o.name.split()[0]} block" for o in sc.objects},
        "initial": {k: list(v) for k, v in build_frames_initial(sc).items()},
        "steps": events,
        "final": {k: [round(v[0], 1), round(v[1], 1)] for k, v in final.positions.items()},
        "containers": [
            {"name": c.name, "kind": c.kind, "center": list(c.center), "size": list(c.size)}
            for c in sc.containers
        ],
    }
    (out_dir / f"{sc.name}.json").write_text(json.dumps(truth, indent=2))
    return video


def build_frames_initial(sc: Scenario) -> dict[str, Point]:
    return {k: (round(v[0], 1), round(v[1], 1)) for k, v in _initial_layout(sc).items()}
