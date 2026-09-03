"""
Atomic JSON checkpoint writes.

`Path.write_text(json.dumps(...))` is NOT atomic: it opens the file
(truncating whatever was there) and then writes the new content in a
separate step. If anything interrupts that window -- disk full, the
process killed, a power loss -- the file is left in whatever partial
state the write reached, which can mean a checkpoint that took hours to
build is silently replaced by 0 bytes.

This is exactly what happened: a scale run's disk filled mid-checkpoint,
the write started (truncating the 350-result checkpoint to empty) and
then failed with ENOSPC before any content landed, and the next process
start read an empty file and had nothing to resume from. Every
long-running harvester in this project checkpoints the same way and is
equally exposed.

The fix is the standard one: write the new content to a temp file in the
same directory, then os.replace() it onto the real path. os.replace is
atomic on a given filesystem -- the destination is either the complete
old file or the complete new file, never a partial write, regardless of
what interrupts the process in between.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any


def atomic_write_text(path: Path, text: str) -> None:
    """The same guarantee as atomic_write_json, for callers building their
    own text (e.g. JSONL corpora written line by line) rather than a
    single JSON-serializable object."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(
        dir=str(path.parent), prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
        os.replace(tmp_name, path)
    except BaseException:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


def atomic_write_json(path: Path, data: Any, **json_kwargs: Any) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(
        dir=str(path.parent), prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, **json_kwargs)
        os.replace(tmp_name, path)
    except BaseException:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise
