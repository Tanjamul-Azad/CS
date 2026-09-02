"""LiveSession command parsing.

Windows-path regression: shlex.split's default POSIX mode treats
backslash as an escape character, which silently corrupts a bare Windows
path argument (`C:\\Users\\...`) into something else. The failure surfaces
far from the cause -- the server process fails to start on the mangled
path and the client sees only "Connection closed" during initialize().
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from mcpmut.live import _split_command  # noqa: E402


def test_windows_path_survives_splitting():
    cmd = r"npx -y @modelcontextprotocol/server-filesystem C:\Users\User\scratch"
    parts = _split_command(cmd)
    assert parts == ["npx", "-y", "@modelcontextprotocol/server-filesystem",
                     r"C:\Users\User\scratch"]


def test_simple_unix_style_command_still_splits_on_whitespace():
    parts = _split_command("uvx some-package --flag value")
    assert parts == ["uvx", "some-package", "--flag", "value"]


def test_backslash_in_path_is_not_treated_as_escape():
    # The historical bug: posix-mode shlex consumes "\U" as an escape,
    # turning C:\Users\x into C:Usersx.
    parts = _split_command(r"cmd C:\Users\x")
    assert parts[-1] == r"C:\Users\x"
