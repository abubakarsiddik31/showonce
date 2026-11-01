"""Tidy mode: the plan is cleaned before anything moves, and a tidy-up runs end to end."""

import json
from pathlib import Path

import pytest

from showonce.meta.muse import tidy_request, tidy_schema
from showonce.program import Step
from showonce.scene_spec import SceneSpec
from showonce.sim.scene import DEFAULT_ASSET_DIR
from showonce.tidy import TidyError, clean_plan, run_tidy

needs_panda = pytest.mark.skipif(
    not (DEFAULT_ASSET_DIR / "panda.xml").exists(), reason="Panda model missing"
)

SCENE = Path(__file__).resolve().parent.parent / "samples" / "tidy_table.json"
OBJECTS = ["red block", "green block", "blue block", "red apple"]
BOXES = ["bowl"]


def step(obj: str, action: str, target: str, relation: str | None = None) -> Step:
    return Step.model_validate(
        {"object": obj, "action": action, "target": target, "relation": relation}
    )


def test_a_sound_plan_is_kept_whole() -> None:
    plan = [
        step("red block", "place_in", "bowl"),
        step("green block", "stack_on", "blue block"),
        step("red apple", "place_near", "blue block", "left_of"),
    ]
    kept, dropped = clean_plan(plan, OBJECTS, BOXES, round_objects={"red apple"})
    assert kept == plan and dropped == []


@pytest.mark.parametrize(
    ("bad", "reason"),
    [
        (step("red block", "pour", "bowl"), "not a tidy-up action"),
        (step("purple cube", "place_in", "bowl"), "no object"),
        (step("red block", "place_in", "blue block"), "not a container"),
        (step("red block", "stack_on", "red apple"), "round"),
        (step("red block", "place_near", "bowl"), "not an object"),
        (step("red block", "stack_on", "red block"), "onto itself"),
    ],
)
def test_steps_the_arm_cannot_do_are_dropped_with_a_reason(bad: Step, reason: str) -> None:
    kept, dropped = clean_plan([bad], OBJECTS, BOXES, round_objects={"red apple"})
    assert kept == [] and reason in dropped[0]


def test_an_object_moves_once_and_a_covered_object_stays_put() -> None:
    plan = [
        step("green block", "stack_on", "blue block"),
        step("green block", "place_in", "bowl"),
        step("blue block", "place_in", "bowl"),
    ]
    kept, dropped = clean_plan(plan, OBJECTS, BOXES)
    assert kept == plan[:1]
    assert "already moved" in dropped[0] and "stacked on it" in dropped[1]


def test_the_request_lists_positions_and_only_tidy_actions() -> None:
    body = tidy_request(
        "m", "data:image/png;base64,x", "pack away", {"red block": (0.45, -0.1)}, ["bowl"]
    )
    text = json.dumps(body)
    assert "red block: x 45, y -10" in text and "pack away" in text
    actions = tidy_schema(["a"], ["bowl"])["properties"]["steps"]["items"]["properties"]["action"]
    assert actions["enum"] == ["place_in", "stack_on", "place_near", "push"]


@needs_panda
def test_tidy_runs_a_plan_end_to_end_and_every_step_checks() -> None:
    scene = SceneSpec.load(SCENE)

    def planner(png, goal, positions, containers):  # type: ignore[no-untyped-def]
        assert png[:4] == b"\x89PNG" and set(positions) == set(scene.prompts)
        return [
            step("red block", "place_in", "bowl"),
            step("green block", "place_in", "bowl"),
            step("blue block", "place_near", "red apple", "next_to"),
            step("ghost", "place_in", "bowl"),
        ]

    result = run_tidy(None, scene, seed=2, oracle=True, planner=planner)  # type: ignore[arg-type]
    assert result.success and len(result.checks) == 3
    assert len(result.dropped) == 1 and "ghost" in result.dropped[0]


@needs_panda
def test_an_empty_plan_is_an_error_not_a_pass() -> None:
    scene = SceneSpec.load(SCENE)
    with pytest.raises(TidyError):
        run_tidy(None, scene, seed=1, oracle=True, planner=lambda *_: [])  # type: ignore[arg-type]
