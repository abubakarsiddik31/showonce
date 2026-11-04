from showonce.program import Step, TaskProgram
from showonce.unposed import unposed_layout


def prog() -> TaskProgram:
    return TaskProgram(
        name="t",
        steps=[
            Step(object="steel knife", action="cut", target="carrot"),
            Step(object="red cup", action="pour", target="bowl"),
            Step(object="orange lamp", action="press", target="orange lamp"),
        ],
    )


def test_objects_come_from_steps_and_containers_become_regions() -> None:
    layout = unposed_layout(prog(), {}, ["bowl"])
    assert set(layout.objects) == {"steel knife", "carrot", "red cup", "orange lamp"}
    assert [r.name for r in layout.regions] == ["bowl"]


def test_everything_lands_inside_arm_reach() -> None:
    layout = unposed_layout(prog(), {}, ["bowl"])
    for x, y in layout.objects.values():
        assert 0.34 <= x <= 0.60 and -0.24 <= y <= 0.24
    for r in layout.regions:
        assert 0.34 <= r.center[0] <= 0.60 and -0.24 <= r.center[1] <= 0.24


def test_same_seed_gives_the_same_table() -> None:
    assert (
        unposed_layout(prog(), {}, ["bowl"], seed=3).objects
        == unposed_layout(prog(), {}, ["bowl"], seed=3).objects
    )
