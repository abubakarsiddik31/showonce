from pathlib import Path
from typing import Any

import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient

from showonce.api.app import create_app
from showonce.chat import clean_steps, how_it_will_do, talk
from showonce.config import Settings
from showonce.meta.client import MetaAPIError
from showonce.meta.muse import chat_request, chat_schema, scene_schema
from showonce.perception.scene import DiscoveryError, discover_scene
from showonce.program import Step

OBJECTS = ["yellow sponge", "white plate", "blue plate"]
CONTAINERS = ["tray"]


def wipe(target: str) -> Step:
    return Step(object="yellow sponge", action="wipe", target=target)


def test_steps_naming_things_that_are_not_on_the_table_are_dropped() -> None:
    steps = [wipe("white plate"), Step(object="purple cup", action="place_in", target="tray")]
    assert clean_steps(steps, OBJECTS, CONTAINERS) == [wipe("white plate")]


def test_opening_always_targets_the_thing_opened() -> None:
    sloppy = Step(object="white plate", action="open", target="tray")
    (fixed,) = clean_steps([sloppy], OBJECTS, CONTAINERS)
    assert fixed.target == "white plate"


def test_actions_need_a_sensible_target() -> None:
    nonsense = [
        Step(object="white plate", action="place_in", target="blue plate"),  # not a container
        Step(object="white plate", action="stack_on", target="white plate"),  # on itself
        Step(object="yellow sponge", action="wipe", target="yellow sponge"),  # wipe itself
        Step(object="white plate", action="wipe", target="nothing"),  # no such thing
    ]
    assert clean_steps(nonsense, OBJECTS, CONTAINERS) == []
    fine = [
        Step(object="white plate", action="place_in", target="tray"),
        Step(object="white plate", action="stack_on", target="blue plate"),
        wipe("tray"),
    ]
    assert clean_steps(fine, OBJECTS, CONTAINERS) == fine


def test_how_the_robot_will_do_each_step_is_its_own_way() -> None:
    assert "own way" in how_it_will_do(wipe("white plate"))
    assert "inside the tray" in how_it_will_do(
        Step(object="blue plate", action="place_in", target="tray")
    )
    assert "tear" in how_it_will_do(Step(object="white plate", action="open", target="white plate"))


class FakeClient:
    def __init__(self, answer: dict[str, Any] | Exception) -> None:
        self.answer = answer
        self.seen: list[Any] = []

    def chat(self, *args: Any) -> dict[str, Any]:
        self.seen.append(args)
        if isinstance(self.answer, Exception):
            raise self.answer
        return self.answer


def say(client: FakeClient, plan: list[Step]):  # type: ignore[no-untyped-def]
    return talk(client, OBJECTS, CONTAINERS, plan, [("person", "hi")])  # type: ignore[arg-type]


def test_a_correction_revises_the_plan() -> None:
    answer = {
        "reply": "Added the blue plate.",
        "steps": [wipe("white plate").model_dump(), wipe("blue plate").model_dump()],
        "confirmed": False,
    }
    turn = say(FakeClient(answer), [wipe("white plate")])
    assert turn.steps == [wipe("white plate"), wipe("blue plate")]
    assert turn.reply == "Added the blue plate." and not turn.confirmed


def test_confirmation_is_passed_through() -> None:
    answer = {"reply": "Great.", "steps": [wipe("white plate").model_dump()], "confirmed": True}
    assert say(FakeClient(answer), [wipe("white plate")]).confirmed


def test_an_answer_that_is_all_nonsense_leaves_the_plan_alone() -> None:
    bad = Step(object="purple cup", action="open", target="purple cup").model_dump()
    turn = say(FakeClient({"reply": "Done.", "steps": [bad], "confirmed": False}), [wipe("tray")])
    assert turn.steps == [wipe("tray")]
    assert "unchanged" in turn.reply


@pytest.mark.parametrize("failure", [MetaAPIError("down"), KeyError("steps"), ValueError("bad")])
def test_a_failed_turn_keeps_the_plan_and_apologises(failure: Exception) -> None:
    turn = say(FakeClient(failure), [wipe("white plate")])
    assert turn.steps == [wipe("white plate")] and "Sorry" in turn.reply and not turn.confirmed


def test_request_only_allows_names_on_the_table_and_includes_the_plan_and_talk() -> None:
    body = chat_request(
        "muse", OBJECTS, CONTAINERS, [wipe("white plate")], [("person", "also the blue one")]
    )
    prompt = body["input"][0]["content"][0]["text"]
    assert "wipe white plate with yellow sponge" in prompt and "also the blue one" in prompt
    step_props = chat_schema(OBJECTS, CONTAINERS)["properties"]["steps"]["items"]["properties"]
    assert step_props["object"]["enum"] == OBJECTS
    assert set(step_props["target"]["enum"]) == {*OBJECTS, *CONTAINERS}
    assert set(scene_schema()["properties"]) == {"objects", "containers"}


# -- finding out what is on the table ------------------------------------------------------


def blank_clip(path: Path) -> Path:
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), 10, (64, 48))
    for _ in range(5):
        writer.write(np.zeros((48, 64, 3), dtype=np.uint8))
    writer.release()
    return path


class SceneClient:
    def __init__(self, found: dict[str, Any]) -> None:
        self.found = found

    def describe_scene(self, png: bytes) -> dict[str, Any]:
        assert png.startswith(b"\x89PNG")
        return self.found


def test_discovery_builds_a_scene_from_what_the_model_sees(tmp_path: Path) -> None:
    found = {
        "objects": [
            {"name": "Red  Mug", "find": "red mug"},
            {"name": "red mug", "find": "a duplicate"},  # same name twice
            {"name": "", "find": "nothing"},
            {"name": "gray tray", "find": "gray tray"},  # also listed as a container
        ],
        "containers": [{"name": "gray tray", "find": "gray plastic tray"}],
    }
    scene = discover_scene(SceneClient(found), blank_clip(tmp_path / "c.mp4"))  # type: ignore[arg-type]
    assert scene.prompts == {"red mug": "red mug"}
    assert scene.container_prompts == {"gray tray": "gray plastic tray"}


def test_an_empty_table_is_reported(tmp_path: Path) -> None:
    empty = SceneClient({"objects": [], "containers": []})
    with pytest.raises(DiscoveryError):
        discover_scene(empty, blank_clip(tmp_path / "c.mp4"))  # type: ignore[arg-type]


# -- the API -------------------------------------------------------------------------------


@pytest.fixture
def api(tmp_path: Path) -> TestClient:
    settings = Settings(  # type: ignore[call-arg]
        _env_file=None,
        api_key="k",
        samples_dir=tmp_path / "samples",
        runs_dir=tmp_path / "runs",
        cache_dir=tmp_path / "cache",
        web_dist=tmp_path / "none",
    )
    return TestClient(create_app(settings))


def test_chat_about_an_unknown_clip_is_404(api: TestClient) -> None:
    body = {
        "sampleId": "nope",
        "messages": [{"role": "person", "text": "hi"}],
        "steps": [],
    }
    assert api.post("/api/chat", json=body).status_code == 404


def test_chat_needs_at_least_one_message(api: TestClient) -> None:
    assert (
        api.post("/api/chat", json={"sampleId": "x", "messages": [], "steps": []}).status_code
        == 422
    )


def test_clean_steps_keeps_the_new_actions_that_make_sense() -> None:
    steps = [
        Step(object="red block", action="place_near", target="blue block", relation="left_of"),
        Step(object="green book", action="push", target="bin"),
        Step(object="red cup", action="pour", target="bowl"),
        Step(object="yellow spoon", action="stir", target="bowl"),
        Step(object="gray knife", action="cut", target="white bar"),
        Step(object="orange lamp", action="press", target="orange lamp"),
        Step(object="red cup", action="pour", target="blue block"),  # pour target not a container
        Step(object="gray knife", action="cut", target="ghost"),  # not on the table
    ]
    kept = clean_steps(
        steps,
        [
            "red block",
            "blue block",
            "green book",
            "red cup",
            "yellow spoon",
            "gray knife",
            "white bar",
            "orange lamp",
        ],
        ["bin", "bowl"],
    )
    assert kept == steps[:6]


def test_how_it_will_do_words_the_new_actions() -> None:
    assert "beside" in how_it_will_do(
        Step(object="a", action="place_near", target="b", relation="next_to")
    )
    assert "push" in how_it_will_do(Step(object="a", action="push", target="bin"))
    assert "pour" in how_it_will_do(Step(object="a", action="pour", target="bowl")).lower()
    assert "stir" in how_it_will_do(Step(object="a", action="stir", target="bowl")).lower()
    assert "cut" in how_it_will_do(Step(object="a", action="cut", target="b")).lower()
    assert "press" in how_it_will_do(Step(object="a", action="press", target="a")).lower()
