"""A tiny in-memory job store: long calls run in a pool and the page polls for the result."""

from __future__ import annotations

import threading
import uuid
from collections.abc import Callable
from concurrent.futures import Executor, Future
from dataclasses import dataclass
from typing import Any

from showonce.api.schemas import JobKind, JobStatus


@dataclass(slots=True)
class Job:
    id: str
    kind: JobKind
    status: JobStatus = "queued"
    stage: str = "Waiting"
    error: str | None = None
    result: Any = None


class JobStore:
    def __init__(self) -> None:
        self._jobs: dict[str, Job] = {}
        self._lock = threading.Lock()

    def submit(
        self,
        kind: JobKind,
        executor: Executor,
        fn: Callable[[Callable[[str], None]], Any],
    ) -> Job:
        """Run ``fn(progress)`` in ``executor``. ``progress(stage)`` updates the job's stage."""
        job = Job(uuid.uuid4().hex[:12], kind)
        with self._lock:
            self._jobs[job.id] = job

        def progress(stage: str) -> None:
            job.stage = stage

        def work() -> None:
            job.status = "running"
            try:
                job.result = fn(progress)
                job.status = "done"
                job.stage = "Done"
            except Exception as exc:  # report any failure to the page instead of dying silently
                job.status = "failed"
                job.error = f"{type(exc).__name__}: {exc}"

        future: Future[None] = executor.submit(work)
        future.add_done_callback(lambda f: f.exception())
        return job

    def get(self, job_id: str) -> Job | None:
        return self._jobs.get(job_id)
