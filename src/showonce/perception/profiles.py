"""Describe each task object from the clip's first frame, before any hand appears."""

from __future__ import annotations

import logging
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


def profile_objects(
    client: MetaClient, frame: NDArray[np.uint8], scene: SceneSpec
) -> dict[str, ObjectProfile]:
    """A profile per object: shape and size from Muse Spark, colour from the pixels.

    Objects the scene already profiles are kept. If Muse Spark cannot answer, the name decides.
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
        if color_in(name) is None:  # a named colour is used as is; otherwise look at the pixels
            detections = client.segment_image(png, scene.prompts[name])
            if detections:
                box = max(detections, key=lambda d: d.box.area).box
                rgb = _color_in_box(frame, (box.x1, box.y1, box.x2, box.y2))
        try:
            profiles[name] = profile_from_description(described[name], rgb)
        except (KeyError, TypeError, ValueError):
            profiles[name] = profile_from_name(name).model_copy(update={"rgb": rgb})
    return profiles
