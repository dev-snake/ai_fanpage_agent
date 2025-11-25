import time
from typing import Callable


def run_loop(
    task: Callable[[], None],
    *,
    interval_seconds: int,
    cycles: int | None = None,
) -> None:
    """
    Run task repeatedly. cycles=None means run forever.
    """
    count = 0
    while True:
        count += 1
        task()
        if cycles and count >= cycles:
            break
        time.sleep(interval_seconds)
