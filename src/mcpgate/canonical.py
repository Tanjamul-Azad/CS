"""Structure-aware canonical views of staged files, for effect templates.

Byte-level templates over container formats are useless: a DOCX is a zip whose
member timestamps change on every write, and a SQLite file's page layout is not
its logical content. Both would otherwise always be L1 (unbounded slack). The
template is therefore inferred and checked over a canonical *view*:

  SQLite database  -> sqlite_state_text (schema lines plus one line per row)
  zip container    -> one "entry <name>" line per member in name order, then
                      the member's text if it is UTF-8, else its SHA-256;
                      zip metadata (member timestamps, order) is excluded

The admitted bytes are still exactly the staged bytes that were checked; the
view only decides what the check means. What the view drops (page layout, zip
timestamps) is unconstrained by construction and must be reported as such.
"""

from __future__ import annotations

import hashlib
import io
import os
import tempfile
import zipfile
from pathlib import Path

SQLITE_MAGIC = b"SQLite format 3\x00"
ZIP_MAGIC = b"PK\x03\x04"


def canonical_view(path: str, content: bytes) -> bytes:
    """Return the canonical view of one staged file (the bytes if no view applies)."""
    if content.startswith(SQLITE_MAGIC):
        return _sqlite_view(content)
    if content.startswith(ZIP_MAGIC):
        return _zip_view(content)
    return content


def _sqlite_view(content: bytes) -> bytes:
    from .sqlite_mediator import snapshot_sqlite, sqlite_state_text
    handle, name = tempfile.mkstemp(suffix=".sqlite")
    try:
        with os.fdopen(handle, "wb") as out:
            out.write(content)
        try:
            text = sqlite_state_text(snapshot_sqlite(Path(name)))
        except Exception as error:  # noqa: BLE001 - unreadable database
            return b"sqlite-unreadable " + type(error).__name__.encode() + b"\n"
        return b"sqlite-state\n" + text.encode("utf-8")
    finally:
        try:
            os.unlink(name)
        except OSError:
            pass


def _zip_view(content: bytes) -> bytes:
    try:
        archive = zipfile.ZipFile(io.BytesIO(content))
    except zipfile.BadZipFile:
        return content
    lines = ["zip-entries"]
    with archive:
        for name in sorted(archive.namelist()):
            data = archive.read(name)
            lines.append(f"entry {name}")
            try:
                lines.append(data.decode("utf-8"))
            except UnicodeDecodeError:
                lines.append("sha256 " + hashlib.sha256(data).hexdigest())
    return ("\n".join(lines) + "\n").encode("utf-8")
