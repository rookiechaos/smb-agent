from __future__ import annotations

import pytest

from smbagent._jsonx import extract_json


def test_bare_json_object():
    assert extract_json('{"a": 1}') == {"a": 1}


def test_fenced_json_block():
    text = 'Here is the result:\n```json\n{"a": 1}\n```\nDone.'
    assert extract_json(text) == {"a": 1}


def test_fenced_block_without_lang():
    text = '```\n{"a": 1}\n```'
    assert extract_json(text) == {"a": 1}


def test_nested_object_in_fenced_block():
    """Regression: original regex used non-greedy {.*?} which stopped at the first }."""
    text = '```json\n{"plan": {"summary": "ok", "tasks": [{"id": "T1"}]}, "extra": 2}\n```'
    result = extract_json(text)
    assert result == {"plan": {"summary": "ok", "tasks": [{"id": "T1"}]}, "extra": 2}


def test_json_embedded_in_prose():
    text = 'The agent says: {"done": true, "requirements": {"goals": ["X"]}} and stops.'
    result = extract_json(text)
    assert result["done"] is True
    assert result["requirements"] == {"goals": ["X"]}


def test_first_fenced_block_wins_when_multiple():
    text = '```json\n{"first": 1}\n```\nand later\n```json\n{"second": 2}\n```'
    assert extract_json(text) == {"first": 1}


def test_array_at_top_level():
    assert extract_json("[1, 2, 3]") == [1, 2, 3]


def test_skips_invalid_fenced_block_and_finds_valid_one():
    text = '```json\n{not json\n```\n```json\n{"a": 1}\n```'
    assert extract_json(text) == {"a": 1}


def test_no_json_raises():
    with pytest.raises(ValueError):
        extract_json("there is no json here at all")


def test_braces_in_strings_dont_confuse_decoder():
    text = '```json\n{"text": "this has } in it"}\n```'
    assert extract_json(text) == {"text": "this has } in it"}
