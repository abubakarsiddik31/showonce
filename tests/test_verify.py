"""SAM-based verification and the one corrective retry, with the camera stood in by the sim."""

import pytest

from showonce.program import Step, TaskProgram
from showonce.replay import replay, shuffled_layout, slip_spot
from showonce.scene_spec import ContainerSpec, SceneSpec
from showonce.sim.controller import PandaController
from showonce.sim.executor import Layout, Region, build_world, execute
from showonce.sim.scene import DEFAULT_ASSET_DIR, SimWorld
from showonce.verify import fix_misses, verify_with_sam

needs_panda = pytest.mark.skipif(
    not (DEFAULT_ASSET_DIR / "panda.xml").exists(), reason="Panda model missing"
)

XY = tuple[float, float]


def camera(world: SimWorld):  # type: ignore[no-untyped-def]
    """A perfect stand-in for SAM: report where the objects really are."""

    def look(names: list[str]) -> dict[str, XY]:
        return {n: (float(world.block_pos(n)[0]), float(world.block_pos(n)[1])) for n in names}

    return look


def setup(steps: list[Step]):  # type: ignore[no-untyped-def]
    region = Region("box", (0.47, -0.16), (0.14, 0.14))
    names = ["red block", "blue block"]
    truth = shuffled_layout(names, [region], seed=2)
    program = TaskProgram(name="t", steps=steps)
    world = build_world(Layout(truth, [region]), program)
    controller = PandaController(world)
    return program, world, controller, [region], names


@needs_panda
def test_a_finished_table_passes_without_a_retry() -> None:
    program, world, controller, regions, names = setup(
        [Step(object="red block", action="place_in", target="box")]
    )
    execute(program, world, controller, regions)
    report = fix_misses(program, world, controller, regions, camera(world), names)
    assert not report.missed and report.retried == []
    assert report.before[0].detail.startswith("SAM:")


@needs_panda
def test_a_slipped_object_is_seen_and_put_back() -> None:
    program, world, controller, regions, names = setup(
        [Step(object="red block", action="place_in", target="box")]
    )
    execute(program, world, controller, regions)
    world.set_block("red block", slip_spot(world, regions, "red block", seed=1))
    report = fix_misses(program, world, controller, regions, camera(world), names)
    assert report.missed and not report.before[0].ok
    assert report.retried == [str(program.steps[0])]
    assert report.fixed and report.after[0].ok


@needs_panda
def test_a_step_a_picture_cannot_show_falls_back_to_the_simulator() -> None:
    program, world, _controller, regions, _ = setup(
        [Step(object="red block", action="press", target="red block")]
    )
    checks, _ = verify_with_sam(program, world, regions, camera(world))
    assert checks[0].detail.startswith("sim:")


@needs_panda
def test_replay_stages_a_slip_and_oracle_still_reports_truth() -> None:
    scene = SceneSpec(
        name="t",
        prompts={"red block": "red block", "blue block": "blue block"},
        containers=[ContainerSpec(name="box", center=(1030, 360), size=(240, 280))],
        size=(1280, 720),
    )
    program = TaskProgram(
        name="t", steps=[Step(object="red block", action="place_in", target="box")]
    )
    assert not replay(None, program, scene, seed=2, oracle=True, slip="red block").success


@needs_panda
def test_a_covered_block_is_not_judged_from_above() -> None:
    steps = [
        Step(object="red block", action="stack_on", target="blue block"),
        Step(object="blue block", action="place_in", target="box"),
    ]
    program, world, controller, regions, names = setup(steps[:1])
    execute(program, world, controller, regions)

    def blind(wanted: list[str]) -> dict[str, XY]:
        assert "blue block" not in wanted, "nothing should ask the camera for a hidden block"
        return camera(world)(wanted)

    start = {n: (float(world.block_pos(n)[0]), float(world.block_pos(n)[1])) for n in names}
    checks, _ = verify_with_sam(program, world, regions, blind, start)
    assert checks[0].ok and checks[0].detail.startswith("SAM:")
    covered_step = TaskProgram(name="t", steps=steps)
    checks, _ = verify_with_sam(covered_step, world, regions, blind, start)
    assert checks[1].detail.startswith("sim:")
