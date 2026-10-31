"""Repeatability test: stack one block on another from random layouts."""

from __future__ import annotations

import math
import random
from dataclasses import dataclass

from showonce.sim.controller import IKError, PandaController
from showonce.sim.scene import BLOCK_HALF, BlockDef, SimWorld

XY_TOL = 0.015
Z_TOL = 0.006


@dataclass(frozen=True, slots=True)
class StackResult:
    run: int
    ok: bool
    xy_error: float
    z_error: float
    note: str = ""


def _random_layout(rng: random.Random) -> tuple[tuple[float, float], tuple[float, float]]:
    while True:
        a = (rng.uniform(0.35, 0.6), rng.uniform(-0.22, 0.22))
        b = (rng.uniform(0.35, 0.6), rng.uniform(-0.22, 0.22))
        if math.dist(a, b) > 0.12:
            return a, b


def run_stack_test(runs: int = 10, seed: int = 0) -> list[StackResult]:
    rng = random.Random(seed)
    results: list[StackResult] = []
    for i in range(1, runs + 1):
        world = SimWorld([BlockDef("a", (0.85, 0.2, 0.2, 1)), BlockDef("b", (0.2, 0.4, 0.85, 1))])
        pos_a, pos_b = _random_layout(rng)
        world.set_block("a", pos_a)
        world.set_block("b", pos_b)
        controller = PandaController(world)
        try:
            controller.pick_place("a", pos_b, surface_z=2 * BLOCK_HALF)
        except IKError as exc:
            results.append(StackResult(i, False, math.nan, math.nan, str(exc)))
            continue
        a, b = world.block_pos("a"), world.block_pos("b")
        xy_err = math.dist(a[:2], b[:2])
        z_err = abs(a[2] - (b[2] + 2 * BLOCK_HALF))
        results.append(StackResult(i, xy_err < XY_TOL and z_err < Z_TOL, xy_err, z_err))
    return results
