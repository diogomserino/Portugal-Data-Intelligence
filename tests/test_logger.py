"""Tests for the logging utility."""

import json
import logging

from src.utils.logger import JsonFormatter, get_logger, log_section


class TestGetLogger:
    def test_returns_logger(self):
        logger = get_logger("test_module")
        assert isinstance(logger, logging.Logger)
        assert logger.name == "test_module"

    def test_same_name_returns_same_logger(self):
        l1 = get_logger("test_same")
        l2 = get_logger("test_same")
        assert l1 is l2

    def test_custom_level(self):
        logger = get_logger("test_level", level=logging.DEBUG)
        assert logger.level == logging.DEBUG


class TestLogSection:
    def test_log_section_does_not_raise(self):
        logger = get_logger("test_section")
        # Should not raise
        log_section(logger, "TEST SECTION")
        log_section(logger, "ANOTHER", char="-", width=40)


class TestJsonFormatter:
    def test_json_output(self):
        formatter = JsonFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="hello world",
            args=(),
            exc_info=None,
        )
        output = formatter.format(record)
        data = json.loads(output)
        assert data["message"] == "hello world"
        assert data["level"] == "INFO"
        assert "timestamp" in data

    def test_json_with_pillar(self):
        formatter = JsonFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="test msg",
            args=(),
            exc_info=None,
        )
        record.pillar = "gdp"
        output = formatter.format(record)
        data = json.loads(output)
        assert data["pillar"] == "gdp"
