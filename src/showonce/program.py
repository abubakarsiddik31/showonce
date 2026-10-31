"""The symbolic task program: object names and relations only, never pixel positions."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

Action = Literal["place_in", "stack_on"]


class Step(BaseModel):
    object: str
    action: Action
    target: str

    def __str__(self) -> str:
        verb = "put" if self.action == "place_in" else "stack"
        prep = "in" if self.action == "place_in" else "on"
        return f"{verb} {self.object} {prep} {self.target}"


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
