"""The symbolic task program: object names and relations only, never pixel positions."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

Action = Literal[
    "place_in", "stack_on", "wipe", "open", "place_near", "push", "pour", "stir", "cut", "press"
]
Relation = Literal["next_to", "left_of", "right_of", "in_front_of", "behind"]

# Actions that geometry (where things ended up) cannot tell apart from a plain move: the
# video has to be understood. A wipe slides a tool over something, an open tears it apart,
# a pour tips a cup, a stir circles a tool through a bowl, a cut divides, a press pushes
# straight down and changes nothing that rests.
SEMANTIC_ACTIONS: frozenset[str] = frozenset({"wipe", "open", "pour", "stir", "cut", "press"})


class Step(BaseModel):
    """What happens to ``object``.

    - place_in / stack_on: ``object`` ends up in / on ``target``.
    - place_near: ``object`` ends up on the table, ``relation`` says where around ``target``.
    - push: ``object`` is slid, not lifted, to ``target`` (a container, or an object + relation).
    - wipe: ``object`` is a tool (sponge, cloth) rubbed over ``target`` to clean it.
    - pour: ``object`` is a cup whose contents end up in the container ``target``.
    - stir: ``object`` is a spoon or tool stirred through the container ``target``.
    - cut: ``object`` is a knife; ``target`` ends up in two halves.
    - press: ``object`` is pressed straight down. ``target`` is ``object``.
    - open: ``object`` is a packet, bag or box that gets torn open. ``target`` is ``object``.
    """

    object: str
    action: Action
    target: str
    relation: Relation | None = None

    def __str__(self) -> str:
        rel = (self.relation or "next_to").replace("_", " ")
        match self.action:
            case "place_in":
                return f"put {self.object} in {self.target}"
            case "stack_on":
                return f"stack {self.object} on {self.target}"
            case "place_near":
                return f"put {self.object} {rel} {self.target}"
            case "push":
                to = rel if self.relation else "into"
                return f"push {self.object} {to} {self.target}"
            case "pour":
                return f"pour {self.object} into {self.target}"
            case "stir":
                return f"stir {self.target} with {self.object}"
            case "cut":
                return f"cut {self.target} with {self.object}"
            case "press":
                return f"press {self.object}"
            case "open":
                return f"open {self.object}"
            case "wipe":
                return f"wipe {self.target} with {self.object}"


class TaskProgram(BaseModel):
    """An ordered list of steps that stays valid on any layout of the same objects."""

    name: str
    steps: list[Step] = Field(default_factory=list)

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.model_dump_json(indent=2))

    @classmethod
    def load(cls, path: Path) -> TaskProgram:
        return cls.model_validate_json(path.read_text())
