"""Atomic checkpoint writes.

Regression for a real data loss: a scale run's disk filled mid-write,
which truncated a 350-result checkpoint to 0 bytes rather than leaving
the previous complete content in place -- write_text() is not atomic.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from measure.atomic_io import atomic_write_json  # noqa: E402


def test_writes_valid_json(tmp_path):
    p = tmp_path / "out.json"
    atomic_write_json(p, {"a": 1, "b": [1, 2, 3]})
    assert json.loads(p.read_text(encoding="utf-8")) == {"a": 1, "b": [1, 2, 3]}


def test_overwrites_cleanly(tmp_path):
    p = tmp_path / "out.json"
    atomic_write_json(p, {"v": 1})
    atomic_write_json(p, {"v": 2})
    assert json.loads(p.read_text(encoding="utf-8")) == {"v": 2}


def test_failed_write_leaves_old_content_intact(tmp_path):
    """The core property: a write that fails partway must not destroy
    what was there before -- the historical bug this replaces truncated
    the file to 0 bytes on exactly this kind of failure."""
    p = tmp_path / "out.json"
    atomic_write_json(p, {"good": "checkpoint", "n": 350})

    with patch("json.dump", side_effect=OSError("No space left on device")):
        try:
            atomic_write_json(p, {"this": "should never land"})
        except OSError:
            pass

    assert json.loads(p.read_text(encoding="utf-8")) == {
        "good": "checkpoint", "n": 350}


def test_no_leftover_temp_file_after_failure(tmp_path):
    p = tmp_path / "out.json"
    with patch("json.dump", side_effect=OSError("disk full")):
        try:
            atomic_write_json(p, {"x": 1})
        except OSError:
            pass
    leftovers = list(tmp_path.glob(f".{p.name}.*.tmp"))
    assert leftovers == []


def test_creates_parent_directories(tmp_path):
    p = tmp_path / "nested" / "dir" / "out.json"
    atomic_write_json(p, {"ok": True})
    assert json.loads(p.read_text(encoding="utf-8")) == {"ok": True}


def test_indent_kwarg_passed_through(tmp_path):
    p = tmp_path / "out.json"
    atomic_write_json(p, {"a": 1}, indent=2)
    text = p.read_text(encoding="utf-8")
    assert "\n" in text  # pretty-printed, not a single line
