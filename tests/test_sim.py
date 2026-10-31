import pytest

from showonce.sim.scene import DEFAULT_ASSET_DIR, BlockDef, SimWorld
from showonce.sim.stack_test import run_stack_test

pytestmark = pytest.mark.skipif(
    not (DEFAULT_ASSET_DIR / "panda.xml").exists(),
    reason="Panda model missing; run scripts/fetch_assets.sh",
)


def test_blocks_settle_on_table() -> None:
    world = SimWorld([BlockDef("a", (1, 0, 0, 1))])
    world.set_block("a", (0.5, 0.1))
    world.step(500)
    x, y, z = world.block_pos("a")
    assert (round(x, 3), round(y, 3)) == (0.5, 0.1)
    assert abs(z - 0.02) < 1e-3


def test_stack_succeeds_from_random_layouts() -> None:
    results = run_stack_test(runs=3, seed=1)
    assert all(r.ok for r in results), results
