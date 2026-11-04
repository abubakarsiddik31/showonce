"""The finished human and robot video pairs in ``demos/``, for the landing page."""

from __future__ import annotations

import json
from pathlib import Path

from showonce.api.schemas import DemoOut

ORDER = [
    "pexels_fruit_basket",
    "pexels_sugar_mix",
    "pexels_cut_carrots",
    "toys_into_bin",
    "dishes_into_rack",
    "lamp_press",
    "tidy_table",
]

TITLES = {"tidy_table": "Tidy a scattered table"}


def _words(step: dict[str, str | None]) -> str:
    verb = str(step["action"]).replace("_", " ")
    target = step.get("target")
    return f"{step['object']}: {verb}" + (f" {target}" if target else "")


def _title(name: str, samples_dir: Path) -> str:
    if name in TITLES:
        return TITLES[name]
    try:
        scene = json.loads((samples_dir / f"{name}.json").read_text())
        return str(scene.get("title") or name.replace("_", " "))
    except (OSError, ValueError):
        return name.replace("_", " ")


def _steps(folder: Path) -> list[str]:
    try:
        return [_words(s) for s in json.loads((folder / "program.json").read_text())["steps"]]
    except (OSError, ValueError, KeyError, TypeError):
        return []


def list_demos(demos_dir: Path, samples_dir: Path) -> list[DemoOut]:
    """Every folder that has a robot video, in a fixed showcase order."""
    found = (
        [d for d in demos_dir.glob("*") if (d / "robot.mp4").is_file()]
        if demos_dir.is_dir()
        else []
    )
    found.sort(key=lambda d: (ORDER.index(d.name) if d.name in ORDER else len(ORDER), d.name))

    def url(folder: Path, file: str) -> str | None:
        return f"/media/demos/{folder.name}/{file}" if (folder / file).is_file() else None

    return [
        DemoOut(
            id=d.name,
            title=_title(d.name, samples_dir),
            real_footage=d.name.startswith("pexels_"),
            steps=_steps(d),
            human_url=url(d, "human.mp4"),
            robot_url=f"/media/demos/{d.name}/robot.mp4",
            shuffled_url=url(d, "robot_shuffled.mp4"),
        )
        for d in found
    ]
