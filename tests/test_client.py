from pathlib import Path

import httpx
import respx

from showonce.cache import JsonCache
from showonce.config import Settings
from showonce.meta.client import MetaClient

SSE = (
    'data: {"type":"response.output_text.delta","delta":"<0f>0<|box;x1=1;y1=2;x2=3;y2=4;w=10;h=10|>"}\n\n'
    'data: {"type":"response.output_text.delta","delta":"<|mask;x=0;y=0;data=10,10,~zz|>"}\n\n'
    'data: {"type":"response.completed"}\n\n'
)


@respx.mock
def test_segment_video_streams_parses_and_caches(tmp_path: Path) -> None:
    settings = Settings(_env_file=None, api_key="k", cache_dir=tmp_path)  # type: ignore[call-arg]
    route = respx.post("https://api.meta.ai/v1/responses").mock(
        return_value=httpx.Response(200, text=SSE)
    )
    with MetaClient(settings, JsonCache(tmp_path)) as client:
        first = client.segment_video("file_1", "red block")
        second = client.segment_video("file_1", "red block")
    assert len(first) == 1 and first[0].box.center == (2.0, 3.0)
    assert second == first
    assert route.call_count == 1
