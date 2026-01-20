"""Result wrapper for async task execution."""

from typing import Any, Optional


class TaskResult:
    """Represents the outcome of a task execution.

    Attributes:
        success: True if the task completed successfully, False if it raised an exception
        value: The return value of the task (only set if success=True)
        error: The exception raised by the task (only set if success=False)
    """

    def __init__(self, success: bool, value: Optional[Any] = None, error: Optional[Exception] = None):
        """Initialize a TaskResult.

        Args:
            success: Whether the task succeeded
            value: The return value (if successful)
            error: The exception (if failed)
        """
        self.success = success
        self.value = value
        self.error = error

    def __repr__(self) -> str:
        if self.success:
            return f"TaskResult(success=True, value={self.value!r})"
        else:
            return f"TaskResult(success=False, error={self.error!r})"
