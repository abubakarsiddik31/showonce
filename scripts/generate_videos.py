"""Generate long chore clips for testing, from scripts/chore_prompts.json.

Development tool only. ShowOnce itself uses only Meta models; these clips are test footage.

Generative video does not keep objects consistent over long clips, so each clip is built from
anchored steps:

1. An image model makes a clean start frame of the table.
2. For each step, the image model edits the previous frame into the step's end state.
3. Omni generates the hand motion between the two frames (first and last frame given).
4. The segments are joined, with a still of each end state held between steps so every step
   ends with a clean resting frame and no hand.

Everything is cached under samples/generated/_work/, so reruns only pay for missing pieces.
Needs GEMINI_API_KEY and the `tools` dependency group:

    uv run --group tools python scripts/generate_videos.py --only dishes_into_rack
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import subprocess
from pathlib import Path

from google import genai
from google.genai import types

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "samples" / "generated"
WORK = OUT / "_work"
VIDEO_MODEL = "gemini-omni-1.1-flash"  # about $0.10 per second of 720p video
IMAGE_MODEL = "gemini-3.1-flash-image"
SEGMENT_SECONDS = 8
HOLD_SECONDS = 1.0


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


def make_segment(client: genai.Client, first: Path, last: Path, motion: str, path: Path) -> None:
    if path.exists():
        return

    def image(p: Path) -> dict[str, str]:
        return {
            "type": "image",
            "data": base64.b64encode(p.read_bytes()).decode(),
            "mime_type": "image/jpeg",
        }

    text = (
        f"{motion} The first image is the exact start and the second image is the exact end. "
        f"The clip lasts about {SEGMENT_SECONDS} seconds."
    )
    interaction = client.interactions.create(
        model=VIDEO_MODEL,
        input=[image(first), image(last), {"type": "text", "text": text}],
        response_format={"type": "video", "resolution": "720p", "aspect_ratio": "16:9"},
    )
    path.write_bytes(base64.b64decode(interaction.output_video.data))


def assemble(frames: list[Path], segments: list[Path], out: Path) -> None:
    """Join: hold(frame0), then for each step segment + hold(end frame). Video only, 24 fps."""
    norm = (
        "scale=1280:720:force_original_aspect_ratio=increase,crop=1280:720,"
        "fps=24,setsar=1,format=yuv420p"
    )
    cmd = ["ffmpeg", "-loglevel", "error", "-y"]
    for frame in (frames[0], *frames[1:]):
        cmd += ["-loop", "1", "-t", str(HOLD_SECONDS), "-i", str(frame)]
    for seg in segments:
        cmd += ["-i", str(seg)]
    n_frames = len(frames)
    order = [0]  # input index of each clip in playback order
    for i in range(len(segments)):
        order += [n_frames + i, i + 1]
    filters = [f"[{idx}:v]{norm}[v{k}]" for k, idx in enumerate(order)]
    joined = "".join(f"[v{k}]" for k in range(len(order)))
    filters.append(f"{joined}concat=n={len(order)}:v=1:a=0[out]")
    cmd += ["-filter_complex", ";".join(filters), "-map", "[out]", "-c:v", "libx264", str(out)]
    subprocess.run(cmd, check=True)


def build_clip(client: genai.Client, name: str, spec: dict, clip: dict) -> None:
    out = OUT / f"{name}.mp4"
    if out.exists():
        print(f"skip {name}: already built")
        return
    work = WORK / name
    work.mkdir(parents=True, exist_ok=True)
    frames = [work / "frame0.png"]
    print(f"{name}: start frame", flush=True)
    make_image(client, [f"{spec['_style']} {clip['scene']}"], frames[0])
    for i, step in enumerate(clip["steps"], 1):
        frames.append(work / f"frame{i}.png")
        print(f"{name}: end frame {i}", flush=True)
        previous = types.Part.from_bytes(data=frames[i - 1].read_bytes(), mime_type="image/jpeg")
        make_image(client, [previous, step["edit"]], frames[i])
    segments = []
    for i, step in enumerate(clip["steps"]):
        segments.append(work / f"seg{i}.mp4")
        print(f"{name}: motion segment {i + 1}/{len(clip['steps'])}", flush=True)
        make_segment(
            client,
            frames[i],
            frames[i + 1],
            f"{step['motion']} {spec['_motion']}",
            segments[i],
        )
    assemble(frames, segments, out)
    (WORK / name / "clip.json").write_text(json.dumps(clip, indent=2))
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
