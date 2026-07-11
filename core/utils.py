"""Shared utility functions used across the application."""

import threading


def call_with_timeout(func, args=None, kwargs=None, timeout=8):
    """Call a function with a timeout using a daemon thread.

    Works on macOS where ThreadPoolExecutor is broken (Python 3.14.6).
    Returns (result, None) on success, (None, error) on failure/timeout.
    """
    if args is None:
        args = ()
    if kwargs is None:
        kwargs = {}
    result = [None]
    error = [None]

    def wrapper():
        try:
            result[0] = func(*args, **kwargs)
        except Exception as e:
            error[0] = e

    thread = threading.Thread(target=wrapper, daemon=True)
    thread.start()
    thread.join(timeout=timeout)

    if thread.is_alive():
        return None, TimeoutError(f'Timeout after {timeout}s')
    if error[0]:
        return None, error[0]
    return result[0], None
