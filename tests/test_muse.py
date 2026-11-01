import json

import pytest

from showonce.learn import compare_plans
from showonce.meta.muse import PROMPT, build_request, parse_steps, response_text, step_schema
from showonce.program import Step


def step(obj: str, action: str, target: str) -> Step:
    return Step(object=obj, action=action, target=target)  # type: ignore[arg-type]


def test_schema_restricts_names_to_the_scene() -> None:
    schema = step_schema(["red block"], ["box"])
    props = schema["properties"]["steps"]["items"]["properties"]
    assert props["object"]["enum"] == ["red block"]
    assert props["target"]["enum"] == ["red block", "box"]


def test_request_uses_structured_output_and_video() -> None:
    body = build_request("muse-spark-1.3", "file-1", ["red block"], ["box"])
    assert body["text"]["format"]["type"] == "json_schema"
    assert body["input"][0]["content"][1] == {"type": "input_video", "file_id": "file-1"}


def test_response_text_reads_output_items() -> None:
    payload = {"output": [{"type": "message", "content": [{"type": "output_text", "text": "{}"}]}]}
    assert response_text(payload) == "{}"
    with pytest.raises(ValueError):
        response_text({"output": []})


def test_parse_steps() -> None:
    text = json.dumps({"steps": [{"object": "a", "action": "place_in", "target": "box"}]})
    assert parse_steps(text) == [step("a", "place_in", "box")]


def test_step_schema_knows_all_ten_actions_and_the_relation() -> None:
    schema = step_schema(["red cup"], ["bowl"])
    item = schema["properties"]["steps"]["items"]
    assert set(item["properties"]["action"]["enum"]) == {
        "place_in",
        "stack_on",
        "wipe",
        "open",
        "place_near",
        "push",
        "pour",
        "stir",
        "cut",
        "press",
    }
    assert item["properties"]["relation"]["enum"] == [
        "next_to",
        "left_of",
        "right_of",
        "in_front_of",
        "behind",
        None,
    ]
    # The API's strict mode rejects a schema unless every property is required.
    assert set(item["required"]) == set(item["properties"])


def test_a_null_relation_reads_as_no_relation() -> None:
    steps = parse_steps(
        '{"steps":[{"object":"a","action":"place_in","relation":null,"target":"box"}]}'
    )
    assert steps[0].relation is None


def test_prompt_names_every_action() -> None:
    for action in ("place_near", "push", "pour", "stir", "cut", "press"):
        assert f'"{action}"' in PROMPT


def test_compare_plans_reports_differences() -> None:
    a = [step("a", "place_in", "box")]
    assert compare_plans(a, list(a)) == []
    assert len(compare_plans(a, [step("a", "stack_on", "b")])) == 1
    assert "count" in compare_plans(a, [])[0]
