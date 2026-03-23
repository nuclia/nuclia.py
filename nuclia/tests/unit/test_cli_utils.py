import logging
import os
import pytest

from nuclia.cli.utils import CustomFormatter, yes_no


def test_yes_no_returns_true_in_testing_mode(monkeypatch):
    monkeypatch.setenv("TESTING", "True")
    assert yes_no("Are you sure?") is True


def test_custom_formatter_debug():
    formatter = CustomFormatter()
    record = logging.LogRecord(
        name="test", level=logging.DEBUG, pathname="", lineno=0,
        msg="debug message", args=(), exc_info=None,
    )
    result = formatter.format(record)
    assert "debug message" in result


def test_custom_formatter_info():
    formatter = CustomFormatter()
    record = logging.LogRecord(
        name="test", level=logging.INFO, pathname="", lineno=0,
        msg="info message", args=(), exc_info=None,
    )
    result = formatter.format(record)
    assert "info message" in result


def test_custom_formatter_warning():
    formatter = CustomFormatter()
    record = logging.LogRecord(
        name="test", level=logging.WARNING, pathname="", lineno=0,
        msg="warning message", args=(), exc_info=None,
    )
    result = formatter.format(record)
    assert "warning message" in result


def test_custom_formatter_error():
    formatter = CustomFormatter()
    record = logging.LogRecord(
        name="test", level=logging.ERROR, pathname="", lineno=0,
        msg="error message", args=(), exc_info=None,
    )
    result = formatter.format(record)
    assert "error message" in result


def test_custom_formatter_critical():
    formatter = CustomFormatter()
    record = logging.LogRecord(
        name="test", level=logging.CRITICAL, pathname="", lineno=0,
        msg="critical message", args=(), exc_info=None,
    )
    result = formatter.format(record)
    assert "critical message" in result
