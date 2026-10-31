import itertools

import pytest

from showonce.demo import fit_profiles
from showonce.objects import ObjectProfile
from showonce.program import Step, TaskProgram
from showonce.sim.controller import PandaController
from showonce.sim.executor import ExecutionError, Layout, build_world, execute, verify
from showonce.sim.scene import DEFAULT_ASSET_DIR
from showonce.sim.skills import wipe_path

needs_panda = pytest.mark.skipif(
    not (DEFAULT_ASSET_DIR / "panda.xml").exists(), reason="Panda model missing"
)

PLATE = ObjectProfile(shape="cylinder", width=0.13, depth=0.13, height=0.02)
SPONGE = ObjectProfile(shape="box", width=0.06, depth=0.04, height=0.025)
CHIPS = ObjectProfile(shape="box", width=0.09, depth=0.04, height=0.16, openable=True)


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
    assert world.block_pos("red chips")[2] == pytest.approx(0.08, abs=0.005)  # still upright


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
