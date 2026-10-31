import pytest

from showonce.program import Step, TaskProgram
from showonce.sim.controller import PandaController
from showonce.sim.executor import Layout, Region, build_world, execute, verify
from showonce.sim.scene import DEFAULT_ASSET_DIR

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
