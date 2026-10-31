"""Motions that go beyond pick-and-place: wiping a surface and opening a packet.

Each skill drives the controller and leaves its effect in the simulated world (stains cleared,
lid carried off), which ``verify`` then checks against ground truth.
"""

from __future__ import annotations

import math

import numpy as np
from numpy.typing import NDArray

from showonce.sim.controller import PandaController
from showonce.sim.scene import STRIP_HALF, STRIP_TAIL, TRAY_FLOOR, SimWorld, strip_offset

XY = tuple[float, float]
Vec = NDArray[np.float64]

CLEARANCE = 0.01  # a held sponge rides this far above what it cleans, so it never drags it
SPONGE_MARGIN = 0.005  # stains this close to the sponge's edge still count as wiped
DROP_CLEARANCE = 0.09  # how far from other things a lid is put down
LID_REACH_X, LID_REACH_Y = (0.34, 0.60), (-0.22, 0.22)  # where the arm can put a lid down


def wipe_path(centre: XY, half: XY, tool_half: XY) -> list[XY]:
    """A back-and-forth sweep that covers a rectangle with a rectangular tool."""
    span_x, span_y = max(0.0, half[0] - tool_half[0]), max(0.0, half[1] - tool_half[1])
    rows = 1 if span_x == 0 else math.ceil(2 * span_x / (1.6 * tool_half[0])) + 1
    path: list[XY] = []
    for i in range(rows):
        x = centre[0] + (-span_x + 2 * span_x * i / (rows - 1) if rows > 1 else 0.0)
        ends = [centre[1] - span_y, centre[1] + span_y]
        path += [(x, y) for y in (ends if i % 2 == 0 else ends[::-1])]
    return path


def circle_path(centre: XY, radius: float, tool_half: XY) -> list[XY]:
    """Scrub in rings: the centre first, then circles of growing radius, as a hand would."""
    spacing = 1.4 * min(tool_half)
    reach = max(0.0, radius - min(tool_half))
    rings = max(1, math.ceil(reach / spacing))
    path: list[XY] = [centre]
    for k in range(1, rings + 1):
        r = reach * k / rings
        points = max(10, min(28, round(2 * math.pi * r / 0.025)))
        for i in range(points + 1):  # the last point closes the ring where it started
            a = 2 * math.pi * i / points
            path.append((centre[0] + r * math.cos(a), centre[1] + r * math.sin(a)))
    return path


def wipe(
    world: SimWorld,
    controller: PandaController,
    tool: str,
    tool_at: Vec,
    surface: str,
    centre: XY,
    half: XY,
    top: float,
    *,
    round_surface: bool = False,
) -> None:
    """Pick up ``tool``, scrub the whole of ``surface`` with it and put it back.

    Round dishes are scrubbed in circles and everything else in back-and-forth strokes. Either
    way it is the robot's own way of cleaning: it need not copy the hand it watched.
    """
    hx, hy, hz = world.shape(tool).half
    z = top + hz + CLEARANCE  # the gripper holds the tool at its center
    path = (
        circle_path(centre, min(half), (hx, hy))
        if round_surface
        else wipe_path(centre, half, (hx, hy))
    )

    def clean() -> None:
        tcp = world.tcp_pos()
        world.scrub(
            surface, (float(tcp[0]), float(tcp[1])), (hx + SPONGE_MARGIN, hy + SPONGE_MARGIN)
        )

    controller.grasp(tool, tool_at)
    start = path[0]
    controller.move_to(np.array([start[0], start[1], z + 0.06]))
    controller.move_to(np.array([start[0], start[1], z]))
    clean()
    controller.sweep(path[1:], z, clean)
    controller.release(tool, tool_at + np.array([0.0, 0.0, 0.002]))


REACH_X, REACH_Y = (0.20, 0.62), (-0.28, 0.28)  # where the arm can set something down


def free_spot(
    anchor: XY,
    half: tuple[float, float],
    others: list[tuple[XY, float]],
    keep_out: list[tuple[XY, XY]],
    direction: XY | None = None,
) -> XY:
    """A clear place to set something down: beside ``anchor`` at ``half``'s footprint.

    ``direction`` is a unit vector away from the anchor (a relation's world unit); ``None``
    tries all four sides. Raises ``ValueError`` when nowhere within arm reach is clear.
    """
    reach_x = max(half[0], 0.02)
    reach_y = max(half[1], 0.02)
    unit = (direction[0], direction[1]) if direction and direction != (0.0, 0.0) else None
    dirs = [unit] if unit else [(1.0, 0.0), (-1.0, 0.0), (0.0, 1.0), (0.0, -1.0)]
    gaps = (0.02, 0.05, 0.08, 0.11)
    best, best_room = None, -math.inf
    for d in dirs:
        dx, dy = d[0] * (reach_x if d[0] else reach_y), d[1] * (reach_y if d[1] else reach_x)
        for gap in gaps:
            spot = (anchor[0] + dx + d[0] * gap, anchor[1] + dy + d[1] * gap)
            if not (REACH_X[0] <= spot[0] <= REACH_X[1] and REACH_Y[0] <= spot[1] <= REACH_Y[1]):
                continue
            room = min(
                [
                    max(abs(spot[0] - p[0]) - r - half[0], abs(spot[1] - p[1]) - r - half[1])
                    for p, r in others
                ]
                + [1.0]
            )
            for centre, size in keep_out:
                room = min(
                    room,
                    max(
                        abs(spot[0] - centre[0]) - size[0] / 2,
                        abs(spot[1] - centre[1]) - size[1] / 2,
                    ),
                )
            if gap != 0:
                room -= gap * 0.5  # the closer beside, the better
            if room > best_room:
                best, best_room = spot, room
    if best is None:
        raise ValueError(f"No free place beside {anchor}")
    return best


def _drop_spot(
    bag: XY,
    half: tuple[float, float],
    others: list[tuple[XY, float]],
    keep_out: list[tuple[XY, XY]],
) -> XY:
    """Where to lay the torn-off strip: right beside the bag, clear of everything else.

    The strip lies parallel to the bag's top edge and is long, so clearance is measured against
    its footprint, not just its center.
    """
    length = half[1] + STRIP_TAIL
    gaps = (0.04, 0.07, 0.10)  # from the bag's edge; a flat bag needs no room for the hand
    sides = [(sign * (half[0] + gap), 0.0) for gap in gaps for sign in (1, -1)]
    best, best_room = None, -math.inf
    for dx, dy in sides:
        spot = (bag[0] + dx, bag[1] + dy)
        if not (
            LID_REACH_X[0] <= spot[0] <= LID_REACH_X[1]
            and LID_REACH_Y[0] <= spot[1] <= LID_REACH_Y[1]
        ):
            continue
        room = min(
            [
                max(abs(spot[0] - p[0]) - r - STRIP_HALF[0], abs(spot[1] - p[1]) - r - length)
                for p, r in others
            ]
            + [1.0]
        )
        for centre, size in keep_out:
            room = min(
                room,
                max(abs(spot[0] - centre[0]) - size[0] / 2, abs(spot[1] - centre[1]) - size[1] / 2),
            )
        if dx != 0:
            room -= abs(dx) * 0.5  # the closer to the bag the better, as in the video
        if room > best_room:
            best, best_room = spot, room
    if best is None:
        raise ValueError("No free place to lay the strip down")
    return best


def open_package(
    world: SimWorld,
    controller: PandaController,
    package: str,
    bag: XY,
    others: list[tuple[XY, float]],
    keep_out: list[tuple[XY, XY]],
) -> None:
    """Take hold of the seal strip by the end that sticks out, tear it off and lay it aside."""
    shape = world.shape(package)
    hx, hy, hz = shape.half
    dx, _ = strip_offset(shape)
    # Grip the end nearer the middle of the table, so the arm does not stretch to the edge.
    side = -1.0 if bag[1] > 0 else 1.0
    reach = side * (hy + STRIP_TAIL / 2)
    grip = np.array([bag[0] + dx, bag[1] + reach, 2 * hz + STRIP_HALF[2]])
    spot = _drop_spot(bag, (hx, hy), others, keep_out)
    rest_z = STRIP_HALF[2] + 0.002  # the strip lies flat on the table
    controller.pull_off(f"{package}_lid", grip, np.array([spot[0], spot[1] + reach, rest_z]))


def pour(
    world: SimWorld,
    controller: PandaController,
    source: str,
    source_at: Vec,
    target_name: str,
    centre: XY,
) -> None:
    """Hold the cup over the target, tip it until it is empty, and set it back down.

    The contents are an abstraction (Task 4): the transfer happens in ``pour_into``, not
    in the physics.
    """
    over = np.array([centre[0], centre[1], TRAY_FLOOR + 0.14])
    controller.grasp(source, source_at)
    controller.move_to(over)
    controller.tilt(2.0)
    world.pour_into(source, target_name)
    controller.dwell(100)
    controller.tilt(0.0)
    controller.release(source, source_at + np.array([0.0, 0.0, 0.002]))
