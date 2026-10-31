"""Parser for SAM 3.1 special-token text output.

Each output line starts with a frame marker ``<Nf>`` followed by comma-separated records
of the form ``<id><|box;...|><|mask;...|>``. Boxes are in source pixels. Mask payloads are
kept raw here because the detection pipeline only needs boxes.
"""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass

_FRAME_RE = re.compile(r"<(\d+)f>")
_RECORD_RE = re.compile(
    r"(?P<id>\d+)\s*<\|box;(?P<box>[^|]*?)\|>\s*<\|mask;(?P<mask>.*?)\|>",
    re.DOTALL,
)
_MASK_DATA_RE = re.compile(r"data=(?P<h>\d+),(?P<w>\d+),(?P<enc>[~!])(?P<payload>.*)", re.DOTALL)


@dataclass(frozen=True, slots=True)
class Box:
    x1: float
    y1: float
    x2: float
    y2: float
    frame_w: int
    frame_h: int
    confidence: float | None = None

    @property
    def center(self) -> tuple[float, float]:
        return ((self.x1 + self.x2) / 2, (self.y1 + self.y2) / 2)

    @property
    def area(self) -> float:
        return max(0.0, self.x2 - self.x1) * max(0.0, self.y2 - self.y1)


@dataclass(frozen=True, slots=True)
class RawMask:
    rows: int
    cols: int
    encoding: str  # "~" lossless, "!" one-bit
    payload: str


@dataclass(frozen=True, slots=True)
class Detection:
    frame: int
    object_id: int
    box: Box
    mask: RawMask | None


def _fields(token: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for item in token.split(";"):
        if "=" in item:
            key, _, value = item.partition("=")
            out[key.strip()] = value.strip()
    return out


def _parse_box(token: str) -> Box:
    f = _fields(token)
    return Box(
        x1=float(f["x1"]),
        y1=float(f["y1"]),
        x2=float(f["x2"]),
        y2=float(f["y2"]),
        frame_w=int(float(f["w"])),
        frame_h=int(float(f["h"])),
        confidence=float(f["c"]) if "c" in f else None,
    )


def _parse_mask(token: str) -> RawMask | None:
    match = _MASK_DATA_RE.search(token)
    if match is None:
        return None
    return RawMask(
        rows=int(match["h"]),
        cols=int(match["w"]),
        encoding=match["enc"],
        payload=match["payload"],
    )


def parse_sam_text(text: str) -> list[Detection]:
    """Parse the concatenated text of a SAM 3.1 response into detections.

    The explicit ``<Nf>`` value is used as the frame index; line order is not trusted.
    """
    markers = list(_FRAME_RE.finditer(text))
    detections: list[Detection] = []
    for i, marker in enumerate(markers):
        end = markers[i + 1].start() if i + 1 < len(markers) else len(text)
        body = text[marker.end() : end]
        frame = int(marker[1])
        for record in _RECORD_RE.finditer(body):
            detections.append(
                Detection(
                    frame=frame,
                    object_id=int(record["id"]),
                    box=_parse_box(record["box"]),
                    mask=_parse_mask(record["mask"]),
                )
            )
    return detections


def group_by_object(detections: list[Detection]) -> dict[int, list[Detection]]:
    """Group detections by track id, sorted by frame."""
    grouped: dict[int, list[Detection]] = defaultdict(list)
    for det in detections:
        grouped[det.object_id].append(det)
    return {oid: sorted(dets, key=lambda d: d.frame) for oid, dets in sorted(grouped.items())}
