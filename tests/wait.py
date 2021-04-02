"""Waiting for events."""
import time
from typing import Callable, TypeVar


DEFAULT_TIMEOUT = 15.0
Ret = TypeVar('Ret')


class Timeout(Exception):
    """Timeout expired in wait_until."""


def wait_until(
    fn: Callable[[], Ret],
    check: Callable[[Ret], bool] = bool,
    timeout: float = DEFAULT_TIMEOUT,
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

    raise Timeout(message.format(time=timeout))
