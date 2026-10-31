import json
from pathlib import Path

from showonce.synth.render import build_frames, write_clip
from showonce.synth.scene import FPS, SCENARIOS


def test_all_scenarios_fit_clip_length_limits() -> None:
    for sc in SCENARIOS:
        frames, events = build_frames(sc)
        assert 5 <= len(frames) / FPS <= 15, sc.name
        assert len(events) == len(sc.steps)


def test_objects_rest_inside_target_after_release() -> None:
    sc = next(s for s in SCENARIOS if s.name == "move_red_into_box")
    frames, _ = build_frames(sc)
    assert frames[-1].hand is None
    box = sc.containers[0]
    x, y = frames[-1].positions["red block"]
    assert abs(x - box.center[0]) < box.size[0] / 2
    assert abs(y - box.center[1]) < box.size[1] / 2


def test_write_clip_emits_video_and_truth(tmp_path: Path) -> None:
    video = write_clip(SCENARIOS[1], tmp_path)
    truth = json.loads(video.with_suffix(".json").read_text())
    assert video.stat().st_size > 10_000
    assert truth["steps"][0]["action"] == "stack_on"
    assert set(truth["final"]) == {"red cup", "green cup", "blue cup"}
