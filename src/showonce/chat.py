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


def clean_steps(
    steps: Sequence[Step], objects: Sequence[str], containers: Sequence[str]
) -> list[Step]:
    """Keep only steps that make sense on this table, and fix what is obviously off."""
    known = set(objects)
    out: list[Step] = []
    for step in steps:
        if step.object not in known:
            continue
        if step.action == "open":
            out.append(Step(object=step.object, action="open", target=step.object))
        elif (
            (step.action == "place_in" and step.target in containers)
            or (step.action == "stack_on" and step.target in known and step.target != step.object)
            or (
                step.action == "wipe"
                and step.target != step.object
                and (step.target in known or step.target in containers)
            )
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
