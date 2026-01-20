"""Asyncio-based concurrent task management library.

This library provides a simple interface for executing multiple async tasks
concurrently with automatic concurrency limiting and comprehensive error handling.

Single Manager Example:
    >>> from concurrency import TaskManager
    >>>
    >>> manager = TaskManager(max_concurrent=10)
    >>> manager.add_task(fetch_data(url1))
    >>> manager.add_task(fetch_data(url2))
    >>> results = manager.run()
    >>>
    >>> for result in results:
    ...     if result.success:
    ...         print(result.value)
    ...     else:
    ...         print(f"Error: {result.error}")

Multiple Managers Example:
    >>> import asyncio
    >>> from concurrency import TaskManager
    >>>
    >>> async def main():
    ...     # Create multiple managers with different concurrency limits
    ...     manager1 = TaskManager(max_concurrent=5)
    ...     manager2 = TaskManager(max_concurrent=10)
    ...
    ...     # Add tasks to each manager
    ...     for url in urls_group1:
    ...         manager1.add_task(fetch_data(url))
    ...     for url in urls_group2:
    ...         manager2.add_task(fetch_data(url))
    ...
    ...     # Run both managers concurrently in the same event loop
    ...     results1, results2 = await asyncio.gather(
    ...         manager1.run_async(),
    ...         manager2.run_async()
    ...     )
    ...
    ...     return results1, results2
    >>>
    >>> asyncio.run(main())
"""

from .manager import TaskManager
from .result import TaskResult

__version__ = "0.1.0"
__all__ = ["TaskManager", "TaskResult"]
