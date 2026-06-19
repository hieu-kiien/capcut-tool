from typing import Callable, Optional


class JobCancelled(RuntimeError):
    """Raised when a pipeline job is cancelled by the user."""


def raise_if_cancelled(cancel_check: Optional[Callable[[], bool]]) -> None:
    """Raise JobCancelled when the provided cancellation callback is active."""
    if cancel_check and cancel_check():
        raise JobCancelled("Quy trình đã bị hủy bởi người dùng.")
