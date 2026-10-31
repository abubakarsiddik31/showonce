"""Muse Spark: read a demo clip into a structured step list."""

from __future__ import annotations

import json
from collections.abc import Sequence
from typing import Any

from showonce.program import Step

PROMPT = """\
This clip is filmed from above. A person moves objects on a table with one hand.
Objects: {objects}.
Containers: {containers}.
List every completed move in the order it happens. For each move give:
- object: the object that was moved
- action: "place_in" if it ended inside a container, "stack_on" if it ended on top of another object
- target: the container or object it ended in or on
Only list moves that actually happened. Do not invent moves."""


def step_schema(objects: Sequence[str], containers: Sequence[str]) -> dict[str, Any]:
    """JSON schema for the answer, with object and target names restricted to the scene."""
    return {
        "type": "object",
        "properties": {
            "steps": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "object": {"type": "string", "enum": list(objects)},
                        "action": {"type": "string", "enum": ["place_in", "stack_on"]},
                        "target": {"type": "string", "enum": [*objects, *containers]},
                    },
                    "required": ["object", "action", "target"],
                    "additionalProperties": False,
                },
            }
        },
        "required": ["steps"],
        "additionalProperties": False,
    }


def build_request(
    model: str, file_id: str, objects: Sequence[str], containers: Sequence[str]
) -> dict[str, Any]:
    prompt = PROMPT.format(objects=", ".join(objects), containers=", ".join(containers) or "none")
    return {
        "model": model,
        "input": [
            {
                "type": "message",
                "role": "user",
                "content": [
                    {"type": "input_text", "text": prompt},
                    {"type": "input_video", "file_id": file_id},
                ],
            }
        ],
        "text": {
            "format": {
                "type": "json_schema",
                "name": "task_steps",
                "schema": step_schema(objects, containers),
                "strict": True,
            }
        },
    }


def response_text(payload: dict[str, Any]) -> str:
    """Pull the model's text out of a Responses API result."""
    if isinstance(payload.get("output_text"), str):
        return str(payload["output_text"])
    chunks = [
        part["text"]
        for item in payload.get("output", [])
        if item.get("type") == "message"
        for part in item.get("content", [])
        if part.get("type") == "output_text"
    ]
    if not chunks:
        raise ValueError(f"No text in Muse Spark response: {json.dumps(payload)[:300]}")
    return "".join(chunks)


def parse_steps(text: str) -> list[Step]:
    data = json.loads(text)
    return [Step.model_validate(item) for item in data["steps"]]
