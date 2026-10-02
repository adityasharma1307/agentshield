"""Queues that accept a run id and do not execute it."""

from typing import Protocol

from arq.connections import RedisSettings


class RunQueue(Protocol):
    """Something that records a run for a worker. `enqueue` does not run the suite."""

    async def enqueue(self, run_id: str) -> None:
        """Record `run_id` for a later `execute_run` call."""


class MemoryQueue:
    """In-process list of run ids. Tests drain it by calling the worker themselves."""

    def __init__(self) -> None:
        self.jobs: list[str] = []

    async def enqueue(self, run_id: str) -> None:
        self.jobs.append(run_id)


class ArqQueue:
    """Enqueue `execute_run` on Redis. The arq worker process runs the job."""

    def __init__(self, redis_url: str) -> None:
        self._redis_url = redis_url

    async def enqueue(self, run_id: str) -> None:
        from arq import create_pool

        redis = await create_pool(RedisSettings.from_dsn(self._redis_url))
        try:
            job = await redis.enqueue_job("execute_run", run_id)
        finally:
            await redis.close()
        if job is None:
            raise RuntimeError("arq did not enqueue the run")
