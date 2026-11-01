"""Describe each task object from the clip's first frame, before any hand appears."""

from __future__ import annotations

import logging
import re
from pathlib import Path

import cv2
import numpy as np
from numpy.typing import NDArray

from showonce.meta.client import MetaAPIError, MetaClient
from showonce.objects import (
    RGB,
    ObjectProfile,
    color_in,
    profile_from_description,
    profile_from_name,
)
from showonce.scene_spec import SceneSpec

log = logging.getLogger(__name__)

MIN_SATURATION = 110  # beige table is about 80; painted objects are well above
MIN_VALUE = 70  # darker pixels are shadow or the inside of a mug


def first_frame(video: Path) -> NDArray[np.uint8]:
    capture = cv2.VideoCapture(str(video))
    try:
        ok, frame = capture.read()
    finally:
        capture.release()
    if not ok:
        raise RuntimeError(f"Could not read the first frame of {video}")
    return np.asarray(frame, dtype=np.uint8)


def encode_png(frame: NDArray[np.uint8]) -> bytes:
    ok, encoded = cv2.imencode(".png", frame)
    if not ok:
        raise RuntimeError("Could not encode the frame")
    return encoded.tobytes()


def _color_in_box(frame: NDArray[np.uint8], box: tuple[float, float, float, float]) -> RGB | None:
    """Median colour of the vivid, lit pixels in a box.

    Beige table, shadows and a mug's dark inside are all left out, so what remains is the
    object's own colour. None if the object has no vivid pixels (grey, white, black).
    """
    x1, y1, x2, y2 = box
    crop = frame[max(0, int(y1)) : int(y2), max(0, int(x1)) : int(x2)]
    if crop.size == 0:
        return None
    hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV).reshape(-1, 3)
    vivid = crop.reshape(-1, 3)[(hsv[:, 1] >= MIN_SATURATION) & (hsv[:, 2] >= MIN_VALUE)]
    if len(vivid) < 20:
        return None
    b, g, r = np.median(vivid, axis=0)
    return (float(r) / 255, float(g) / 255, float(b) / 255)


MAX_ASPECT = 4.0  # a crop longer than this is probably a bad detection, not a real object


def texture_path(directory: Path, name: str) -> Path:
    """Where the picture of ``name`` lives."""
    return directory / f"{re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-') or 'object'}.png"


def sim_texture_path(texture: Path) -> Path:
    """The same picture turned to sit on a box in the simulator (see ``save_texture``)."""
    return texture.with_name(f"{texture.stem}.sim.png")


def sim_picture(crop: NDArray[np.uint8], round_: bool) -> NDArray[np.uint8]:
    """The crop, turned the way the simulator wants it.

    MuJoCo lays a texture's columns along the table's x axis and its rows along -y, while a
    picture taken from above has its columns along -y and its rows along -x, hence a quarter
    turn. A round decal is mapped from the other side, so it also needs flipping.
    """
    turned = np.rot90(crop, k=-1)
    return np.ascontiguousarray(np.flipud(turned) if round_ else turned)


def save_texture(
    frame: NDArray[np.uint8],
    box: tuple[float, float, float, float],
    path: Path,
    *,
    round_: bool = False,
) -> tuple[int, int] | None:
    """Cut an object out of the frame and save it twice, returning its (width, height) in pixels.

    The plain crop is for people to look at; the other copy is oriented for the simulator (see
    ``sim_picture``).
    """
    x1, y1, x2, y2 = (round(v) for v in box)
    h, w = frame.shape[:2]
    x1, y1, x2, y2 = max(0, x1), max(0, y1), min(w, x2), min(h, y2)
    if x2 - x1 < 8 or y2 - y1 < 8:
        return None
    ratio = (x2 - x1) / (y2 - y1)
    if ratio > MAX_ASPECT or 1 / ratio > MAX_ASPECT:
        return None
    crop = frame[y1:y2, x1:x2]
    path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(path), crop)
    cv2.imwrite(str(sim_texture_path(path)), sim_picture(crop, round_))
    return x2 - x1, y2 - y1


def footprint_from_picture(
    width: float, depth: float, picture: tuple[int, int]
) -> tuple[float, float]:
    """Give a box the proportions of its picture, keeping the larger side Muse Spark estimated.

    The picture is seen from above with image up along x, so its height is the box's width
    (x) and its width is the box's depth (y).
    """
    wide, high = picture
    longest = max(width, depth)
    if wide >= high:  # wider than tall: depth is the long side
        return longest * high / wide, longest
    return longest, longest * wide / high


def profile_objects(
    client: MetaClient,
    frame: NDArray[np.uint8],
    scene: SceneSpec,
    texture_dir: Path | None = None,
) -> dict[str, ObjectProfile]:
    """A profile per object: shape and size from Muse Spark, colour from the pixels.

    Objects the scene already profiles are kept. If Muse Spark cannot answer, the name decides.
    With ``texture_dir``, each box-shaped object is also cut out of the frame so the simulator
    can show the real thing (its label, its colours) instead of a plain block.
    """
    names = [n for n in scene.prompts if n not in scene.profiles]
    png = encode_png(frame)
    try:
        described = client.describe_objects(png, names) if names else {}
    except (MetaAPIError, ValueError, KeyError) as exc:
        log.warning("Muse Spark could not describe the objects: %s", exc)
        described = {}
    profiles = dict(scene.profiles)
    for name in names:
        rgb: RGB | None = None
        found: tuple[float, float, float, float] | None = None
        if color_in(name) is None or texture_dir is not None:
            detections = client.segment_image(png, scene.prompts[name])
            if detections:
                box = max(detections, key=lambda d: d.box.area).box
                found = (box.x1, box.y1, box.x2, box.y2)
                if color_in(name) is None:  # a named colour is used as is; else look at the pixels
                    rgb = _color_in_box(frame, found)
        try:
            profile = profile_from_description(described[name], rgb)
        except (KeyError, TypeError, ValueError):
            profile = profile_from_name(name).model_copy(update={"rgb": rgb})
        # Boxes and handle-less round things get a picture (a handle would skew the crop).
        pictured = profile.shape == "box" or (profile.shape == "cylinder" and not profile.handle)
        if texture_dir is not None and found is not None and pictured:
            path = texture_path(texture_dir, name)
            round_ = profile.shape == "cylinder"
            picture = save_texture(frame, found, path, round_=round_)
            if picture is not None:
                update: dict[str, object] = {"texture": str(path)}
                if not round_:
                    width, depth = footprint_from_picture(profile.width, profile.depth, picture)
                    update |= {"width": width, "depth": depth}
                profile = profile.model_copy(update=update)
        profiles[name] = profile
    return profiles
