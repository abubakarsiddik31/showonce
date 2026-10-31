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
  "place_near": an object ended up on the table beside another object, not in or on it
  "push": an object was slid across the table without ever being lifted
  "pour": a cup or bottle was tipped so its contents went into a container
  "stir": a spoon or tool was stirred round and round through a container's contents
  "cut": something was cut into two pieces with a knife
  "press": a button, pump or push-light was pressed straight down
- object: the object that was moved; for "wipe" the cleaning tool; for "open" the thing opened;
  for "pour" the cup poured; for "stir" the spoon; for "cut" the knife; for "push" the thing slid
- target: for "place_in" the container, for "stack_on" the object underneath, for "wipe" the
  thing being cleaned, for "open" the same as object, for "place_near" the object it ended up
  beside, for "push" where it was pushed to (container or object), for "pour" the container
  poured into, for "stir" the container stirred, for "cut" the thing cut, for "press" the
  same as object
- relation: only for "place_near" (and "push" toward an object): one of "next_to", "left_of",
  "right_of", "in_front_of", "behind", from the camera's point of view
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
                            "enum": [
                                "place_in", "stack_on", "wipe", "open",
                                "place_near", "push", "pour", "stir", "cut", "press",
                            ],
                        },
                        "relation": {
                            "type": "string",
                            "enum": ["next_to", "left_of", "right_of", "in_front_of", "behind"],
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
- pressable: true only if it is a button, pump or push-light (something you press straight down)
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


SCENE_PROMPT = """\
This photo is of a table, seen from above, at the start of a short clip in which a person does a
task with their hands. List what is on the table:
- objects: every separate thing a person could pick up or work on (not the hand, the table or
  the background)
- containers: an empty tray, bowl, box, rack, basket or bin that is there to hold other things.
  A plate, dish, mug or cup is an object, not a container, and so is anything that looks used,
  stained or dirty.
Give each a short name of at most three words that includes its colour, such as "red mug" or
"white plate". Every name must be different, so tell look-alikes apart by colour or position.
For each also give "find": a short phrase for finding it again in a photo, usually its name."""


def scene_schema() -> dict[str, Any]:
    """JSON schema for what is on the table."""
    thing = {
        "type": "object",
        "properties": {"name": {"type": "string"}, "find": {"type": "string"}},
        "required": ["name", "find"],
        "additionalProperties": False,
    }
    return {
        "type": "object",
        "properties": {
            "objects": {"type": "array", "items": thing},
            "containers": {"type": "array", "items": thing},
        },
        "required": ["objects", "containers"],
        "additionalProperties": False,
    }


def scene_request(model: str, image_url: str) -> dict[str, Any]:
    return _image_request(model, image_url, SCENE_PROMPT, "table_contents", scene_schema())


CHAT_PROMPT = """\
You are teaching a one-armed robot a tabletop task. The person showed it a video, and the robot
wrote down what it thinks they did, as a plan. You are the robot, talking to the person.

Objects on the table: {objects}.
Containers: {containers}.
Each plan step is one of:
- place_in: an object ends up inside a container (target is the container)
- stack_on: an object ends up on top of another object (target is that object)
- wipe: a sponge or cloth is rubbed over something to clean it (object is the tool, target is
  the thing cleaned)
- open: a sealed bag or packet is torn open (target is the same as object)

The plan as it stands:
{plan}

The conversation so far:
{conversation}

Reply to the person's last message. If they correct or add something, change the plan to match,
using only the objects and containers above. If they ask a question, answer it and leave the plan
alone. If they say the plan is right ("yes", "that's right", "go ahead"), set confirmed to true.
Keep reply to one to three short, plain sentences, say what you changed, and never mention
JSON or schemas."""


def chat_schema(objects: Sequence[str], containers: Sequence[str]) -> dict[str, Any]:
    """JSON schema for a reply: what to say, the revised plan, and whether it was confirmed."""
    schema = step_schema(objects, containers)
    return {
        "type": "object",
        "properties": {
            "reply": {"type": "string"},
            "steps": schema["properties"]["steps"],
            "confirmed": {"type": "boolean"},
        },
        "required": ["reply", "steps", "confirmed"],
        "additionalProperties": False,
    }


def chat_request(
    model: str,
    objects: Sequence[str],
    containers: Sequence[str],
    plan: Sequence[Step],
    conversation: Sequence[tuple[str, str]],
) -> dict[str, Any]:
    """``conversation`` is (speaker, text) pairs, speaker being "person" or "robot"."""
    prompt = CHAT_PROMPT.format(
        objects=", ".join(objects) or "none",
        containers=", ".join(containers) or "none",
        plan="\n".join(f"{i}. {s}" for i, s in enumerate(plan, 1)) or "(empty)",
        conversation="\n".join(f"{who}: {text}" for who, text in conversation),
    )
    return {
        "model": model,
        "input": [
            {"type": "message", "role": "user", "content": [{"type": "input_text", "text": prompt}]}
        ],
        "text": {
            "format": {
                "type": "json_schema",
                "name": "robot_reply",
                "schema": chat_schema(objects, containers),
                "strict": True,
            }
        },
    }


def _image_request(
    model: str, image_url: str, prompt: str, name: str, schema: dict[str, Any]
) -> dict[str, Any]:
    return {
        "model": model,
        "input": [
            {
                "type": "message",
                "role": "user",
                "content": [
                    {"type": "input_text", "text": prompt},
                    {"type": "input_image", "image_url": image_url},
                ],
            }
        ],
        "text": {"format": {"type": "json_schema", "name": name, "schema": schema, "strict": True}},
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
