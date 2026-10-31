import pytest

from showonce.learn import LearnError, classify_move, learn_program
from showonce.perception.moves import Move, Rest
from showonce.scene_spec import ContainerSpec

BOX = ContainerSpec(name="box", center=(1000.0, 360.0), size=(240.0, 280.0))


def rest(frame: int, x: float, y: float) -> Rest:
    return Rest(frame, frame + 30, (x, y))


def test_move_inside_container_is_place_in() -> None:
    move = Move("red block", 40, 90, (200, 200), (1010, 340))
    step = classify_move(move, {}, [BOX])
    assert (step.action, step.target) == ("place_in", "box")


def test_move_onto_another_object_is_stack_on() -> None:
    move = Move("red cup", 40, 90, (200, 200), (400, 400))
    rests = {"blue cup": [rest(0, 402, 398)], "red cup": [rest(0, 200, 200), rest(90, 400, 400)]}
    step = classify_move(move, rests, [])
    assert (step.action, step.target) == ("stack_on", "blue cup")


def test_stack_picks_topmost_object() -> None:
    first = Move("red cup", 40, 90, (200, 200), (400, 400))
    second = Move("green cup", 140, 190, (600, 200), (400, 400))
    rests = {
        "blue cup": [rest(0, 400, 400)],
        "red cup": [rest(0, 200, 200), rest(90, 400, 400)],
        "green cup": [rest(0, 600, 200), rest(190, 400, 400)],
    }
    program = learn_program("t", [first, second], rests, [])
    assert [(s.object, s.target) for s in program.steps] == [
        ("red cup", "blue cup"),
        ("green cup", "red cup"),
    ]


def test_unexplained_move_raises() -> None:
    move = Move("red block", 40, 90, (200, 200), (600, 600))
    with pytest.raises(LearnError):
        classify_move(move, {}, [BOX])
