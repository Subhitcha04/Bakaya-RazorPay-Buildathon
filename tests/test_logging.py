import io
import json

from app.observability.logging import log_event, info, warning, error


def test_log_event_writes_valid_json():
    stream = io.StringIO()
    log_event("info", "diagnostician", "diagnosed case", trace_id="t1", stream=stream)
    line = stream.getvalue().strip()
    record = json.loads(line)
    assert record["level"] == "info"
    assert record["component"] == "diagnostician"
    assert record["message"] == "diagnosed case"
    assert record["trace_id"] == "t1"


def test_log_event_includes_extra_structured_fields():
    stream = io.StringIO()
    log_event("info", "strategist", "proposed action", trace_id="t1", stream=stream,
               ladder_level="L3", confidence=0.9)
    record = json.loads(stream.getvalue().strip())
    assert record["ladder_level"] == "L3"
    assert record["confidence"] == 0.9


def test_log_event_has_a_numeric_timestamp():
    stream = io.StringIO()
    record = log_event("info", "x", "y", stream=stream)
    assert isinstance(record["timestamp"], float)


def test_info_warning_error_set_correct_levels():
    stream = io.StringIO()
    assert info("c", "m", stream=stream)["level"] == "info"
    stream = io.StringIO()
    assert warning("c", "m", stream=stream)["level"] == "warning"
    stream = io.StringIO()
    assert error("c", "m", stream=stream)["level"] == "error"


def test_trace_id_defaults_to_none_when_not_provided():
    stream = io.StringIO()
    record = log_event("info", "c", "m", stream=stream)
    assert record["trace_id"] is None
