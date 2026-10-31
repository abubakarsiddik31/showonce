from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from showonce.api.app import create_app
from showonce.api.questions import build_questions
from showonce.config import Settings
from showonce.program import Step


def step(obj: str, target: str = "box") -> Step:
    return Step(object=obj, action="place_in", target=target)


def test_no_question_when_both_readings_agree() -> None:
    plan = [step("red block"), step("blue block")]
    assert build_questions(plan, list(plan), "geometry") == []


def test_no_question_without_a_second_reading() -> None:
    assert build_questions([step("red block")], None, "geometry") == []


def test_question_offers_both_plans_when_they_differ() -> None:
    geometry = [step("red block"), step("red block")]
    semantic = [step("red block"), step("blue block")]
    (question,) = build_questions(geometry, semantic, "geometry")
    assert [o.id for o in question.options] == ["geometry", "muse_spark"]
    assert [s.text for s in question.options[1].steps] == [
        "put red block in box",
        "put blue block in box",
    ]


@pytest.fixture
def client(tmp_path: Path) -> TestClient:
    samples = tmp_path / "samples"
    samples.mkdir()
    (samples / "demo.mp4").write_bytes(b"")
    (samples / "demo.json").write_text(
        '{"name": "demo", "prompts": {"red block": "red block"}, '
        '"container_prompts": {"box": "box"}}'
    )
    settings = Settings(samples_dir=samples, runs_dir=tmp_path / "runs", web_dist=tmp_path / "nope")
    return TestClient(create_app(settings))


def test_lists_samples_in_camel_case(client: TestClient) -> None:
    (sample,) = client.get("/api/samples").json()
    assert sample["id"] == "demo"
    assert sample["videoUrl"] == "/media/samples/demo.mp4"
    assert sample["objects"] == ["red block"]
    assert sample["containers"] == ["box"]


def test_learn_unknown_sample_is_404(client: TestClient) -> None:
    assert client.post("/api/learn", json={"sampleId": "../etc/passwd"}).status_code == 404


def test_run_before_learning_is_409(client: TestClient) -> None:
    body = {
        "sampleId": "demo",
        "steps": [{"object": "red block", "action": "place_in", "target": "box"}],
    }
    assert client.post("/api/run", json=body).status_code == 409


def test_unknown_job_is_404(client: TestClient) -> None:
    assert client.get("/api/jobs/nope").status_code == 404
