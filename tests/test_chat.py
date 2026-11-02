from pathlib import Path
from typing import Any

import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient

from showonce.api.app import create_app
from showonce.chat import clean_steps, describe_plan, how_it_will_do, talk, understand
from showonce.config import Settings
from showonce.meta.client import MetaAPIError
from showonce.meta.muse import chat_request, chat_schema, narrate_request, scene_schema
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


# -- saying what it understood ---------------------------------------------------------------


def test_the_plain_account_of_a_plan_reads_like_speech_and_asks_if_it_is_right() -> None:
    said = describe_plan([wipe("white plate"), wipe("blue plate")])
    assert said.startswith("I saw you wipe white plate with yellow sponge, then wipe blue plate")
    assert said.endswith("Did I get that right?")


def test_with_nothing_understood_it_asks_the_person_to_say_what_they_did() -> None:
    assert "tell me what you did" in describe_plan([]).lower()


class Narrator:
    def __init__(self, answer: str | Exception) -> None:
        self.answer = answer

    def narrate(self, file_id: str, plan: list[Step]) -> str:
        if isinstance(self.answer, Exception):
            raise self.answer
        return self.answer


def test_it_uses_the_models_own_words_when_it_has_them() -> None:
    said = understand(Narrator("I watched you clean the plate. Right?"), "file-1", [wipe("tray")])  # type: ignore[arg-type]
    assert said == "I watched you clean the plate. Right?"


@pytest.mark.parametrize("answer", ["", MetaAPIError("down"), ValueError("bad")])
def test_it_falls_back_to_a_plain_sentence_when_the_model_cannot_narrate(
    answer: str | Exception,
) -> None:
    said = understand(Narrator(answer), "file-1", [wipe("white plate")])  # type: ignore[arg-type]
    assert said == describe_plan([wipe("white plate")])


def test_the_narration_request_carries_the_video_and_the_plan_but_asks_for_plain_words() -> None:
    body = narrate_request("muse", "file-9", [wipe("white plate")])
    content = body["input"][0]["content"]
    assert {"type": "input_video", "file_id": "file-9"} in content
    prompt = content[0]["text"]
    assert "wipe white plate with yellow sponge" in prompt and "no numbered" in prompt.lower()


def test_the_conversation_prompt_knows_all_ten_actions_and_asks_before_guessing() -> None:
    prompt = chat_request("muse", OBJECTS, CONTAINERS, [], [("person", "hi")])["input"][0][
        "content"
    ][0]["text"]
    for word in (
        "put something in",
        "pour",
        "stir",
        "cut",
        "press",
        "push",
        "stack",
        "wipe",
        "open",
    ):
        assert word in prompt
    assert "ONE short question" in prompt


def test_clips_carry_a_title_and_a_group_for_the_app(tmp_path: Path) -> None:
    samples = tmp_path / "samples"
    samples.mkdir()
    (samples / "wash.mp4").write_bytes(b"")
    (samples / "wash.json").write_text(
        '{"name": "wash", "title": "Wash the plates", "group": "Chores", "prompts": {"a": "a"}}'
    )
    (samples / "plain.mp4").write_bytes(b"")
    (samples / "plain.json").write_text('{"name": "plain", "prompts": {"a": "a"}}')
    settings = Settings(  # type: ignore[call-arg]
        _env_file=None,
        api_key="k",
        samples_dir=samples,
        runs_dir=tmp_path / "runs",
        cache_dir=tmp_path / "cache",
        web_dist=tmp_path / "none",
    )
    found = {s["id"]: s for s in TestClient(create_app(settings)).get("/api/samples").json()}
    assert (found["wash"]["title"], found["wash"]["group"]) == ("Wash the plates", "Chores")
    assert (found["plain"]["title"], found["plain"]["group"]) == ("Plain", "More clips")


# -- the plan read from the clip is checked like any other ------------------------------------


class Planner:
    """A stand-in for Muse Spark that returns whatever plan it is given."""

    def __init__(self, plan: list[Step]) -> None:
        self.plan = plan

    def upload_video(self, video: Path) -> str:
        return "file-1"

    def plan_video(self, file_id: str, objects: list[str], containers: list[str]) -> list[Step]:
        return self.plan


def test_a_step_that_moves_the_bag_beside_itself_is_dropped_from_the_plan_it_reads() -> None:
    """Real case: laying the torn-off seal down came back as 'put red chips right of red chips'."""
    from showonce.demo import _read_with_muse_spark
    from showonce.scene_spec import SceneSpec

    bad = Step(object="red chips", action="place_near", target="red chips", relation="right_of")
    opened = Step(object="red chips", action="open", target="red chips")
    scene = SceneSpec(prompts={"red chips": "red chips bag"})
    read = _read_with_muse_spark(Planner([opened, bad]), Path("clip.mp4"), scene)  # type: ignore[arg-type]
    assert read == [opened]


def test_a_sensible_plan_is_read_unchanged() -> None:
    from showonce.demo import _read_with_muse_spark
    from showonce.scene_spec import SceneSpec

    plan = [wipe("white plate"), wipe("blue plate")]
    scene = SceneSpec(prompts={n: n for n in OBJECTS})
    assert _read_with_muse_spark(Planner(plan), Path("c.mp4"), scene) == plan  # type: ignore[arg-type]


def test_putting_the_tool_down_after_using_it_is_not_a_step_of_its_own() -> None:
    """Real case: wiping a plate came back as wipe, then 'put the sponge next to the plate'."""
    from showonce.chat import drop_setting_down

    down = Step(
        object="yellow sponge", action="place_near", target="white plate", relation="next_to"
    )
    plan = [wipe("white plate"), down, wipe("blue plate")]
    assert drop_setting_down(plan) == [wipe("white plate"), wipe("blue plate")]


def test_moving_something_on_purpose_is_kept() -> None:
    from showonce.chat import drop_setting_down

    to_tray = Step(object="yellow sponge", action="place_in", target="tray")
    elsewhere = Step(
        object="yellow sponge", action="place_near", target="blue plate", relation="left_of"
    )
    plan = [wipe("white plate"), to_tray, elsewhere]
    assert drop_setting_down(plan) == plan  # put in a tray, or beside a different thing: on purpose


class _CannedClient:
    def __init__(self, text: str) -> None:
        self._text = text

    def chat(
        self, objects: object, containers: object, plan: object, conversation: object
    ) -> dict:
        return {"text": self._text}


def test_repair_advice_reads_two_numbers() -> None:
    from showonce.chat import repair_advice

    step = Step(object="red block", action="push", target="bin")
    assert repair_advice(_CannedClient("0.02 -0.01"), step, "stopped 3 cm short") == (
        0.02,
        -0.01,
    )


def test_repair_advice_rejects_wild_or_garbled_answers() -> None:
    from showonce.chat import repair_advice

    step = Step(object="red block", action="push", target="bin")
    with pytest.raises(ValueError):
        repair_advice(_CannedClient("0.50 0.00"), step, "missed")  # beyond a fingertip fix
    with pytest.raises(ValueError):
        repair_advice(_CannedClient("a bit to the left please"), step, "missed")
