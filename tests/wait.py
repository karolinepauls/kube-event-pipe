"""Waiting for events."""
import time
from typing import Callable, TypeVar


Ret = TypeVar('Ret')


def wait_until(
    fn: Callable[[], Ret],
    check: Callable[[Ret], bool] = bool,
    timeout: float = 15,
    interval: float = 0.1,
    message: str = 'Condition not true in {time} seconds.',
) -> Ret:
    """Poll until the condition is not falsy and return the value returned by `cond`."""
    start = time.monotonic()
    end = start + timeout
    while time.monotonic() <= end:
        val = fn()
        if check(val):
            return val
        time.sleep(interval)

    raise AssertionError(message.format(timeout=timeout))
