"""Work out what is on the table from the first frame of a clip, so the person need not say."""

from __future__ import annotations

from pathlib import Path

from showonce.meta.client import MetaClient
from showonce.perception.profiles import encode_png, first_frame
from showonce.scene_spec import SceneSpec

MAX_OBJECTS = 8


class DiscoveryError(RuntimeError):
    """Raised when nothing movable can be found on the table."""


def _unique(things: list[dict[str, str]]) -> dict[str, str]:
    """name -> phrase to find it, with blank and repeated names dropped."""
    out: dict[str, str] = {}
    for thing in things:
        name = " ".join(str(thing.get("name", "")).lower().split())
        find = " ".join(str(thing.get("find", "")).lower().split()) or name
        if name and name not in out:
            out[name] = find
    return out


def discover_scene(client: MetaClient, video: Path, name: str = "upload") -> SceneSpec:
    """Ask Muse Spark what objects and containers the clip's first frame shows."""
    found = client.describe_scene(encode_png(first_frame(video)))
    containers = _unique(list(found.get("containers", [])))
    objects = {
        n: f for n, f in _unique(list(found.get("objects", []))).items() if n not in containers
    }
    if not objects:
        raise DiscoveryError("I could not see anything on the table to learn about.")
    return SceneSpec(
        name=name,
        prompts=dict(list(objects.items())[:MAX_OBJECTS]),
        container_prompts=containers,
    )
