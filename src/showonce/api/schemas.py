"""Request and response models for the web API (camelCase JSON for the TypeScript client)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

JobStatus = Literal["queued", "running", "done", "failed"]
JobKind = Literal["learn", "run"]
Action = Literal[
    "place_in", "stack_on", "wipe", "open", "place_near", "push", "pour", "stir", "cut", "press"
]
Relation = Literal["next_to", "left_of", "right_of", "in_front_of", "behind"]


class ApiModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class SampleOut(ApiModel):
    id: str
    name: str
    video_url: str
    objects: list[str]
    containers: list[str]
    duration_s: float


class StepModel(ApiModel):
    object: str
    action: Action
    target: str
    relation: Relation | None = None
    text: str = ""
    how: str = ""  # in plain words, how the robot will do it


class OptionOut(ApiModel):
    id: str
    label: str
    steps: list[StepModel]


class QuestionOut(ApiModel):
    id: str
    prompt: str
    options: list[OptionOut]


class RestOut(ApiModel):
    object: str
    start_s: float
    end_s: float
    x: float
    y: float


class MoveOut(ApiModel):
    object: str
    start_s: float
    end_s: float
    from_x: float
    from_y: float
    to_x: float
    to_y: float


class ContainerOut(ApiModel):
    name: str
    x1: float
    y1: float
    x2: float
    y2: float


class LearnResultOut(ApiModel):
    sample_id: str
    video_url: str
    width: int
    height: int
    duration_s: float
    source: Literal["geometry", "muse_spark"]
    steps: list[StepModel]
    questions: list[QuestionOut]
    discrepancies: list[str]
    rests: list[RestOut]
    moves: list[MoveOut]
    containers: list[ContainerOut]
    object_names: list[str]  # everything the robot found on the table
    container_names: list[str]


class CheckOut(ApiModel):
    step: str
    ok: bool
    detail: str


class FixesOut(ApiModel):
    """What SAM saw on the finished table, and the one corrective try it triggered."""

    before: list[CheckOut]
    after: list[CheckOut]
    retried: list[str]
    missed: bool
    fixed: bool


class RunResultOut(ApiModel):
    video_url: str
    success: bool
    seed: int
    checks: list[CheckOut]
    step_times_s: list[float]
    perception_error_mm: dict[str, float]
    fixes: FixesOut | None = None


class JobOut(ApiModel):
    id: str
    kind: JobKind
    status: JobStatus
    stage: str
    error: str | None = None
    learn: LearnResultOut | None = None
    run: RunResultOut | None = None


class JobRef(ApiModel):
    job_id: str


class ChatMessage(ApiModel):
    role: Literal["person", "robot"]
    text: str


class ChatRequest(ApiModel):
    sample_id: str
    messages: list[ChatMessage] = Field(min_length=1)
    steps: list[StepModel]


class ChatReply(ApiModel):
    reply: str
    steps: list[StepModel]
    confirmed: bool


class LearnRequest(ApiModel):
    sample_id: str


class RunRequest(ApiModel):
    sample_id: str
    steps: list[StepModel] = Field(min_length=1)
    seed: int = 0
    oracle: bool = False
    slip: bool = False  # stage a miss: drop one object after the run so SAM has something to catch
