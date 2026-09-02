"""
Verify every launchability candidate's declared package actually exists
on PyPI/npm, and correct `runnable_standalone` to require it.

Static triage can only see that a manifest DECLARES a name; the Phase 1
pilot found 10 of 24 launch failures were simply packages nobody ever
published. This is the fix -- one HTTP call per candidate, before any
container is spent on a name that cannot possibly resolve.

    python experiments/run_registry_check.py
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from measure.registry_check import check  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
TRIAGE = ROOT / "data" / "processed" / "triage.json"
OUT = ROOT / "data" / "processed" / "triage_registry.json"

ECOSYSTEM = {"npm-published": "npm", "py-published": "pypi", "py-module": "pypi"}


def main() -> None:
    rows = json.loads(TRIAGE.read_text(encoding="utf-8"))
    candidates = [r for r in rows if r["launch_class"] in ECOSYSTEM and r["package"]]
    print(f"{len(rows)} triaged servers; {len(candidates)} declare an "
          f"installable package name\n")

    checked = []
    for i, r in enumerate(candidates, 1):
        eco = ECOSYSTEM[r["launch_class"]]
        st = check(r["package"], eco)
        r = dict(r)
        r["registry_checked"] = st.checked_ok
        r["registry_exists"] = st.exists
        r["registry_detail"] = st.detail
        # runnable_standalone now additionally requires registry existence.
        # A network check failure (not a confirmed 404) does NOT flip a
        # server to unrunnable -- that would conflate "we could not verify"
        # with "confirmed absent", the same mistake the triage timeout bug
        # made once already.
        if st.checked_ok and not st.exists:
            r["runnable_standalone"] = False
        checked.append(r)
        mark = "OK " if st.exists else ("N/A" if not st.checked_ok else "gone")
        print(f"  [{i}/{len(candidates)}] {mark}  {eco:5} {r['package']}")
        time.sleep(0.1)

    by_id = {r["server_id"]: r for r in checked}
    merged = [by_id.get(r["server_id"], r) for r in rows]
    OUT.write_text(json.dumps(merged, indent=1), encoding="utf-8")

    before = sum(1 for r in rows if r["runnable_standalone"])
    after = sum(1 for r in merged if r["runnable_standalone"])
    gone = [r["server_id"] for r in rows if r["runnable_standalone"]
           and r["server_id"] not in
           {x["server_id"] for x in merged if x["runnable_standalone"]}]

    print(f"\nrunnable_standalone: {before} -> {after} after registry check")
    if gone:
        print(f"removed ({len(gone)}), package never published:")
        for sid in gone:
            print("  ", sid)
    print(f"\nwrote {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
