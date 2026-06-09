"""Renderer process pool — manages concurrent PDF render processes."""

from __future__ import annotations

import threading
from concurrent.futures import Future, ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from typing import Callable

from md_publishing_mcp.errors import RenderResult, TimeoutError_


class RenderPool:
    """Manages a pool of concurrent PDF render processes.

    Wraps a ThreadPoolExecutor to limit parallelism and provide
    a clean async interface for PDF rendering tasks. All public
    methods are thread-safe.

    Usage:
        with RenderPool() as pool:
            future = pool.submit(render_func)
            result = future.result()
    """

    def __init__(self, max_workers: int = 3, render_timeout: float = 120.0):
        self._max_workers = max_workers
        self._render_timeout = render_timeout
        self._executor = ThreadPoolExecutor(max_workers=max_workers)
        self._futures: set[Future] = set()
        self._lock = threading.Lock()

    def submit(self, render_func: Callable[[], RenderResult]) -> Future:
        """Submit a render task to the pool.

        Args:
            render_func: A zero-argument callable that returns a RenderResult.
                         Use functools.partial or lambda to bind arguments.

        Returns:
            A Future[RenderResult] for asynchronous result retrieval.
        """
        future = self._executor.submit(render_func)
        with self._lock:
            self._futures.add(future)
        return future

    @property
    def active_count(self) -> int:
        """Number of currently executing render tasks."""
        with self._lock:
            done = {f for f in self._futures if f.done()}
            self._futures -= done
            return len(self._futures)

    @property
    def queue_size(self) -> int:
        """Approximate number of queued (not yet executing) tasks.

        Since ThreadPoolExecutor does not expose its internal queue,
        this is estimated as pending futures minus max_workers.
        """
        with self._lock:
            done = {f for f in self._futures if f.done()}
            pending = len(self._futures) - len(done)
            self._futures -= done
        return max(0, pending - self._max_workers)

    def shutdown(self, wait: bool = True) -> None:
        """Shut down the pool.

        Cancels pending futures and waits for running ones with a
        per-task timeout of render_timeout seconds.

        Args:
            wait: If True, wait for running tasks to complete
                  (with timeout). If False, return immediately.
        """
        with self._lock:
            futures = list(self._futures)

        for f in futures:
            f.cancel()

        if wait:
            import time

            deadline = time.monotonic() + self._render_timeout
            for f in futures:
                if not f.done():
                    remaining = max(0.0, deadline - time.monotonic())
                    try:
                        f.result(timeout=remaining)
                    except (FuturesTimeoutError, Exception):
                        pass

        self._executor.shutdown(wait=False, cancel_futures=True)

    def __enter__(self) -> RenderPool:
        return self

    def __exit__(self, exc_type: object, exc_val: object, exc_tb: object) -> None:
        self.shutdown(wait=True)

    def map_render(self, render_funcs: list[Callable[[], RenderResult]]) -> list[RenderResult]:
        """Submit multiple render tasks and collect results in order.

        Args:
            render_funcs: List of zero-argument callables each returning
                          a RenderResult.

        Returns:
            List of RenderResult objects in the same order as render_funcs.

        Raises:
            TimeoutError_: If any render task exceeds the configured timeout.
        """
        futures = [self.submit(f) for f in render_funcs]
        results: list[RenderResult] = []
        for future in futures:
            try:
                result = future.result(timeout=self._render_timeout)
                results.append(result)
            except FuturesTimeoutError:
                future.cancel()
                raise TimeoutError_(f"Render timed out after {self._render_timeout}s")
        return results
