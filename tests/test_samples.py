"""Every sample scene file must describe a program the system can actually express."""

import json
from pathlib import Path

import pytest

from showonce.program import Step
from showonce.scene_spec import SceneSpec

SAMPLES = Path(__file__).resolve().parent.parent / "samples"


@pytest.mark.parametrize("path", sorted(SAMPLES.glob("*.json")), ids=lambda p: p.stem)
def test_scene_files_parse_and_name_real_things(path: Path) -> None:
    scene = SceneSpec.model_validate_json(path.read_text())
    assert scene.prompts, "a scene with no objects cannot show anything"
    names = set(scene.prompts) | set(scene.container_prompts)
    for raw in json.loads(path.read_text()).get("steps", []):
        step = Step.model_validate(raw)
        assert step.object in names, f"{step.object} is not on the table in {path.name}"
        assert step.target in names or step.target == step.object, (
            f"{step.target} is not on the table in {path.name}"
        )


def test_the_new_clips_exist() -> None:
    for name in ("cooking_prep", "book_push_aside", "lamp_press"):
        assert (SAMPLES / f"{name}.json").exists()
