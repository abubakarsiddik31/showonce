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
List every completed step in the order it happens. For each step give:
- action: one of
  "place_in": an object ended up inside a container
  "stack_on": an object ended up on top of another object
  "wipe": a sponge, cloth or brush was rubbed over a dish, surface or container to clean it
  "open": a sealed bag, packet or box was torn or opened
- object: the object that was moved; for "wipe" the cleaning tool; for "open" the thing opened
- target: for "place_in" the container, for "stack_on" the object underneath, for "wipe" the
  thing being cleaned, for "open" the same as object
Only list steps that actually happened. Do not invent steps."""


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
                        "action": {
                            "type": "string",
                            "enum": ["place_in", "stack_on", "wipe", "open"],
                        },
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


DESCRIBE_PROMPT = """\
This photo is of a table, seen from above at an angle. Describe each of these objects as a
simple physical primitive so a robot simulator can model it: {objects}.
For each give:
- shape: "box" (blocks, boxes, books, phones), "cylinder" (mugs, cups, cans, bottles, jars)
  or "sphere" (balls, round fruit)
- width_cm, depth_cm: its footprint seen from above, handles excluded
- height_cm: how tall it stands
- handle: true if it has a handle that sticks out sideways (a mug or cup)
- openable: true if it is a sealed bag, packet or box that gets opened (chips, a snack, cereal)
Use real-world sizes. A mug is about 8 cm wide and 9 cm tall."""


def describe_schema(objects: Sequence[str]) -> dict[str, Any]:
    """JSON schema for one primitive description per named object."""
    one = {
        "type": "object",
        "properties": {
            "shape": {"type": "string", "enum": ["box", "cylinder", "sphere"]},
            "width_cm": {"type": "number"},
            "depth_cm": {"type": "number"},
            "height_cm": {"type": "number"},
            "handle": {"type": "boolean"},
            "openable": {"type": "boolean"},
        },
        "required": ["shape", "width_cm", "depth_cm", "height_cm", "handle", "openable"],
        "additionalProperties": False,
    }
    return {
        "type": "object",
        "properties": {name: one for name in objects},
        "required": list(objects),
        "additionalProperties": False,
    }


def describe_request(model: str, image_url: str, objects: Sequence[str]) -> dict[str, Any]:
    return {
        "model": model,
        "input": [
            {
                "type": "message",
                "role": "user",
                "content": [
                    {
                        "type": "input_text",
                        "text": DESCRIBE_PROMPT.format(objects=", ".join(objects)),
                    },
                    {"type": "input_image", "image_url": image_url},
                ],
            }
        ],
        "text": {
            "format": {
                "type": "json_schema",
                "name": "object_shapes",
                "schema": describe_schema(objects),
                "strict": True,
            }
        },
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
