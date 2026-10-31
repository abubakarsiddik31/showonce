import json

import pytest

from showonce.learn import compare_plans
from showonce.meta.muse import build_request, parse_steps, response_text, step_schema
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


def test_compare_plans_reports_differences() -> None:
    a = [step("a", "place_in", "box")]
    assert compare_plans(a, list(a)) == []
    assert len(compare_plans(a, [step("a", "stack_on", "b")])) == 1
    assert "count" in compare_plans(a, [])[0]
