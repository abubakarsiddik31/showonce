"""What a task object is, as a simple physical primitive the simulator can model.

Any object the user films is reduced to a box, cylinder or sphere with a real-world size, a
colour and an optional handle. The profile is read from the clip's first frame at learn time
(Muse Spark for shape and size, the pixels for colour) and saved with the scene, so the sim
can recreate the object without knowing what a "stapler" is.
"""

from __future__ import annotations

import colorsys
from typing import Any, Literal

from pydantic import BaseModel

ShapeKind = Literal["box", "cylinder", "sphere", "log"]
RGB = tuple[float, float, float]

# The sim gripper opens 8 cm, so nothing wider than this can be held.
MAX_GRASP_WIDTH = 0.068
MIN_SIZE = 0.02
MAX_HEIGHT = 0.2
MAX_LENGTH = 0.11  # longest side of a box (a knife, a bar), so several fit on the table at once
MAX_FOOTPRINT = 0.16  # keeps big things (plates, bags) small enough for the table view

COLORS: dict[str, RGB] = {
    "red": (0.85, 0.2, 0.2),
    "green": (0.2, 0.7, 0.3),
    "blue": (0.2, 0.4, 0.85),
    "yellow": (0.95, 0.8, 0.2),
    "orange": (0.92, 0.36, 0.05),  # deep, so it stays visible against the beige table
    "purple": (0.55, 0.3, 0.75),
    "pink": (0.95, 0.5, 0.7),
    "white": (0.95, 0.95, 0.95),
    "gray": (0.5, 0.5, 0.5),
    "brown": (0.45, 0.3, 0.18),
    "black": (0.12, 0.12, 0.12),
}
_ROUND_WORDS = ("ball", "apple", "orange", "lemon", "peach", "pear", "plum", "tomato")
_HOLLOW_WORDS = ("mug", "cup")


class ObjectProfile(BaseModel):
    """Size in meters. ``width`` runs along world x (the gripper's closing axis), ``depth`` y."""

    shape: ShapeKind = "box"
    width: float = 0.04
    depth: float = 0.04
    height: float = 0.04
    handle: bool = False  # a handle sticking out sideways, as on a mug
    openable: bool = False  # a sealed bag, packet or box: a lid you pull off to get inside
    pressable: bool = False  # a button, pump or push-light: press it straight down
    slices: int = (
        0  # a "log" (carrot, cucumber) lying along y that a knife cuts into this many discs
    )
    rgb: RGB | None = None  # colour sampled from the clip, used when the name has no colour word
    texture: str | None = None  # a picture of the object cut from the clip, seen from above


def color_in(name: str) -> str | None:
    """The colour word a name contains, if any."""
    lowered = name.lower()
    return next((word for word in COLORS if word in lowered), None)


def nearest_color(rgb: RGB) -> str:
    """Name a colour by hue, so a muted blue is still blue and not "black"."""
    hue, sat, val = colorsys.rgb_to_hsv(*rgb)
    degrees = hue * 360
    if val < 0.25:
        return "black"
    if sat < 0.2:
        return "white" if val > 0.8 else "gray"
    for upper, word in ((15, "red"), (40, "orange" if val >= 0.55 else "brown"), (70, "yellow")):
        if degrees < upper:
            return word
    for upper, word in ((170, "green"), (260, "blue"), (300, "purple"), (345, "pink")):
        if degrees < upper:
            return word
    return "red"


def color_of(name: str, profile: ObjectProfile) -> RGB:
    """The palette colour for the object's colour word, so the sim object and its prompt agree."""
    return COLORS[color_in(name) or nearest_color(profile.rgb or COLORS["gray"])]


def profile_from_name(name: str) -> ObjectProfile:
    """Best guess from the name alone, for when no description is available."""
    lowered = name.lower()
    if any(word in lowered for word in _HOLLOW_WORDS):
        return ObjectProfile(shape="cylinder", width=0.064, depth=0.064, height=0.08, handle=True)
    if any(word in lowered for word in _ROUND_WORDS):
        return ObjectProfile(shape="sphere", width=0.06, depth=0.06, height=0.06)
    return ObjectProfile()


def profile_from_description(description: dict[str, Any], rgb: RGB | None = None) -> ObjectProfile:
    """Turn Muse Spark's centimetre description into a profile (true size, before any fitting)."""
    shape: ShapeKind = description["shape"]
    width = min(MAX_FOOTPRINT, max(MIN_SIZE, float(description["width_cm"]) / 100))
    depth = min(MAX_FOOTPRINT, max(MIN_SIZE, float(description["depth_cm"]) / 100))
    height = min(MAX_HEIGHT, max(MIN_SIZE, float(description["height_cm"]) / 100))
    if shape != "box":  # round things are as wide as they are deep
        width = depth = (width + depth) / 2
    if shape == "sphere":
        width = depth = height = (width + depth + height) / 3
    return ObjectProfile(
        shape=shape,
        width=width,
        depth=depth,
        height=height,
        handle=bool(description.get("handle")) and shape == "cylinder",
        openable=bool(description.get("openable")) and shape == "box",
        pressable=bool(description.get("pressable")),
        rgb=rgb,
    )


def fit_to_gripper(profile: ObjectProfile) -> ObjectProfile:
    """Shrink an object the sim gripper cannot open around, keeping its proportions."""
    scale = min(1.0, MAX_GRASP_WIDTH / profile.width)
    if scale == 1.0:
        return profile
    return profile.model_copy(
        update={
            "width": profile.width * scale,
            "depth": profile.depth * scale,
            "height": max(MIN_SIZE, profile.height * scale),
        }
    )


def fit_to_table(profile: ObjectProfile) -> ObjectProfile:
    """Shrink a long box so it leaves room for the other things on the table."""
    scale = min(1.0, MAX_LENGTH / max(profile.width, profile.depth))
    if profile.shape != "box" or scale == 1.0:
        return profile
    return profile.model_copy(
        update={
            "width": profile.width * scale,
            "depth": profile.depth * scale,
            "height": max(MIN_SIZE, profile.height * scale),
        }
    )


def sim_prompts(name: str, profile: ObjectProfile) -> list[str]:
    """Phrases SAM can use to find the simulated stand-in, best first.

    SAM is picky about wording ("red box" works where "red packet" does not), so perception
    tries each in turn and uses the first that finds something.
    """
    word = color_in(name) or nearest_color(profile.rgb or COLORS["gray"])
    if profile.handle:
        phrases = [f"{word} mug", f"{word} cup"]
    elif profile.openable:
        phrases = [f"{word} packet", f"{word} box"]
    elif profile.pressable:
        phrases = [f"{word} button", f"{word} lamp"]
    elif profile.shape == "cylinder" and profile.height < 0.4 * profile.width:
        phrases = [f"{word} plate", f"{word} circle", f"{word} round object", "round plate"]
    else:
        noun = {"box": "block", "cylinder": "cylinder", "sphere": "ball", "log": "carrot"}[
            profile.shape
        ]
        phrases = [f"{word} {noun}"]
    return [*phrases, f"{word} object"]


def sim_prompt(name: str, profile: ObjectProfile) -> str:
    return sim_prompts(name, profile)[0]
