import pytest

from showonce.objects import ObjectProfile
from showonce.program import Step, TaskProgram
from showonce.sim.executor import contents_for
from showonce.sim.scene import DEFAULT_ASSET_DIR, SimWorld, ZoneDef, block_def
from showonce.sim.stack_test import run_stack_test

pytestmark = pytest.mark.skipif(
    not (DEFAULT_ASSET_DIR / "panda.xml").exists(),
    reason="Panda model missing; run scripts/fetch_assets.sh",
)

needs_panda = pytest.mark.skipif(
    not (DEFAULT_ASSET_DIR / "panda.xml").exists(),
    reason="Panda model missing; run scripts/fetch_assets.sh",
)


def test_blocks_settle_on_table() -> None:
    world = SimWorld([block_def("red a")])
    world.set_block("red a", (0.5, 0.1))
    world.step(500)
    x, y, z = world.block_pos("red a")
    assert (round(x, 3), round(y, 3)) == (0.5, 0.1)
    assert abs(z - 0.02) < 1e-3


def test_stack_succeeds_from_random_layouts() -> None:
    results = run_stack_test(runs=3, seed=1)
    assert all(r.ok for r in results), results


@needs_panda
def test_contents_pour_from_the_cup_into_the_bowl() -> None:
    cup = block_def("red cup", ObjectProfile(shape="cylinder", width=0.06, depth=0.06, height=0.08))
    world = SimWorld(
        [cup], [ZoneDef("bowl", (0.4, 0.1), (0.16, 0.16))],
        contents=["red cup"], pour_targets=["bowl"],
    )
    assert world.contents_of("red cup") is not None and world.contents_of("bowl") is None
    world.pour_into("red cup", "bowl")
    assert world.contents_of("red cup") is None and world.contents_of("bowl") is not None


@needs_panda
def test_a_stirred_bowl_is_marked_mixed() -> None:
    bowl = ZoneDef("bowl", (0.4, 0.1), (0.16, 0.16))
    world = SimWorld([], [bowl], contents=["bowl"])
    assert not world.is_mixed("bowl")
    world.stir("bowl")
    assert world.is_mixed("bowl")


def test_contents_for_the_program_from_its_pour_and_stir_steps() -> None:
    program = TaskProgram(
        name="t",
        steps=[
            Step(object="red cup", action="pour", target="bowl"),
            Step(object="yellow spoon", action="stir", target="bowl"),
        ],
    )
    full, targets = contents_for(program)
    assert full == {"red cup", "bowl"} and targets == {"bowl"}
