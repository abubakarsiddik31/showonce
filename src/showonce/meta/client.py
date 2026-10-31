"""Thin client for the Meta Model API (Files + Responses), with disk caching."""

from __future__ import annotations

import base64
import hashlib
import json
import logging
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import httpx

from showonce.cache import JsonCache, hash_file, make_key
from showonce.config import Settings
from showonce.meta.muse import (
    build_request,
    chat_request,
    describe_request,
    parse_steps,
    response_text,
    scene_request,
)
from showonce.meta.sam import Detection, parse_sam_text
from showonce.program import Step

log = logging.getLogger(__name__)


class MetaAPIError(RuntimeError):
    """Raised when the Meta Model API returns an error."""


class MetaClient:
    """Calls the Meta Model API. All results are cached by content hash."""

    def __init__(
        self,
        settings: Settings,
        cache: JsonCache | None = None,
        http: httpx.Client | None = None,
    ) -> None:
        self.settings = settings
        self.cache = cache or JsonCache(settings.cache_dir)
        self._http = http or httpx.Client(
            base_url=settings.api_base_url,
            timeout=settings.request_timeout_s,
            headers={"Authorization": f"Bearer {settings.require_api_key()}"},
        )

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> MetaClient:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    # -- Files ---------------------------------------------------------------------------

    def upload_video(self, path: Path) -> str:
        """Upload a clip once and return its file id (cached by file content)."""
        key = make_key("file", hash_file(path))
        cached = self.cache.get(key)
        if cached:
            return str(cached["id"])
        with path.open("rb") as handle:
            resp = self._http.post(
                "/files", data={"purpose": "user_data"}, files={"file": (path.name, handle)}
            )
        self._raise_for_status(resp)
        file_id = str(resp.json()["id"])
        self.cache.set(key, {"id": file_id})
        log.info("uploaded %s as %s", path.name, file_id)
        return file_id

    # -- Responses -----------------------------------------------------------------------

    def segment_video(self, file_id: str, prompt: str) -> list[Detection]:
        """Run SAM 3.1 on an uploaded clip with a short noun-phrase prompt."""
        key = make_key("sam", file_id, prompt, self.settings.sam_model)
        cached = self.cache.get(key)
        if cached is not None:
            return parse_sam_text(str(cached["text"]))
        body = {
            "model": self.settings.sam_model,
            "stream": True,
            "input": [
                {
                    "type": "message",
                    "role": "user",
                    "content": [
                        {"type": "input_text", "text": prompt},
                        {"type": "input_video", "file_id": file_id},
                    ],
                }
            ],
        }
        text = "".join(self._stream_text(body))
        self.cache.set(key, {"text": text})
        return parse_sam_text(text)

    def segment_image(self, png: bytes, prompt: str) -> list[Detection]:
        """Run SAM 3.1 on one PNG image with a short noun-phrase prompt."""
        key = make_key(
            "sam-image", hashlib.sha256(png).hexdigest(), prompt, self.settings.sam_model
        )
        cached = self.cache.get(key)
        if cached is not None:
            return parse_sam_text(str(cached["text"]))
        data_url = "data:image/png;base64," + base64.b64encode(png).decode()
        body = {
            "model": self.settings.sam_model,
            "stream": True,
            "input": [
                {
                    "type": "message",
                    "role": "user",
                    "content": [
                        {"type": "input_text", "text": prompt},
                        {"type": "input_image", "image_url": data_url},
                    ],
                }
            ],
        }
        text = "".join(self._stream_text(body))
        self.cache.set(key, {"text": text})
        return parse_sam_text(text)

    def plan_video(self, file_id: str, objects: list[str], containers: list[str]) -> list[Step]:
        """Ask Muse Spark to read the clip into steps (object, action, target)."""
        body = build_request(self.settings.plan_model, file_id, objects, containers)
        key = make_key("plan", json.dumps(body, sort_keys=True))
        cached = self.cache.get(key)
        if cached is not None:
            return parse_steps(str(cached["text"]))
        resp = self._http.post("/responses", json=body)
        self._raise_for_status(resp)
        text = response_text(resp.json())
        self.cache.set(key, {"text": text})
        return parse_steps(text)

    def describe_objects(self, png: bytes, objects: list[str]) -> dict[str, dict[str, Any]]:
        """Ask Muse Spark what primitive (shape, size, handle) each named object is."""
        data_url = "data:image/png;base64," + base64.b64encode(png).decode()
        body = describe_request(self.settings.plan_model, data_url, objects)
        key = make_key("describe", hashlib.sha256(png).hexdigest(), json.dumps(objects))
        cached = self.cache.get(key)
        if cached is not None:
            return dict(json.loads(str(cached["text"])))
        resp = self._http.post("/responses", json=body)
        self._raise_for_status(resp)
        text = response_text(resp.json())
        self.cache.set(key, {"text": text})
        return dict(json.loads(text))

    def describe_scene(self, png: bytes) -> dict[str, Any]:
        """Ask Muse Spark what objects and containers are on the table in this frame."""
        data_url = "data:image/png;base64," + base64.b64encode(png).decode()
        body = scene_request(self.settings.plan_model, data_url)
        key = make_key("scene-v2", hashlib.sha256(png).hexdigest())
        cached = self.cache.get(key)
        if cached is not None:
            return dict(json.loads(str(cached["text"])))
        resp = self._http.post("/responses", json=body)
        self._raise_for_status(resp)
        text = response_text(resp.json())
        self.cache.set(key, {"text": text})
        return dict(json.loads(text))

    def chat(
        self,
        objects: list[str],
        containers: list[str],
        plan: list[Step],
        conversation: list[tuple[str, str]],
    ) -> dict[str, Any]:
        """One turn of talking the plan through. Not cached: the answer depends on the turn."""
        body = chat_request(self.settings.plan_model, objects, containers, plan, conversation)
        resp = self._http.post("/responses", json=body)
        self._raise_for_status(resp)
        return dict(json.loads(response_text(resp.json())))

    def _stream_text(self, body: dict[str, Any]) -> Iterator[str]:
        """Yield ``response.output_text.delta`` chunks from a streaming Responses call."""
        with self._http.stream("POST", "/responses", json=body) as resp:
            if resp.status_code >= 400:
                resp.read()
                self._raise_for_status(resp)
            for line in resp.iter_lines():
                if not line.startswith("data:"):
                    continue
                payload = line.removeprefix("data:").strip()
                if not payload or payload == "[DONE]":
                    continue
                event = json.loads(payload)
                if event.get("type") == "response.output_text.delta":
                    yield str(event.get("delta", ""))

    @staticmethod
    def _raise_for_status(resp: httpx.Response) -> None:
        if resp.status_code >= 400:
            raise MetaAPIError(
                f"{resp.request.method} {resp.url} -> {resp.status_code}: {resp.text}"
            )
