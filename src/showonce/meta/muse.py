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
                            ],
                        },
                        # Strict schemas must list every key as required, so "no relation" is null.
                        "relation": {
                            "type": ["string", "null"],
                            "enum": [
                                "next_to",
                                "left_of",
                                "right_of",
                                "in_front_of",
                                "behind",
                                None,
                            ],
                        },
                        "target": {"type": "string", "enum": [*objects, *containers]},
                    },
                    "required": ["object", "action", "relation", "target"],
                    "additionalProperties": False,
                },
            }
        },
        "required": ["steps"],
        "additionalProperties": False,
    }


TIDY_ACTIONS = ("place_in", "stack_on", "place_near", "push")
TIDY_PROMPT = """\
This picture is of a messy table, seen from above. A robot arm with one gripper will tidy it.
Objects, with their positions on the table in centimetres (x grows away from the robot, which
is toward the top of the picture; y grows toward the left of the picture):
{objects}
Containers (they cannot be moved): {containers}.
Goal: {goal}

Plan the fewest steps that leave the table tidy. Each step is one of:
  "place_in": put an object into a container
  "stack_on": put an object on top of a flat-topped object (never on a round one)
  "place_near": set an object on the table beside another object; relation says on which side,
    from the picture's point of view: next_to, left_of, right_of, in_front_of (toward the bottom
    of the picture) or behind (toward the top)
  "push": slide something too wide to lift into a container or beside another object
Rules: move each object at most once. Never move an object after something is stacked on it.
Leave alone anything that is already tidy. Group things that belong together. Use only the
names listed above."""


def tidy_schema(objects: Sequence[str], containers: Sequence[str]) -> dict[str, Any]:
    """The step schema, limited to the actions a tidy-up can use."""
    schema = step_schema(objects, containers)
    schema["properties"]["steps"]["items"]["properties"]["action"]["enum"] = list(TIDY_ACTIONS)
    return schema


def tidy_request(
    model: str,
    image_url: str,
    goal: str,
    positions: dict[str, tuple[float, float]],
    containers: Sequence[str],
) -> dict[str, Any]:
    objects = "\n".join(
        f"- {name}: x {x * 100:.0f}, y {y * 100:.0f}" for name, (x, y) in positions.items()
    )
    prompt = TIDY_PROMPT.format(
        objects=objects, containers=", ".join(containers) or "none", goal=goal
    )
    return _image_request(
        model, image_url, prompt, "tidy_plan", tidy_schema(list(positions), containers)
    )


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
You are a one-armed robot learning a tabletop task by watching a person's video, and you are talking
to that person. Speak like a thoughtful colleague: plain, warm and short. Never number things,
never read out a list of steps, and never mention JSON, schemas or "the plan".

What you can do: put something in a container, stack something on something, put something beside
something, push something along the table, wipe a dish or surface with a sponge or cloth, open a
sealed bag or packet, pour a cup into a container, stir a container with a spoon, cut something
with a knife, and press a button.

Objects on the table: {objects}.
Containers: {containers}.

What you currently understand, written as steps for your own reference (do not read them out):
{plan}
In the steps, "object" is the thing moved or the tool, and "target" is what it ends up in, on or
beside, or what is cleaned, stirred or cut. For "open" and "press" the target is the same as the
object. "relation" is only for putting something beside something and for pushing.

The conversation so far:
{conversation}

Now reply to the person's last message:
- If they correct or add something, change the steps to match (only the objects and containers
  above), then say back in one or two sentences what you now understand and ask if that is right.
- If something is unclear, ask ONE short question instead of guessing, and leave the steps alone.
- If they ask a question, answer it briefly and leave the steps alone.
- If they approve ("yes", "that's right", "go ahead"), set confirmed to true and say you are ready.
- If they ask for something you cannot do, say so plainly and leave the steps alone."""

NARRATE_PROMPT = """\
You are a one-armed robot. You have just watched this short clip of a person doing a task on a
table. For your own reference, here is what you worked out they did, as steps (do not read them
out): {plan}

Tell the person what you understood, in your own words, the way you would to a friend: two to four
short sentences, in the first person ("I saw you ..."). Say what the goal seemed to be. No numbered
lists and no technical words. End by asking whether you got it right."""


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


def narrate_request(model: str, file_id: str, plan: Sequence[Step]) -> dict[str, Any]:
    """Ask for a plain-language account of what the clip showed, grounded in the plan."""
    text = NARRATE_PROMPT.format(plan="; ".join(str(s) for s in plan) or "none")
    return {
        "model": model,
        "input": [
            {
                "type": "message",
                "role": "user",
                "content": [
                    {"type": "input_text", "text": text},
                    {"type": "input_video", "file_id": file_id},
                ],
            }
        ],
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
