import math
from pathlib import Path

import httpx
import pytest
import respx

from showonce.cache import JsonCache
from showonce.config import Settings
from showonce.meta.client import MetaClient
from showonce.program import Step, TaskProgram
from showonce.replay import replay, shuffled_layout
from showonce.scene_spec import ContainerSpec, SceneSpec
from showonce.sim.executor import Region
from showonce.sim.scene import DEFAULT_ASSET_DIR

needs_panda = pytest.mark.skipif(
    not (DEFAULT_ASSET_DIR / "panda.xml").exists(), reason="Panda model missing"
)


def test_shuffled_layout_is_deterministic_and_clear() -> None:
    region = Region("box", (0.47, -0.16), (0.1, 0.1))
    names = ["a", "b", "c"]
    first = shuffled_layout(names, [region], seed=3)
    assert first == shuffled_layout(names, [region], seed=3)
    assert first != shuffled_layout(names, [region], seed=4)
    points = list(first.values())
    assert all(math.dist(p, q) > 0.09 for i, p in enumerate(points) for q in points[i + 1 :])
    assert all(
        abs(p[1] - region.center[1]) > 0.1 or abs(p[0] - region.center[0]) > 0.1 for p in points
    )


def test_mugs_are_kept_apart_and_inside_the_camera_view() -> None:
    region = Region("tray", (0.468, -0.126), (0.167, 0.166))
    names = ["red mug", "blue mug", "green mug"]
    for seed in range(20):
        points = list(shuffled_layout(names, [region], seed).values())
        assert all(math.dist(p, q) > 0.1 for i, p in enumerate(points) for q in points[i + 1 :])
        assert all(0.34 < x < 0.6 and -0.24 < y < 0.24 for x, y in points)


@needs_panda
def test_replay_with_oracle_positions_succeeds() -> None:
    scene = SceneSpec(
        name="t",
        prompts={"red block": "red block", "blue block": "blue block"},
        containers=[ContainerSpec(name="box", center=(1030, 360), size=(240, 280))],
        size=(1280, 720),
    )
    program = TaskProgram(
        name="t", steps=[Step(object="red block", action="place_in", target="box")]
    )
    assert replay(None, program, scene, seed=2, oracle=True).success


@respx.mock
def test_segment_image_sends_data_url_and_caches(tmp_path: Path) -> None:
    settings = Settings(_env_file=None, api_key="k", cache_dir=tmp_path)  # type: ignore[call-arg]
    sse = (
        'data: {"type":"response.output_text.delta","delta":'
        '"<0f>0<|box;x1=1;y1=2;x2=3;y2=4;w=10;h=10|><|mask;x=0;y=0;data=10,10,~zz|>"}\n\n'
    )
    route = respx.post("https://api.meta.ai/v1/responses").mock(
        return_value=httpx.Response(200, text=sse)
    )
    with MetaClient(settings, JsonCache(tmp_path)) as client:
        client.segment_image(b"png-bytes", "red block")
        client.segment_image(b"png-bytes", "red block")
    assert route.call_count == 1
    content = route.calls[0].request.content.decode()
    assert "data:image/png;base64," in content and "input_image" in content
