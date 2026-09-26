"""Put src/ and tests/ on the path so tests run from anywhere."""

import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
for p in (ROOT / "src", ROOT / "tests"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))


def pytest_configure(config):
    """Use a writable base temp directory.

    Some Windows environments deny access to pytest's default base temp under
    the user %TEMP% (WinError 5), which fails the suite for reasons unrelated to
    any test. When no basetemp is given explicitly, redirect it to a
    repository-local directory that is known to be writable.
    """
    if config.option.basetemp:
        return
    base = ROOT / ".pytest_tmp"
    try:
        base.mkdir(exist_ok=True)
        probe = base / ".probe"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
    except OSError:
        base = Path(tempfile.mkdtemp(prefix="mcpgate-pytest-"))
    config.option.basetemp = str(base / "bt")
    os.environ.setdefault("PYTEST_DEBUG_TEMPROOT", str(base))
