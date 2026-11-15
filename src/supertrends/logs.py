# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Serverless Ventures LLC
"""Structured JSON logging with secret scrubbing (ARCHITECTURE 11.2, NFR-009).

One JSON object per line on stdout. A scrubber runs after every other processor and before
the renderer: it drops values under secret-looking keys and masks secret values, bearer
strings, DSN passwords, and credential query parameters inside any string.
"""

from __future__ import annotations

import logging
import re
import sys
from collections.abc import Mapping
from typing import Any, TextIO

import structlog
from pydantic import SecretStr
from sqlalchemy.engine import make_url
from structlog.typing import EventDict, WrappedLogger

from supertrends.settings import Settings
from supertrends.version import get_version

REDACTED = "[REDACTED]"
_SECRET_KEY = re.compile(r"(?i)(token|api[_-]?key|password|secret|authorization|database_url)")
_SAFE_KEYS = frozenset({"tokens_in", "tokens_out", "narrative_tokens"})
_BEARER = re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+/=\-]+")
_DSN_PASSWORD = re.compile(r"(://[^:/@\s]*:)[^@\s/]+@")
_QUERY_SECRET = re.compile(r"(?i)([?&](?:api[_-]?key|access[_-]?token|token|key)=)[^&\s\"']+")
_MIN_SECRET_LEN = 4
_LEVELS = {"debug": logging.DEBUG, "info": logging.INFO, "warning": logging.WARNING}


def collect_secrets(settings: Settings) -> list[str]:
    """Every non-trivial secret value configured in settings, longest first."""
    values: set[str] = set()
    for name in type(settings).model_fields:
        value = getattr(settings, name)
        if isinstance(value, SecretStr):
            raw = value.get_secret_value()
            if len(raw) >= _MIN_SECRET_LEN:
                values.add(raw)
            if name == "database_url":
                try:
                    password = make_url(raw).password
                except Exception:
                    password = None
                if password and len(password) >= _MIN_SECRET_LEN:
                    values.add(password)
    return sorted(values, key=len, reverse=True)


def scrub_text(text: str, secrets: list[str]) -> str:
    """Mask known secret values, bearer strings, DSN passwords, and credential query params."""
    for secret in secrets:
        text = text.replace(secret, REDACTED)
    text = _BEARER.sub(f"Bearer {REDACTED}", text)
    text = _DSN_PASSWORD.sub(rf"\1{REDACTED}@", text)
    return _QUERY_SECRET.sub(rf"\1{REDACTED}", text)


def scrub_value(value: Any, secrets: list[str]) -> Any:
    """Recursively scrub a log value. Unknown objects are stringified first."""
    if isinstance(value, str):
        return scrub_text(value, secrets)
    if isinstance(value, bool | int | float) or value is None:
        return value
    if isinstance(value, Mapping):
        return {
            str(k): REDACTED
            if _SECRET_KEY.search(str(k)) and str(k) not in _SAFE_KEYS
            else scrub_value(v, secrets)
            for k, v in value.items()
        }
    if isinstance(value, list | tuple | set | frozenset):
        return [scrub_value(v, secrets) for v in value]
    return scrub_text(str(value), secrets)


def make_scrubber(secrets: list[str]) -> Any:
    """structlog processor applying `scrub_value` to the whole event dict."""

    def scrubber(_logger: WrappedLogger, _name: str, event_dict: EventDict) -> EventDict:
        return dict(scrub_value(event_dict, secrets))

    return scrubber


class _NamedPrintLogger(structlog.PrintLogger):
    """PrintLogger that remembers the name passed to `structlog.get_logger(name)`."""

    def __init__(self, file: TextIO, name: str) -> None:
        super().__init__(file)
        self.name = name


class _Factory:
    def __init__(self, stream: TextIO) -> None:
        self._stream = stream

    def __call__(self, *args: object) -> _NamedPrintLogger:
        return _NamedPrintLogger(self._stream, str(args[0]) if args else "supertrends")


def _format_exception(debug: bool) -> Any:
    def processor(_logger: WrappedLogger, _name: str, event_dict: EventDict) -> EventDict:
        exc_info = event_dict.pop("exc_info", None)
        if not exc_info:
            return event_dict
        if exc_info is True:
            exc_info = sys.exc_info()
        if isinstance(exc_info, BaseException):
            exc_info = (type(exc_info), exc_info, exc_info.__traceback__)
        event_dict["exc_type"] = exc_info[0].__name__ if exc_info[0] else "Unknown"
        if debug:  # stack traces only at debug (ARCHITECTURE 11.2)
            event_dict["exception"] = structlog.processors.ExceptionRenderer()(
                _logger, _name, {"exc_info": exc_info}
            ).get("exception", "")
        return event_dict

    return processor


def configure_logging(settings: Settings, *, stream: TextIO | None = None) -> None:
    """Configure structlog for JSON lines. Safe to call repeatedly (tests reconfigure)."""
    level_name = settings.effective_log_level
    context = {"version": get_version(), "env": settings.env}

    def add_context(_l: WrappedLogger, _n: str, event_dict: EventDict) -> EventDict:
        for key, value in context.items():
            event_dict.setdefault(key, value)
        return event_dict

    def add_logger(logger: WrappedLogger, _n: str, event_dict: EventDict) -> EventDict:
        event_dict.setdefault("logger", getattr(logger, "name", "supertrends"))
        return event_dict

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            add_logger,
            structlog.processors.TimeStamper(fmt="iso", utc=True, key="ts"),
            add_context,
            _format_exception(level_name == "debug"),
            make_scrubber(collect_secrets(settings)),
            structlog.processors.JSONRenderer(sort_keys=False),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(_LEVELS.get(level_name, logging.ERROR)),
        logger_factory=_Factory(stream or sys.stdout),
        cache_logger_on_first_use=False,
    )
