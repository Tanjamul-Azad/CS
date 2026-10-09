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
SQLITE_SIDECARS = ("-wal", "-shm", "-journal")


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


def fold_sqlite_sidecars(entries: dict) -> dict:
    """Canonical view of a staged tree with SQLite sidecar files folded in.

    ``entries`` maps a path to ``(kind, content)``. A database's ``-wal`` file
    holds committed rows that are not yet in the main file, and ``-shm`` and
    ``-journal`` files come and go with the engine's timing. For every SQLite
    file whose sidecars are present, the database view is computed with its
    write-ahead log applied, and the sidecar entries are removed from the view.
    Removed sidecars are therefore never checked, so they must never be
    promoted: the mediator promotes the checkpointed database only. A sidecar
    without its database stays in the view and is checked like any file.
    (Development change 6, after the cpersona false blocks in batch 2.)
    """
    out = dict(entries)
    for path, (kind, content) in entries.items():
        if kind != "file" or not content or not content.startswith(SQLITE_MAGIC):
            continue
        sidecars = {sfx: entries.get(path + sfx) for sfx in SQLITE_SIDECARS}
        present = {sfx: e for sfx, e in sidecars.items() if e is not None}
        if not present:
            continue
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "db.sqlite"
            db.write_bytes(content)
            wal = present.get("-wal")
            if wal is not None and wal[0] == "file" and wal[1]:
                (Path(tmp) / "db.sqlite-wal").write_bytes(wal[1])
            from .sqlite_mediator import snapshot_sqlite, sqlite_state_text
            try:
                # Apply the log to this trusted-side copy; the snapshot reader
                # opens databases immutable and would otherwise ignore it.
                import sqlite3
                con = sqlite3.connect(db)
                try:
                    con.execute("PRAGMA wal_checkpoint(TRUNCATE)")
                finally:
                    con.close()
                text = sqlite_state_text(snapshot_sqlite(db))
                view = b"sqlite-state\n" + text.encode("utf-8")
            except Exception as error:  # noqa: BLE001
                view = b"sqlite-unreadable " + type(error).__name__.encode() + b"\n"
        out[path] = (kind, view)
        for sfx in present:
            out.pop(path + sfx, None)
    return out
