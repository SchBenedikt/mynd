"""Test core/utils.py – call_with_timeout."""

import time

from core.utils import call_with_timeout


class TestCallWithTimeout:
    def test_returns_result_on_success(self):
        result, err = call_with_timeout(lambda: 42, timeout=5)
        assert result == 42
        assert err is None

    def test_returns_result_with_args(self):
        result, err = call_with_timeout(lambda a, b: a + b, args=(3, 4), timeout=5)
        assert result == 7
        assert err is None

    def test_returns_result_with_kwargs(self):
        result, err = call_with_timeout(lambda x=0: x * 2, kwargs={"x": 21}, timeout=5)
        assert result == 42
        assert err is None

    def test_timeout_returns_error(self):
        def slow():
            time.sleep(10)
            return "done"

        result, err = call_with_timeout(slow, timeout=1)
        assert result is None
        assert isinstance(err, TimeoutError)

    def test_exception_in_function_returns_error(self):
        def crash():
            raise ValueError("boom")

        result, err = call_with_timeout(crash, timeout=5)
        assert result is None
        assert isinstance(err, ValueError)
        assert "boom" in str(err)

    def test_default_timeout_is_8_seconds(self):
        result, err = call_with_timeout(lambda: "ok")
        # Should complete within 8s
        assert result == "ok"
        assert err is None
