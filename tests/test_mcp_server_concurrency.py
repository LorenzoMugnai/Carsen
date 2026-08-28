from __future__ import annotations

import threading
import time

import anyio

from carsen_mcp.mcp.server import _offload


def test_offload_runs_the_callable_in_a_worker_thread() -> None:
    async def scenario() -> None:
        main_thread = threading.get_ident()
        worker_thread = await _offload(threading.get_ident)
        assert worker_thread != main_thread

    anyio.run(scenario)


def test_offloaded_calls_run_concurrently() -> None:
    def blocking() -> str:
        time.sleep(0.3)
        return "done"

    async def scenario() -> None:
        start = time.monotonic()
        async with anyio.create_task_group() as task_group:
            task_group.start_soon(_offload, blocking)
            task_group.start_soon(_offload, blocking)
        assert time.monotonic() - start < 0.55

    anyio.run(scenario)


def test_offload_forwards_arguments() -> None:
    async def scenario() -> None:
        assert await _offload(lambda a, b: a + b, 2, b=3) == 5

    anyio.run(scenario)
