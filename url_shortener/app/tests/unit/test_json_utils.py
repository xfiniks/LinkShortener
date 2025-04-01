import pytest
from datetime import datetime, timezone
import orjson
from app.json_utils import dumps, loads

def test_dumps_basic():
    data = {"key": "value", "number": 42}
    json_str = dumps(data)
    assert isinstance(json_str, str)
    assert '"key":"value"' in json_str.replace(" ", "")
    assert '"number":42' in json_str.replace(" ", "")

def test_dumps_with_datetime():
    now = datetime.now(timezone.utc)
    data = {"timestamp": now}
    json_str = dumps(data)

    assert isinstance(json_str, str)
    assert "timestamp" in json_str

def test_dumps_with_indent():
    data = {"nested": {"key": "value"}}
    json_str = dumps(data, indent=True)
    assert isinstance(json_str, str)

    assert "\n" in json_str or "  " in json_str

def test_loads_basic():
    json_str = '{"key": "value", "number": 42}'
    data = loads(json_str)
    assert data["key"] == "value"
    assert data["number"] == 42

def test_loads_with_bytes():
    json_bytes = b'{"key": "value"}'
    data = loads(json_bytes)
    assert data["key"] == "value"