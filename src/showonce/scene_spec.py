"""Description of what is in a demo clip: object prompts and container rectangles (pixels).

The ground-truth json written by the synthetic generator already follows this schema, and
real clips can use a hand-written file of the same shape.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field


class ContainerSpec(BaseModel):
    name: str
    center: tuple[float, float]
    size: tuple[float, float]

    def contains(self, point: tuple[float, float]) -> bool:
        return (
            abs(point[0] - self.center[0]) <= self.size[0] / 2
            and abs(point[1] - self.center[1]) <= self.size[1] / 2
        )


class SceneSpec(BaseModel):
    """Objects are listed as name -> SAM prompt. Names default to being their own prompt."""

    name: str = "task"
    prompts: dict[str, str]
    containers: list[ContainerSpec] = Field(default_factory=list)
    size: tuple[int, int] | None = None

    model_config = {"extra": "ignore"}

    @classmethod
    def load(cls, path: Path) -> SceneSpec:
        return cls.model_validate_json(path.read_text())
