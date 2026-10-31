"""Scenario definitions for synthetic top-down demo clips."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

Color = tuple[int, int, int]  # BGR
Point = tuple[float, float]

WIDTH, HEIGHT, FPS = 1280, 720, 30

RED: Color = (50, 50, 215)
GREEN: Color = (70, 170, 60)
BLUE: Color = (200, 100, 40)
YELLOW: Color = (40, 200, 230)


@dataclass(frozen=True, slots=True)
class ObjectSpec:
    name: str
    kind: Literal["block", "cup"]
    color: Color
    prompt: str | None = None  # SAM prompt if it differs from the name


@dataclass(frozen=True, slots=True)
class Container:
    name: str
    kind: Literal["box", "zone"]
    center: Point
    size: tuple[int, int]


@dataclass(frozen=True, slots=True)
class Step:
    object: str
    action: Literal["place_in", "stack_on"]
    target: str


@dataclass(frozen=True, slots=True)
class Scenario:
    name: str
    objects: tuple[ObjectSpec, ...]
    steps: tuple[Step, ...]
    containers: tuple[Container, ...] = ()
    speed: float = 1.0
    light: float = 1.0
    noise: float = 2.0
    seed: int = 0
    notes: str = field(default="", compare=False)


BOX = Container("box", "box", (1030.0, 360.0), (240, 280))
LEFT_ZONE = Container("left zone", "zone", (980.0, 200.0), (240, 200))
RIGHT_ZONE = Container("right zone", "zone", (980.0, 520.0), (240, 200))

_BLOCKS = (
    ObjectSpec("red block", "block", RED),
    ObjectSpec("green block", "block", GREEN),
    ObjectSpec("blue block", "block", BLUE),
)
_CUPS = (
    ObjectSpec("red cup", "cup", RED, "red circle"),
    ObjectSpec("green cup", "cup", GREEN, "green circle"),
    ObjectSpec("blue cup", "cup", BLUE, "blue circle"),
)

SCENARIOS: tuple[Scenario, ...] = (
    Scenario(
        "move_red_into_box",
        _BLOCKS,
        (Step("red block", "place_in", "box"),),
        (BOX,),
        seed=1,
    ),
    Scenario(
        "stack_red_on_blue_cups",
        _CUPS,
        (Step("red cup", "stack_on", "blue cup"),),
        seed=2,
    ),
    Scenario(
        "two_blocks_into_box",
        _BLOCKS,
        (Step("green block", "place_in", "box"), Step("blue block", "place_in", "box")),
        (BOX,),
        seed=3,
    ),
    Scenario(
        "stack_three_cups",
        _CUPS,
        (Step("red cup", "stack_on", "blue cup"), Step("green cup", "stack_on", "red cup")),
        seed=4,
    ),
    Scenario(
        "sort_into_zones",
        (*_BLOCKS[:2], ObjectSpec("yellow block", "block", YELLOW)),
        (Step("red block", "place_in", "left zone"), Step("green block", "place_in", "right zone")),
        (LEFT_ZONE, RIGHT_ZONE),
        seed=5,
    ),
    Scenario(
        "fast_hands_two_into_box",
        _BLOCKS,
        (Step("blue block", "place_in", "box"), Step("red block", "place_in", "box")),
        (BOX,),
        speed=1.7,
        seed=6,
        notes="Fast hand motion: short rests, more motion blur risk.",
    ),
    Scenario(
        "dim_light_stack_cups",
        _CUPS,
        (Step("green cup", "stack_on", "blue cup"),),
        speed=1.0,
        light=0.6,
        noise=6.0,
        seed=7,
        notes="Dim, noisy lighting.",
    ),
    Scenario(
        "three_blocks_into_box",
        _BLOCKS,
        (
            Step("red block", "place_in", "box"),
            Step("green block", "place_in", "box"),
            Step("blue block", "place_in", "box"),
        ),
        (BOX,),
        speed=1.35,
        seed=8,
    ),
)
