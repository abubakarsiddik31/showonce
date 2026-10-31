"""The FastAPI app behind ``showonce ui``: JSON API, media files and the built web page."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from showonce.api.jobs import Job
from showonce.api.schemas import (
    ChatReply,
    ChatRequest,
    JobOut,
    JobRef,
    LearnRequest,
    LearnResultOut,
    RunRequest,
    RunResultOut,
    SampleOut,
)
from showonce.api.service import NotFoundError, Workspace
from showonce.config import Settings, get_settings
from showonce.scene_spec import SceneSpec


def _job_out(job: Job) -> JobOut:
    learn = job.result if job.kind == "learn" and isinstance(job.result, LearnResultOut) else None
    run = job.result if job.kind == "run" and isinstance(job.result, RunResultOut) else None
    return JobOut(
        id=job.id,
        kind=job.kind,
        status=job.status,
        stage=job.stage,
        error=job.error,
        learn=learn,
        run=run,
    )


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    workspace = Workspace(settings)
    app = FastAPI(title="ShowOnce", version="0.1.0")

    @app.get("/api/health")
    def health() -> dict[str, bool]:
        return {"ok": True, "metaKey": settings.api_key is not None}

    @app.get("/api/samples")
    def samples() -> list[SampleOut]:
        return workspace.list_samples()

    @app.post("/api/learn")
    def learn(body: LearnRequest) -> JobRef:
        try:
            return JobRef(job_id=workspace.start_learn(body.sample_id).id)
        except NotFoundError as exc:
            raise HTTPException(404, str(exc)) from exc

    @app.post("/api/learn/upload")
    async def learn_upload(
        video: Annotated[UploadFile, File()],
        objects: Annotated[str, Form(description="JSON object: name -> SAM prompt")] = "{}",
        containers: Annotated[str, Form(description="JSON object: name -> SAM prompt")] = "{}",
    ) -> JobRef:
        try:
            prompts = json.loads(objects)
            container_prompts = json.loads(containers)
        except json.JSONDecodeError as exc:
            raise HTTPException(422, f"Invalid JSON: {exc}") from exc
        scene = SceneSpec(name="upload", prompts=prompts, container_prompts=container_prompts)
        upload_id = workspace.add_upload(await video.read(), scene)
        return JobRef(job_id=workspace.start_learn(upload_id).id)

    @app.post("/api/chat")
    def chat(body: ChatRequest) -> ChatReply:
        try:
            return workspace.chat(body.sample_id, body.messages, body.steps)
        except NotFoundError as exc:
            raise HTTPException(404, str(exc)) from exc

    @app.post("/api/run")
    def run(body: RunRequest) -> JobRef:
        try:
            job = workspace.start_run(body.sample_id, body.steps, body.seed, body.oracle)
        except NotFoundError as exc:
            raise HTTPException(409, str(exc)) from exc
        return JobRef(job_id=job.id)

    @app.get("/api/jobs/{job_id}")
    def job(job_id: str) -> JobOut:
        found = workspace.jobs.get(job_id)
        if found is None:
            raise HTTPException(404, "Unknown job")
        return _job_out(found)

    for url, folder in (
        ("/media/samples", settings.samples_dir),
        ("/media/runs", settings.runs_dir),
    ):
        folder.mkdir(parents=True, exist_ok=True)
        app.mount(url, StaticFiles(directory=folder), name=url.strip("/").replace("/", "-"))

    dist: Path = settings.web_dist
    if dist.is_dir():
        app.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")

        @app.get("/{path:path}", include_in_schema=False)
        def spa(path: str) -> FileResponse:
            target = dist / path
            return FileResponse(target if path and target.is_file() else dist / "index.html")

    return app
