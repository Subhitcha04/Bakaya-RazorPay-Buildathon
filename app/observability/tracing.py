"""
Minimal, dependency-free tracing: one trace_id per case, one span per
agent/tool call, structured export. This is NOT the OpenTelemetry SDK
-- it deliberately reimplements just enough of OTel's SHAPE (trace_id,
span_id, parent_span_id, name, start/end, attributes) to be genuinely
useful now, fully testable without a collector, and structurally close
enough to a real OTel exporter that swapping SpanRecorder's sink for
an OTLP exporter later should be close to a drop-in replacement, not a
rewrite.

TODO before production: wire a real OTel SDK exporter (OTLP to
Langfuse or your collector of choice) behind SpanRecorder.record().
"""
from __future__ import annotations

import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any


def new_trace_id() -> str:
    return str(uuid.uuid4())


@dataclass
class Span:
    trace_id: str
    span_id: str
    parent_span_id: str | None
    name: str
    start_time: float
    end_time: float | None = None
    attributes: dict[str, Any] = field(default_factory=dict)
    status: str = "ok"
    error: str | None = None

    @property
    def duration_seconds(self) -> float | None:
        if self.end_time is None:
            return None
        return self.end_time - self.start_time


class SpanRecorder:
    def __init__(self):
        self.spans: list[Span] = []

    def record(self, span: Span) -> None:
        self.spans.append(span)

    def spans_for_trace(self, trace_id: str) -> list[Span]:
        return [s for s in self.spans if s.trace_id == trace_id]

    def clear(self) -> None:
        self.spans.clear()


_default_recorder = SpanRecorder()


def get_recorder() -> SpanRecorder:
    return _default_recorder


@contextmanager
def span(name: str, trace_id: str, parent_span_id: str | None = None,
         recorder: SpanRecorder | None = None, **attributes: Any):
    recorder = recorder or get_recorder()
    s = Span(trace_id=trace_id, span_id=str(uuid.uuid4()), parent_span_id=parent_span_id,
             name=name, start_time=time.monotonic(), attributes=dict(attributes))
    try:
        yield s
    except Exception as e:
        s.status = "error"
        s.error = str(e)
        raise
    finally:
        s.end_time = time.monotonic()
        recorder.record(s)
