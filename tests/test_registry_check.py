"""Registry existence checks.

Exists because static manifest analysis cannot tell a published package
from a name that only lives in a repo's pyproject.toml/package.json --
the Phase 1 pilot found 15 of 32 "runnable standalone" servers were
exactly that, and every one of them failed identically at container
launch with a resolver error, only discoverable after paying for the
docker attempt. These tests pin the HTTP-status interpretation without
making real network calls.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from measure.registry_check import check, check_npm, check_pypi  # noqa: E402


def test_200_means_exists():
    with patch("measure.registry_check._get", return_value=(200, b"{}")):
        st = check_pypi("real-package")
        assert st.exists is True
        assert st.checked_ok is True


def test_404_means_confirmed_absent():
    with patch("measure.registry_check._get", return_value=(404, b"")):
        st = check_pypi("never-published")
        assert st.exists is False
        assert st.checked_ok is True  # this IS a confirmed answer


def test_network_failure_is_not_confirmed_absence():
    """A -1/timeout status must not be treated the same as a real 404 --
    that would silently reclassify a server as unrunnable because OUR
    network had a bad moment, which is exactly the mistake the triage
    timeout bug made once already (see run_triage.py)."""
    with patch("measure.registry_check._get", return_value=(-1, b"timeout")):
        st = check_pypi("maybe-exists")
        assert st.exists is False
        assert st.checked_ok is False


def test_npm_scoped_package_name_is_percent_encoded():
    captured = {}

    def fake_get(url):
        captured["url"] = url
        return 200, b"{}"

    with patch("measure.registry_check._get", side_effect=fake_get):
        check_npm("@scope/name")
    assert "@scope%2fname" in captured["url"]


def test_dispatch_routes_to_correct_ecosystem():
    with patch("measure.registry_check._get", return_value=(200, b"{}")) as m:
        check("pkg", "pypi")
        assert "pypi.org" in m.call_args[0][0]
        check("pkg", "npm")
        assert "registry.npmjs.org" in m.call_args[0][0]


def test_unknown_ecosystem_raises():
    import pytest
    with pytest.raises(ValueError):
        check("pkg", "cargo")
