"""
Does a launchability candidate's declared package actually exist on a
registry? Static analysis (launchability.py) can only see that a
pyproject.toml or package.json DECLARES a name -- it cannot tell a
published package from one whose author never ran `twine upload` or
`npm publish`. The Phase 1 pilot found this is not a corner case: of 24
launch failures across the 32 "runnable standalone" servers, 10 failed
with "No solution found when resolving tool dependencies" or an npm 404 --
the declared name simply is not on the registry.

This closes that gap with one cheap HTTP call per candidate, run BEFORE
any container is launched, so the pool a docker scale run attempts is one
that can plausibly succeed rather than one discovered to be dead only
after paying for the install attempt.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass

TIMEOUT = 10
USER_AGENT = "mcp-behavioral-integrity-research/0.1 (academic study)"


@dataclass
class RegistryStatus:
    package: str
    ecosystem: str          # "pypi" | "npm"
    exists: bool
    checked_ok: bool         # False if the check itself errored (network),
                             # distinct from a confirmed absence
    detail: str = ""


def _get(url: str) -> tuple[int, bytes]:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, b""
    except Exception as e:  # noqa: BLE001
        return -1, str(e).encode()


def check_pypi(package: str) -> RegistryStatus:
    status, body = _get(f"https://pypi.org/pypi/{package}/json")
    if status == 200:
        return RegistryStatus(package, "pypi", True, True)
    if status == 404:
        return RegistryStatus(package, "pypi", False, True, "404")
    return RegistryStatus(package, "pypi", False, False,
                          f"check failed: status={status}")


def check_npm(package: str) -> RegistryStatus:
    # npm package names can be scoped (@scope/name); the registry API
    # wants the slash percent-encoded.
    encoded = package.replace("/", "%2f")
    status, body = _get(f"https://registry.npmjs.org/{encoded}")
    if status == 200:
        return RegistryStatus(package, "npm", True, True)
    if status == 404:
        return RegistryStatus(package, "npm", False, True, "404")
    return RegistryStatus(package, "npm", False, False,
                          f"check failed: status={status}")


def check(package: str, ecosystem: str) -> RegistryStatus:
    if ecosystem == "pypi":
        return check_pypi(package)
    if ecosystem == "npm":
        return check_npm(package)
    raise ValueError(f"unknown ecosystem: {ecosystem}")
