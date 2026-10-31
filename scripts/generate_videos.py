"""Generate long chore clips for testing, from scripts/chore_prompts.json.

Development tool only. ShowOnce itself uses only Meta models; these clips are test footage.

One clip is one continuous video, so the hand and objects stay consistent with no cuts:

1. An image model makes a clean start frame of the table.
2. Omni generates the first step (up to 10 s) from that frame.
3. Each further step extends the same video (previous_interaction_id), 10 s at a time, up to
   40 s in total.

Every turn is cached under samples/generated/_work/<name>/, so reruns only pay for missing
turns (about $0.10 per generated second). Needs GEMINI_API_KEY and the `tools` group:

    uv run --group tools python scripts/generate_videos.py --only toys_into_bin
"""

from __future__ import annotations

import argparse
import base64
import json
import os
from pathlib import Path

from google import genai
from google.genai import types

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "samples" / "generated"
WORK = OUT / "_work"
VIDEO_MODEL = "gemini-omni-1.1-flash"  # about $0.10 per second of 720p video
IMAGE_MODEL = "gemini-3.1-flash-image"


def load_env() -> None:
    env = ROOT / ".env"
    if not env.exists():
        return
    for line in env.read_text().splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip())


def make_image(client: genai.Client, contents: list[object], path: Path) -> None:
    if path.exists():
        return
    response = client.models.generate_content(
        model=IMAGE_MODEL,
        contents=contents,
        config=types.GenerateContentConfig(
            response_modalities=["IMAGE"],
            image_config=types.ImageConfig(aspect_ratio="16:9"),
        ),
    )
    parts = [p.inline_data for p in response.candidates[0].content.parts if p.inline_data]
    if not parts:
        raise RuntimeError(f"No image returned for {path.name}")
    path.write_bytes(parts[0].data)


def _image(path: Path) -> dict[str, str]:
    return {
        "type": "image",
        "data": base64.b64encode(path.read_bytes()).decode(),
        "mime_type": "image/png" if path.read_bytes()[:4] == b"\x89PNG" else "image/jpeg",
    }


def _create(client: genai.Client, input_: list[dict[str, str]], previous: str | None) -> object:
    kwargs: dict[str, object] = {
        "model": VIDEO_MODEL,
        "input": input_,
        "response_format": {"type": "video", "resolution": "720p", "aspect_ratio": "16:9"},
    }
    if previous:
        kwargs["previous_interaction_id"] = previous
    return client.interactions.create(**kwargs)


def build_clip(client: genai.Client, name: str, spec: dict, clip: dict) -> None:
    out = OUT / f"{name}.mp4"
    if out.exists():
        print(f"skip {name}: already built")
        return
    work = WORK / name
    work.mkdir(parents=True, exist_ok=True)
    start = work / "frame0.png"
    print(f"{name}: start frame", flush=True)
    make_image(client, [f"{spec['_style']} {clip['scene']}"], start)
    previous: str | None = None
    video = work / "turn0.mp4"
    for i, step in enumerate(clip["steps"]):
        video = work / f"turn{i}.mp4"
        ids = work / f"turn{i}.id"
        if video.exists() and ids.exists():
            previous = ids.read_text()
            continue
        print(f"{name}: turn {i + 1}/{len(clip['steps'])}", flush=True)
        if previous is None:
            text = f"{step['motion']} {spec['_motion']} The clip lasts 10 seconds."
            interaction = _create(client, [_image(start), {"type": "text", "text": text}], None)
        else:
            text = (
                f"Extend this video. {step['motion']} {spec['_motion']} The same hand, same "
                "sleeve and same camera as before. Keep everything else the same."
            )
            interaction = _create(client, [{"type": "text", "text": text}], previous)
        video.write_bytes(base64.b64decode(interaction.output_video.data))
        previous = interaction.id
        ids.write_text(previous)
    # Each extension returns the video so far, so the last turn is the whole clip.
    out.write_bytes(video.read_bytes())
    (work / "clip.json").write_text(json.dumps(clip, indent=2))
    print(f"{name}: saved {out.relative_to(ROOT)}", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--only", nargs="*", help="Clip names to build (default: all).")
    args = parser.parse_args()
    load_env()
    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    spec = json.loads((ROOT / "scripts" / "chore_prompts.json").read_text())
    for name, clip in spec["clips"].items():
        if not args.only or name in args.only:
            build_clip(client, name, spec, clip)


if __name__ == "__main__":
    main()
