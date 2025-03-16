import pytest
from datetime import datetime
from main import parse_release_line

def test_parse_release_line_valid():
    line = "## v1.2.3 (2021-12-31)"
    result = parse_release_line(line)
    assert result is not None
    assert result["version"] == "v1.2.3"
    assert result["release_date"] == datetime(2021, 12, 31)

def test_parse_release_line_valid_extra_spaces():
    line = "##   v2.0.0    (2022-01-01)"
    result = parse_release_line(line)
    assert result is not None
    assert result["version"] == "v2.0.0"
    assert result["release_date"] == datetime(2022, 1, 1)

def test_parse_release_line_invalid_missing_date():
    # Missing date part
    line = "## v1.2.3"
    result = parse_release_line(line)
    assert result is None

def test_parse_release_line_invalid_additional_text():
    # Additional text after date causes mismatch
    line = "## v1.2.3 (2021-12-31) extra"
    result = parse_release_line(line)
    assert result is None

def test_parse_release_line_empty_string():
    line = ""
    result = parse_release_line(line)
    assert result is None

def test_parse_release_line_wrong_date_format():
    # Date not in YYYY-MM-DD format
    line = "## v3.0.0 (31-12-2021)"
    result = parse_release_line(line)
    assert result is None