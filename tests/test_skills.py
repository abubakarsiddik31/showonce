import itertools
import math

import numpy as np
import pytest

from showonce.demo import fit_profiles
from showonce.objects import ObjectProfile
from showonce.program import Step, TaskProgram
from showonce.sim.controller import PandaController
from showonce.sim.executor import ExecutionError, Layout, Region, build_world, execute, verify
from showonce.sim.scene import DEFAULT_ASSET_DIR
from showonce.sim.skills import circle_path, wipe_path

needs_panda = pytest.mark.skipif(
    not (DEFAULT_ASSET_DIR / "panda.xml").exists(), reason="Panda model missing"
)

PLATE = ObjectProfile(shape="cylinder", width=0.13, depth=0.13, height=0.02)
SPONGE = ObjectProfile(shape="box", width=0.06, depth=0.04, height=0.025)
CHIPS = ObjectProfile(shape="box", width=0.12, depth=0.16, height=0.05, openable=True)


def test_step_text_reads_naturally() -> None:
    assert str(Step(object="sponge", action="wipe", target="plate")) == "wipe plate with sponge"
    assert str(Step(object="chips", action="open", target="chips")) == "open chips"


def test_wipe_path_covers_the_whole_surface() -> None:
    centre, half, tool = (0.5, 0.0), (0.065, 0.065), (0.03, 0.02)
    path = wipe_path(centre, half, tool)
    xs = sorted({round(x, 4) for x, _ in path})
    assert xs[0] == pytest.approx(0.5 - 0.035) and xs[-1] == pytest.approx(0.5 + 0.035)
    assert all(b - a <= 1.6 * tool[0] + 1e-9 for a, b in itertools.pairwise(xs))
    ys = [y for _, y in path]
    assert min(ys) == pytest.approx(-0.045) and max(ys) == pytest.approx(0.045)


def test_wipe_path_on_a_surface_smaller_than_the_tool_is_one_pass() -> None:
    assert len(wipe_path((0.5, 0.0), (0.02, 0.02), (0.03, 0.02))) == 2


def test_only_grasped_objects_are_fitted_to_the_gripper() -> None:
    program = TaskProgram(
        name="t",
        steps=[
            Step(object="sponge", action="wipe", target="plate"),
            Step(object="chips", action="open", target="chips"),
        ],
    )
    wide_sponge = SPONGE.model_copy(update={"width": 0.14, "depth": 0.08})
    wide_chips = CHIPS.model_copy(update={"shape": "cylinder", "openable": False, "width": 0.14})
    fitted = fit_profiles({"sponge": wide_sponge, "plate": PLATE, "chips": wide_chips}, program)
    assert fitted["sponge"].width <= 0.068  # picked up, so it must fit
    assert fitted["plate"].width == 0.13  # only wiped, keeps its real size
    assert fitted["chips"].width == 0.14 and fitted["chips"].openable  # opened, not gripped


@needs_panda
def test_wipe_clears_every_stain_and_open_takes_the_lid_off() -> None:
    profiles = {"white plate": PLATE, "yellow sponge": SPONGE, "red chips": CHIPS}
    layout = Layout(
        {"white plate": (0.46, -0.12), "yellow sponge": (0.40, 0.0), "red chips": (0.52, 0.17)},
        [],
        profiles,
    )
    program = TaskProgram(
        name="t",
        steps=[
            Step(object="red chips", action="open", target="red chips"),
            Step(object="yellow sponge", action="wipe", target="white plate"),
        ],
    )
    world = build_world(layout, program)
    assert world.dirt_left("white plate") == (14, 14) and not world.is_open("red chips")
    execute(program, world, PandaController(world), [])
    assert all(c.ok for c in verify(program, world, []))
    assert world.dirt_left("white plate")[0] == 0 and world.is_open("red chips")
    assert world.block_pos("red chips")[2] == pytest.approx(0.025, abs=0.005)  # bag not moved


@needs_panda
def test_unwiped_plate_fails_verification() -> None:
    layout = Layout(
        {"white plate": (0.46, -0.12), "yellow sponge": (0.4, 0.1)},
        [],
        {"white plate": PLATE, "yellow sponge": SPONGE},
    )
    program = TaskProgram(
        name="t", steps=[Step(object="yellow sponge", action="wipe", target="white plate")]
    )
    world = build_world(layout, program)
    assert not verify(program, world, [])[0].ok  # nothing has been wiped yet


@needs_panda
def test_opening_something_that_is_not_a_packet_is_refused() -> None:
    layout = Layout({"red block": (0.45, 0.1)}, [])
    world = build_world(layout)
    program = TaskProgram(
        name="t", steps=[Step(object="red block", action="open", target="red block")]
    )
    with pytest.raises(ExecutionError, match="not something"):
        execute(program, world, PandaController(world), [])


def test_circular_scrub_starts_at_the_middle_and_stays_on_the_dish() -> None:
    centre, radius, tool = (0.5, 0.0), 0.08, (0.034, 0.022)
    path = circle_path(centre, radius, tool)
    assert path[0] == centre
    assert all(math.dist(p, centre) <= radius - tool[1] + 1e-9 for p in path)
    reach = max(math.dist(p, centre) for p in path)
    assert reach == pytest.approx(radius - tool[1])  # the outer ring reaches the rim
    rings = sorted({round(math.dist(p, centre), 4) for p in path})
    assert all(b - a <= 1.4 * tool[1] + 1e-3 for a, b in itertools.pairwise(rings))  # no gaps


def test_circular_scrub_on_a_dish_smaller_than_the_sponge_stays_in_the_middle() -> None:
    assert set(circle_path((0.5, 0.0), 0.01, (0.034, 0.022))) == {(0.5, 0.0)}


@needs_panda
def test_slide_pushes_a_box_without_grasping() -> None:
    book = ObjectProfile(shape="box", width=0.2, depth=0.14, height=0.03)  # far too wide to grasp
    layout = Layout({"green book": (0.35, -0.1)}, [], {"green book": book})
    world = build_world(layout, None)
    controller = PandaController(world)
    controller.reset_to_home()
    before = world.block_pos("green book").copy()
    controller.slide("green book", (0.35, 0.15))
    moved = float(np.linalg.norm(world.block_pos("green book")[:2] - before[:2]))
    assert moved > 0.15


@needs_panda
def test_stir_mixes_the_bowl() -> None:
    spoon = ObjectProfile(shape="box", width=0.025, depth=0.025, height=0.09)
    layout = Layout(
        {"yellow spoon": (0.4, -0.1)}, [Region("bowl", (0.5, 0.12), (0.16, 0.16))],
        {"yellow spoon": spoon},
    )
    program = TaskProgram(
        name="t", steps=[Step(object="yellow spoon", action="stir", target="bowl")]
    )
    world = build_world(layout, program)
    execute(program, world, PandaController(world), layout.regions)
    checks = verify(program, world, layout.regions)
    assert all(c.ok for c in checks), [c.detail for c in checks]
    assert world.is_mixed("bowl")


@needs_panda
def test_pour_empties_the_cup_into_the_bowl() -> None:
    cup = ObjectProfile(shape="cylinder", width=0.06, depth=0.06, height=0.08, handle=True)
    profiles = {"red cup": cup}
    layout = Layout({"red cup": (0.4, -0.1)}, [Region("bowl", (0.5, 0.12), (0.16, 0.16))], profiles)
    program = TaskProgram(name="t", steps=[Step(object="red cup", action="pour", target="bowl")])
    world = build_world(layout, program)
    execute(program, world, PandaController(world), layout.regions)
    checks = verify(program, world, layout.regions)
    assert all(c.ok for c in checks), [c.detail for c in checks]
    assert world.contents_of("bowl") is not None and world.contents_of("red cup") is None


@needs_panda
def test_cut_divides_the_bar_and_refuses_a_ball() -> None:
    knife = ObjectProfile(shape="box", width=0.02, depth=0.04, height=0.02)
    bar = ObjectProfile(shape="box", width=0.12, depth=0.05, height=0.04)
    layout = Layout(
        {"gray knife": (0.4, -0.15), "white bar": (0.5, 0.1)}, [], {"gray knife": knife, "white bar": bar}
    )
    program = TaskProgram(name="t", steps=[Step(object="gray knife", action="cut", target="white bar")])
    world = build_world(layout, program)
    execute(program, world, PandaController(world), [])
    assert all(c.ok for c in verify(program, world, []))

    ball_layout = Layout(
        {"gray knife": (0.4, -0.15), "red ball": (0.5, 0.1)},
        [],
        {"gray knife": knife, "red ball": ObjectProfile(shape="sphere", width=0.05, depth=0.05, height=0.05)},
    )
    bad = TaskProgram(name="t2", steps=[Step(object="gray knife", action="cut", target="red ball")])
    with pytest.raises(ExecutionError, match="round"):
        execute(bad, build_world(ball_layout, bad), PandaController(build_world(ball_layout, bad)), [])


@needs_panda
def test_press_latches_the_lamp_down() -> None:
    lamp = ObjectProfile(shape="cylinder", width=0.08, depth=0.08, height=0.03, pressable=True)
    layout = Layout({"orange lamp": (0.45, 0.0)}, [], {"orange lamp": lamp})
    program = TaskProgram(name="t", steps=[Step(object="orange lamp", action="press", target="orange lamp")])
    world = build_world(layout, program)
    execute(program, world, PandaController(world), [])
    assert all(c.ok for c in verify(program, world, []))


@needs_panda
def test_press_refuses_something_without_a_button() -> None:
    mug = ObjectProfile(shape="cylinder", width=0.064, depth=0.064, height=0.08, handle=True)
    layout = Layout({"red mug": (0.45, 0.0)}, [], {"red mug": mug})
    bad = TaskProgram(name="t", steps=[Step(object="red mug", action="press", target="red mug")])
    world = build_world(layout, bad)
    with pytest.raises(ExecutionError, match="press"):
        execute(bad, world, PandaController(world), [])
