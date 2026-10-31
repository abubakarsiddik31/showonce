"""Description of what is in a demo clip: object prompts and container rectangles (pixels).

The ground-truth json written by the synthetic generator already follows this schema, and
real clips can use a hand-written file of the same shape.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field

from showonce.objects import ObjectProfile, profile_from_name, sim_prompt


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
    sim_prompts: dict[str, str] | None = None  # override the prompts used to find sim objects
    profiles: dict[str, ObjectProfile] = Field(default_factory=dict)  # filled in when learning
    containers: list[ContainerSpec] = Field(default_factory=list)
    # Containers located by SAM on the clip's first frame: name -> prompt (e.g. "gray tray").
    container_prompts: dict[str, str] = Field(default_factory=dict)
    size: tuple[int, int] | None = None

    model_config = {"extra": "ignore"}

    def profile(self, name: str) -> ObjectProfile:
        return self.profiles.get(name) or profile_from_name(name)

    @property
    def prompts_for_sim(self) -> dict[str, str]:
        """How SAM finds each object in the simulator, where it is a plain primitive."""
        return self.sim_prompts or {n: sim_prompt(n, self.profile(n)) for n in self.prompts}

    @classmethod
    def load(cls, path: Path) -> SceneSpec:
        return cls.model_validate_json(path.read_text())
