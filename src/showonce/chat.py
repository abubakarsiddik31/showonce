"""Talking a learned plan through with the person who taught it.

The robot says what it understood, the person corrects it in plain words, and the plan is
revised until they confirm. The model's answers are checked here: a plan may only name objects
and containers that are really on the table.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass

from showonce.meta.client import MetaAPIError, MetaClient
from showonce.program import Step

log = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class Turn:
    """The robot's side of one exchange."""

    reply: str
    steps: list[Step]
    confirmed: bool = False


def how_it_will_do(step: Step) -> str:
    """In plain words, how the robot will do a step. It does it its own way, not the hand's."""
    match step.action:
        case "place_in":
            return f"I'll pick up the {step.object} and set it down inside the {step.target}."
        case "stack_on":
            return f"I'll pick up the {step.object} and set it on top of the {step.target}."
        case "wipe":
            return (
                f"I'll scrub the {step.target} with the {step.object}, my own way, "
                "until it is clean."
            )
        case "open":
            return f"I'll take hold of the seal on the {step.object}, tear it off and lay it aside."
        case "place_near":
            relation = step.relation or "next_to"
            rel = "beside" if relation == "next_to" else relation.replace("_", " ")
            return f"I'll pick up the {step.object} and set it down {rel} the {step.target}."
        case "push":
            push_rel = step.relation.replace("_", " ") if step.relation else None
            where = f"{push_rel} the {step.target}" if push_rel else f"into the {step.target}"
            return (
                f"I'll put my fingers behind the {step.object} and push it {where}, "
                "without lifting it."
            )
        case "pour":
            return (
                f"I'll hold the {step.object} over the {step.target} and pour, "
                "tipping it until it is empty."
            )
        case "stir":
            return (
                f"I'll stir the {step.target} round and round with the {step.object} "
                "until it is mixed."
            )
        case "cut":
            return (
                f"I'll draw the {step.object} across the {step.target}, cut it through, "
                "and lay the two halves flat."
            )
        case "press":
            return f"I'll press the {step.object} straight down, once and firmly."


def clean_steps(
    steps: Sequence[Step], objects: Sequence[str], containers: Sequence[str]
) -> list[Step]:
    """Keep only steps that make sense on this table, and fix what is obviously off."""
    known = set(objects)
    out: list[Step] = []
    for step in steps:
        if step.object not in known:
            continue
        if step.action in ("open", "press"):
            out.append(Step(object=step.object, action=step.action, target=step.object))
        elif (
            (step.action == "place_in" and step.target in containers)
            or (step.action == "stack_on" and step.target in known and step.target != step.object)
            or (
                step.action == "wipe"
                and step.target != step.object
                and (step.target in known or step.target in containers)
            )
            or (step.action == "place_near" and step.target in known and step.target != step.object)
            or (
                step.action == "push"
                and (
                    step.target in containers
                    or (step.target in known and step.target != step.object)
                )
            )
            or (step.action == "pour" and step.target in containers)
            or (step.action == "stir" and step.target in containers and step.target != step.object)
            or (step.action == "cut" and step.target in known and step.target != step.object)
        ):
            out.append(step)
    return out


def talk(
    client: MetaClient,
    objects: list[str],
    containers: list[str],
    plan: list[Step],
    conversation: list[tuple[str, str]],
) -> Turn:
    """One turn: answer the person's last message, revising the plan if they asked."""
    try:
        data = client.chat(objects, containers, plan, conversation)
        reply = str(data["reply"]).strip()
        proposed = [Step.model_validate(s) for s in data["steps"]]
        confirmed = bool(data["confirmed"])
    except (MetaAPIError, ValueError, KeyError, TypeError) as exc:
        log.warning("Chat turn failed: %s", exc)
        return Turn("Sorry, I did not catch that. Could you say it another way?", plan)
    steps = clean_steps(proposed, objects, containers)
    if proposed and not steps:  # everything the model proposed was nonsense: keep what we had
        return Turn(reply + " (I could not make that into steps, so the plan is unchanged.)", plan)
    return Turn(reply, steps, confirmed)


def describe_plan(steps: Sequence[Step]) -> str:
    """A plain account of a plan, for when Muse Spark cannot put it in its own words."""
    if not steps:
        return (
            "I watched your clip but could not make out a clear task. "
            "Could you tell me what you did, in your own words?"
        )
    said = ", then ".join(str(s) for s in steps)
    return f"I saw you {said}. Did I get that right?"


def understand(client: MetaClient, video_id: str, steps: Sequence[Step]) -> str:
    """The robot's own account of the clip, falling back to a plain sentence from the steps."""
    try:
        text = client.narrate(video_id, list(steps))
    except (MetaAPIError, ValueError, KeyError) as exc:
        log.warning("Could not narrate the clip: %s", exc)
        return describe_plan(steps)
    return text or describe_plan(steps)
