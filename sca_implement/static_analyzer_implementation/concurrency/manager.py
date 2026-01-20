"""Task manager for concurrent async task execution."""

import asyncio
from typing import List, Coroutine, Any

from .result import TaskResult


class TaskManager:
    """Manages concurrent execution of async tasks.

    Example:
        >>> manager = TaskManager(max_concurrent=10)
        >>> manager.add_task(fetch_data(url1))
        >>> manager.add_task(fetch_data(url2))
        >>> results = manager.run()
    """

    def __init__(self, max_concurrent: int = 100, timeout: float = 300.0):
        """Initialize a TaskManager.

        Args:
            max_concurrent: Maximum number of tasks to run concurrently.
                          Defaults to 100 (auto-tuned for most I/O-bound workloads).
            timeout: Maximum time in seconds for each task to complete.
                    Defaults to 300.0 seconds (5 minutes).
        """
        self.max_concurrent = max_concurrent
        self.timeout = timeout
        self._tasks: List[Coroutine] = []

    def add_task(self, coro: Coroutine) -> None:
        """Add a task (coroutine) to be executed.

        Args:
            coro: An async coroutine to execute

        Example:
            >>> manager.add_task(fetch_url("https://example.com"))
        """
        if not asyncio.iscoroutine(coro):
            raise TypeError(f"Expected coroutine, got {type(coro).__name__}")
        self._tasks.append(coro)

    def run(self) -> List[TaskResult]:
        """Execute all tasks concurrently and block until completion.

        This method will create a new event loop if none exists, or use the
        existing loop if called from within an async context (though run_async()
        is preferred in that case).

        Returns:
            List of TaskResult objects in the same order tasks were added.
            Each result contains either a value (if successful) or an error.

        Example:
            >>> results = manager.run()
            >>> for result in results:
            ...     if result.success:
            ...         print(f"Success: {result.value}")
            ...     else:
            ...         print(f"Error: {result.error}")
        """
        if not self._tasks:
            return []

        # Check if an event loop is already running
        try:
            loop = asyncio.get_running_loop()
            # We're already in an async context, but run() was called (not recommended)
            # This will raise an error to guide users to use run_async() instead
            raise RuntimeError(
                "Cannot use run() from within an async context. "
                "Use 'await manager.run_async()' instead."
            )
        except RuntimeError:
            # No running loop, safe to use asyncio.run()
            return asyncio.run(self.run_async())

    async def run_async(self) -> List[TaskResult]:
        """Execute all tasks concurrently using the current event loop.

        This method is designed to work with an existing event loop, allowing
        multiple managers to run concurrently within the same async context.

        Returns:
            List of TaskResult objects in the same order tasks were added.
            Each result contains either a value (if successful) or an error.

        Example:
            >>> manager1 = TaskManager(max_concurrent=5)
            >>> manager2 = TaskManager(max_concurrent=10)
            >>> manager1.add_task(fetch_data(url1))
            >>> manager2.add_task(fetch_data(url2))
            >>>
            >>> # Run both managers concurrently
            >>> results1, results2 = await asyncio.gather(
            ...     manager1.run_async(),
            ...     manager2.run_async()
            ... )
        """
        if not self._tasks:
            return []

        return await self._execute_tasks()

    async def _execute_tasks(self) -> List[TaskResult]:
        """Internal async method to execute tasks with concurrency control and timeout."""
        semaphore = asyncio.Semaphore(self.max_concurrent)

        async def _run_with_semaphore(coro: Coroutine) -> Any:
            """Execute a single task with semaphore-based concurrency control and timeout."""
            async with semaphore:
                # Apply timeout to the task execution
                return await asyncio.wait_for(coro, timeout=self.timeout)

        # Wrap all tasks with semaphore control and timeout
        controlled_tasks = [_run_with_semaphore(task) for task in self._tasks]

        # Execute all tasks, capturing both results and exceptions
        raw_results = await asyncio.gather(*controlled_tasks, return_exceptions=True)

        # Wrap results in TaskResult objects
        results = []
        for raw_result in raw_results:
            if isinstance(raw_result, Exception):
                results.append(TaskResult(success=False, error=raw_result))
            else:
                results.append(TaskResult(success=True, value=raw_result))

        return results
