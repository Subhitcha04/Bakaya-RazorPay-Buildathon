import pytest

from app.observability.tracing import span, SpanRecorder, new_trace_id


def test_span_records_trace_id_and_name():
    recorder = SpanRecorder()
    trace_id = new_trace_id()
    with span("diagnose", trace_id=trace_id, recorder=recorder):
        pass
    recorded = recorder.spans_for_trace(trace_id)
    assert len(recorded) == 1
    assert recorded[0].name == "diagnose"


def test_span_duration_is_nonnegative():
    recorder = SpanRecorder()
    trace_id = new_trace_id()
    with span("work", trace_id=trace_id, recorder=recorder):
        pass
    s = recorder.spans[0]
    assert s.duration_seconds is not None
    assert s.duration_seconds >= 0


def test_nested_spans_share_trace_id_and_link_parent():
    recorder = SpanRecorder()
    trace_id = new_trace_id()
    with span("outer", trace_id=trace_id, recorder=recorder) as outer:
        with span("inner", trace_id=trace_id, parent_span_id=outer.span_id, recorder=recorder) as inner:
            pass
    spans = recorder.spans_for_trace(trace_id)
    assert len(spans) == 2
    inner_span = next(s for s in spans if s.name == "inner")
    outer_span = next(s for s in spans if s.name == "outer")
    assert inner_span.parent_span_id == outer_span.span_id


def test_exception_inside_span_is_recorded_as_error_and_reraised():
    recorder = SpanRecorder()
    trace_id = new_trace_id()
    with pytest.raises(ValueError):
        with span("failing_work", trace_id=trace_id, recorder=recorder):
            raise ValueError("boom")
    s = recorder.spans[0]
    assert s.status == "error"
    assert s.error == "boom"


def test_spans_for_trace_ignores_other_traces():
    recorder = SpanRecorder()
    t1, t2 = new_trace_id(), new_trace_id()
    with span("a", trace_id=t1, recorder=recorder):
        pass
    with span("b", trace_id=t2, recorder=recorder):
        pass
    assert len(recorder.spans_for_trace(t1)) == 1
    assert len(recorder.spans_for_trace(t2)) == 1


def test_span_attributes_can_be_set_inside_the_block():
    recorder = SpanRecorder()
    trace_id = new_trace_id()
    with span("diagnose", trace_id=trace_id, recorder=recorder) as s:
        s.attributes["root_cause"] = "insufficient_funds"
    assert recorder.spans[0].attributes["root_cause"] == "insufficient_funds"
