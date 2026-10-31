import math

import pytest

from showonce.objects import ObjectProfile
from showonce.program import Step, TaskProgram
from showonce.sim.controller import PandaController
from showonce.sim.executor import (
    ExecutionError,
    Layout,
    Region,
    build_world,
    execute,
    slot_xy,
    verify,
)
from showonce.sim.scene import DEFAULT_ASSET_DIR, RIM_THICKNESS, TRAY_FLOOR, block_def

pytestmark = pytest.mark.skipif(
    not (DEFAULT_ASSET_DIR / "panda.xml").exists(),
    reason="Panda model missing; run scripts/fetch_assets.sh",
)


def test_program_runs_on_two_different_layouts() -> None:
    program = TaskProgram(
        name="t",
        steps=[Step(object="red block", action="place_in", target="box")],
    )
    region = Region("box", (0.5, -0.15), (0.1, 0.1))
    for start in [(0.4, 0.15), (0.55, 0.05)]:
        layout = Layout({"red block": start, "blue block": (0.35, -0.2)}, [region])
        world = build_world(layout)
        execute(program, world, PandaController(world), layout.regions)
        assert all(c.ok for c in verify(program, world, layout.regions))


def test_mugs_are_carried_into_a_tray_and_stay_inside_its_rim() -> None:
    names = ["red mug", "blue mug", "green mug"]
    program = TaskProgram(
        name="t", steps=[Step(object=n, action="place_in", target="tray") for n in names]
    )
    region = Region("tray", (0.47, -0.13), (0.167, 0.166))
    layout = Layout(
        {"red mug": (0.45, 0.05), "blue mug": (0.39, 0.13), "green mug": (0.5, 0.15)}, [region]
    )
    world = build_world(layout)
    assert world.shape("red mug").kind == "cylinder"
    execute(program, world, PandaController(world), layout.regions)
    assert all(c.ok for c in verify(program, world, layout.regions))
    for name in names:
        assert abs(world.block_pos(name)[2] - world.half_height(name)) < 0.01 + TRAY_FLOOR


def test_slots_keep_each_object_clear_of_the_rim_and_apart() -> None:
    region = Region("tray", (0.47, -0.13), (0.167, 0.166))
    radius = block_def("red mug").shape.radius
    slots = [slot_xy(region, i, radius) for i in range(4)]
    for x, y in slots:
        assert abs(x - region.center[0]) + radius + RIM_THICKNESS <= region.size[0] / 2
        assert abs(y - region.center[1]) + radius + RIM_THICKNESS <= region.size[1] / 2
    assert all(math.dist(a, b) > 2 * radius for i, a in enumerate(slots) for b in slots[i + 1 :])


def test_any_profile_can_be_carried_to_a_tray() -> None:
    profiles = {
        "gray book": ObjectProfile(shape="box", width=0.05, depth=0.06, height=0.02),
        "red ball": ObjectProfile(shape="sphere", width=0.05, depth=0.05, height=0.05),
        "blue can": ObjectProfile(shape="cylinder", width=0.05, depth=0.05, height=0.1),
    }
    program = TaskProgram(
        name="t", steps=[Step(object=n, action="place_in", target="tray") for n in profiles]
    )
    region = Region("tray", (0.47, -0.13), (0.167, 0.166))
    layout = Layout(
        {"gray book": (0.45, 0.05), "red ball": (0.39, 0.13), "blue can": (0.5, 0.15)},
        [region],
        profiles,
    )
    world = build_world(layout)
    execute(program, world, PandaController(world), layout.regions)
    assert all(c.ok for c in verify(program, world, layout.regions))


def test_an_object_too_wide_for_the_gripper_is_refused() -> None:
    wide = ObjectProfile(shape="box", width=0.12, depth=0.05, height=0.05)
    region = Region("tray", (0.47, -0.13), (0.167, 0.166))
    layout = Layout({"red tray": (0.45, 0.1)}, [region], {"red tray": wide})
    world = build_world(layout)
    program = TaskProgram(
        name="t", steps=[Step(object="red tray", action="place_in", target="tray")]
    )
    with pytest.raises(ExecutionError, match="too wide"):
        execute(program, world, PandaController(world), layout.regions)


def test_nothing_can_be_stacked_on_a_ball() -> None:
    profiles = {"red ball": ObjectProfile(shape="sphere", width=0.05, depth=0.05, height=0.05)}
    layout = Layout({"red ball": (0.4, 0.1), "blue block": (0.5, 0.1)}, [], profiles)
    world = build_world(layout)
    program = TaskProgram(
        name="t", steps=[Step(object="blue block", action="stack_on", target="red ball")]
    )
    with pytest.raises(ExecutionError, match="round"):
        execute(program, world, PandaController(world), layout.regions)
