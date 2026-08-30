"""
Structured JSON logging with correlation IDs. Every log line is a JSON
object with at least: timestamp, level, component, message, trace_id,
plus whatever structured fields the caller adds -- never a free-text
string a human has to parse by eye.
"""
from __future__ import annotations

import json
import sys
import time
from typing import Any, TextIO


def log_event(
    level: str, component: str, message: str, trace_id: str | None = None,
    stream: TextIO = sys.stdout, **fields: Any,
) -> dict:
    record = {
        "timestamp": time.time(),
        "level": level,
        "component": component,
        "message": message,
        "trace_id": trace_id,
        **fields,
    }
    stream.write(json.dumps(record, default=str) + "\n")
    return record


def info(component: str, message: str, trace_id: str | None = None,
          stream: TextIO = sys.stdout, **fields) -> dict:
    return log_event("info", component, message, trace_id, stream, **fields)


def warning(component: str, message: str, trace_id: str | None = None,
             stream: TextIO = sys.stdout, **fields) -> dict:
    return log_event("warning", component, message, trace_id, stream, **fields)


def error(component: str, message: str, trace_id: str | None = None,
           stream: TextIO = sys.stdout, **fields) -> dict:
    return log_event("error", component, message, trace_id, stream, **fields)
