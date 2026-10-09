"""Development change 6: SQLite sidecar files are folded into the database view."""

import sqlite3
from pathlib import Path

from mcpgate.canonical import fold_sqlite_sidecars


def _wal_database(tmp_path: Path):
    db = tmp_path / "notes.sqlite"
    con = sqlite3.connect(db)
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA wal_autocheckpoint=0")
    con.execute("CREATE TABLE notes (id INTEGER PRIMARY KEY, body TEXT)")
    con.execute("INSERT INTO notes (body) VALUES ('kept only in the wal')")
    con.commit()
    entries = {"notes.sqlite": ("file", db.read_bytes())}
    for sfx in ("-wal", "-shm"):
        side = Path(str(db) + sfx)
        if side.exists():
            entries["notes.sqlite" + sfx] = ("file", side.read_bytes())
    return con, entries


def test_wal_rows_reach_the_view_and_sidecars_leave_it(tmp_path):
    con, entries = _wal_database(tmp_path)
    try:
        assert "notes.sqlite-wal" in entries
        folded = fold_sqlite_sidecars(entries)
    finally:
        con.close()
    assert set(folded) == {"notes.sqlite"}
    kind, view = folded["notes.sqlite"]
    assert kind == "file" and view.startswith(b"sqlite-state")
    assert b"kept only in the wal" in view


def test_view_is_the_same_with_or_without_sidecars(tmp_path):
    con, entries = _wal_database(tmp_path)
    try:
        con.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        checkpointed = {"notes.sqlite": ("file", (tmp_path / "notes.sqlite").read_bytes())}
        folded_wal = fold_sqlite_sidecars(entries)
    finally:
        con.close()
    from mcpgate.canonical import canonical_view
    plain = canonical_view("notes.sqlite", checkpointed["notes.sqlite"][1])
    assert folded_wal["notes.sqlite"][1] == plain


def test_orphan_sidecar_is_still_checked(tmp_path):
    entries = {"other.db-wal": ("file", b"arbitrary bytes")}
    assert fold_sqlite_sidecars(entries) == entries
