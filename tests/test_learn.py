import pytest

from showonce.learn import LearnError, classify_move, learn_program
from showonce.perception.moves import Move, Rest
from showonce.program import Step
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


def test_repeat_move_into_same_container_is_dropped() -> None:
    first = Move("red block", 40, 90, (200, 200), (1010, 340))
    nudge = Move("red block", 200, 230, (1010, 340), (1040, 380))
    program = learn_program("t", [first, nudge], {}, [BOX])
    assert [str(s) for s in program.steps] == ["put red block in box"]


# The landing below must sit outside STACK_RADIUS_PX (45) of the blue block but inside
# NEAR_RADIUS_PX (90): inside the stack radius the move reads as stack_on, not place_near.
def test_move_to_open_table_becomes_place_near() -> None:
    moves = [
        Move(
            label="red block", start_frame=10, end_frame=40, src=(100.0, 100.0), dst=(260.0, 110.0)
        )
    ]
    rests = {
        "red block": [Rest(0, 10, (100.0, 100.0)), Rest(40, 90, (260.0, 110.0))],
        "blue block": [Rest(0, 90, (320.0, 100.0))],
    }
    program = learn_program("t", moves, rests, [])
    assert program.steps == [
        Step(object="red block", action="place_near", target="blue block", relation="left_of")
    ]


def test_place_near_relation_follows_the_dominant_axis() -> None:
    moves = [
        Move(
            label="red block", start_frame=10, end_frame=40, src=(100.0, 100.0), dst=(320.0, 160.0)
        )
    ]
    rests = {
        "red block": [Rest(0, 10, (100.0, 100.0)), Rest(40, 90, (320.0, 160.0))],
        "blue block": [Rest(0, 90, (320.0, 100.0))],
    }
    program = learn_program("t", moves, rests, [])
    assert program.steps[0].relation == "in_front_of"  # lower in frame, toward the person


def test_a_move_to_nowhere_still_fails() -> None:
    moves = [
        Move(
            label="red block", start_frame=10, end_frame=40, src=(100.0, 100.0), dst=(600.0, 500.0)
        )
    ]
    rests = {
        "red block": [Rest(0, 10, (100.0, 100.0)), Rest(40, 90, (600.0, 500.0))],
        "blue block": [Rest(0, 90, (320.0, 100.0))],
    }
    with pytest.raises(LearnError):
        learn_program("t", moves, rests, [])
