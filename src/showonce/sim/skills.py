"""Motions that go beyond pick-and-place: wiping a surface and opening a packet.

Each skill drives the controller and leaves its effect in the simulated world (stains cleared,
lid carried off), which ``verify`` then checks against ground truth.
"""

from __future__ import annotations

import math

import numpy as np
from numpy.typing import NDArray

from showonce.sim.controller import PandaController
from showonce.sim.scene import LID_THICKNESS, TAB, SimWorld

XY = tuple[float, float]
Vec = NDArray[np.float64]

CLEARANCE = 0.003  # a held sponge rides this far above the surface it cleans
SPONGE_MARGIN = 0.005  # stains this close to the sponge's edge still count as wiped
DROP_CLEARANCE = 0.09  # how far from other things a lid is put down
LID_REACH_X, LID_REACH_Y = (0.36, 0.58), (-0.22, 0.22)  # where the arm can put a lid down


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


def wipe(
    world: SimWorld,
    controller: PandaController,
    tool: str,
    tool_at: Vec,
    surface: str,
    centre: XY,
    half: XY,
    top: float,
) -> None:
    """Pick up ``tool``, scrub the whole of ``surface`` with it and put it back."""
    hx, hy, hz = world.shape(tool).half
    z = top + hz + CLEARANCE  # the gripper holds the tool at its center
    path = wipe_path(centre, half, (hx, hy))

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


def _drop_spot(
    bag: XY,
    half: tuple[float, float],
    others: list[tuple[XY, float]],
    keep_out: list[tuple[XY, XY]],
) -> XY:
    """Where to put a lid down: beside the bag, as far as possible from everything else.

    The hand is wide along x, so the sides (along y) come first; a tall bag would be hit
    if the lid went down in line with it along x.
    """
    reach_y, reach_x = 2 * half[1] + 0.06, 2 * half[0] + 0.14
    best, best_room = None, -math.inf
    for dx, dy in ((0, reach_y), (0, -reach_y), (reach_x, 0), (-reach_x, 0)):
        spot = (bag[0] + dx, bag[1] + dy)
        if not (
            LID_REACH_X[0] <= spot[0] <= LID_REACH_X[1]
            and LID_REACH_Y[0] <= spot[1] <= LID_REACH_Y[1]
        ):
            continue
        room = min([math.dist(spot, p) - r for p, r in others] + [1.0])
        for centre, size in keep_out:
            room = min(
                room,
                max(abs(spot[0] - centre[0]) - size[0] / 2, abs(spot[1] - centre[1]) - size[1] / 2),
            )
        if dx == 0:
            room += 0.05  # prefer the sides
        if room > best_room:
            best, best_room = spot, room
    if best is None:
        raise ValueError("No free place to put the lid down")
    return best


def open_package(
    world: SimWorld,
    controller: PandaController,
    package: str,
    bag: XY,
    others: list[tuple[XY, float]],
    keep_out: list[tuple[XY, XY]],
) -> None:
    """Pinch the lid's pull tab, pull the lid off the packet and put it aside."""
    shape = world.shape(package)
    hz = shape.half[2]
    tab_z = 2 * hz + LID_THICKNESS + TAB[2]  # middle of the tab
    spot = _drop_spot(bag, (shape.half[0], shape.half[1]), others, keep_out)
    rest_z = LID_THICKNESS + TAB[2] + 0.002  # tab height when the lid lies on the table
    controller.pull_off(
        f"{package}_lid", np.array([bag[0], bag[1], tab_z]), np.array([spot[0], spot[1], rest_z])
    )
