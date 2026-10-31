"""The symbolic task program: object names and relations only, never pixel positions."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

Action = Literal["place_in", "stack_on", "wipe", "open"]

# Actions that geometry (where things ended up) cannot tell apart from a plain move: the
# video has to be understood. A wipe slides a tool over something, an open tears it apart.
SEMANTIC_ACTIONS: frozenset[str] = frozenset({"wipe", "open"})


class Step(BaseModel):
    """What happens to ``object``.

    - place_in / stack_on: ``object`` ends up in / on ``target``.
    - wipe: ``object`` is a tool (sponge, cloth) rubbed over ``target`` to clean it.
    - open: ``object`` is a packet, bag or box that gets torn open. ``target`` is ``object``.
    """

    object: str
    action: Action
    target: str

    def __str__(self) -> str:
        match self.action:
            case "place_in":
                return f"put {self.object} in {self.target}"
            case "stack_on":
                return f"stack {self.object} on {self.target}"
            case "wipe":
                return f"wipe {self.target} with {self.object}"
            case "open":
                return f"open {self.object}"


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
