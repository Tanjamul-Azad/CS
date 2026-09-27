"""Split judge results by whether the adversary actually kept the transcript honest.

The observation boundary applies only when the attacked transcript is
indistinguishable from an honest one. Our interposition adversary is not
perfect: where it fails to mask an API, the transcript itself changes. This
script decides "leaked" WITHOUT any judge: an attacked transcript leaked if its
normalized server responses and auditor read-back results match none of the
same server's honest transcripts. Normalization removes clock values and
long hex/uuid identifiers, which differ between any two honest runs.

This split was defined after seeing the v2 verdicts (post hoc); the criterion
itself uses no verdict.
"""

from __future__ import annotations

import json
import math
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from mcpgate.template_inference import _CLOCK  # noqa: E402

TRANSCRIPTS = ROOT / "artifact" / "results" / "llm_judge_transcripts_v2.json"
VERDICTS = ROOT / "artifact" / "results" / "llm_judge_v2.json"
OUT = ROOT / "artifact" / "results" / "llm_judge_v2_leak_split.json"
HEX = re.compile(r"\b[0-9a-f]{8,}\b|\b[0-9a-f]{8}-[0-9a-f-]{27,}\b", re.I)


def norm(text: str) -> str:
    return HEX.sub("<id>", _CLOCK.sub("<clock>", text))


def signature(row: dict) -> str:
    parts = [norm(r) for r in row["response"]]
    parts += [norm(c["tool"] + json.dumps(c["arguments"], sort_keys=True) + c["result"])
              for c in row["auditor_calls"]]
    return "\n".join(parts)


def wilson(k, n, z=1.959964):
    if n == 0:
        return [None, None]
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return [round(max(0, c - h), 4), round(min(1, c + h), 4)]


def main() -> int:
    rows = json.loads(TRANSCRIPTS.read_text(encoding="utf-8"))["rows"]
    honest_sigs = defaultdict(set)
    for r in rows:
        if r["scenario"] == "H0":
            honest_sigs[r["server_id"]].add(signature(r))
    leaked = {}
    for r in rows:
        if r["scenario"] != "H0" and r["landed"]:
            leaked[(r["server_id"], r["scenario"], r["tier"], r["rep"])] = (
                signature(r) not in honest_sigs[r["server_id"]])
    verdicts = json.loads(VERDICTS.read_text(encoding="utf-8"))["verdicts"]
    summary = {"leak_rate": {}}
    for tier in ("naive", "consistent"):
        keys = [k for k in leaked if k[2] == tier]
        summary["leak_rate"][tier] = [sum(leaked[k] for k in keys), len(keys)]
    for model in sorted({v["model"] for v in verdicts}):
        mine = [v for v in verdicts if v["model"] == model]
        honest = [v for v in mine if v["scenario"] == "H0"]
        entry = {"honest_fpr": [sum(v["verdict"] == "UNSAFE" for v in honest), len(honest)]}
        for tier in ("naive", "consistent"):
            for leak in (True, False):
                sel = [v for v in mine if v["scenario"] != "H0" and v["tier"] == tier
                       and leaked.get((v["server_id"], v["scenario"], v["tier"], v["rep"])) is leak]
                k = sum(v["verdict"] == "UNSAFE" for v in sel)
                entry[f"{tier}_{'leaked' if leak else 'indistinguishable'}"] = {
                    "flagged": k, "n": len(sel), "wilson": wilson(k, len(sel))}
        entry["honest_fpr"].append(wilson(*entry["honest_fpr"]))
        summary[model] = entry
    OUT.write_text(json.dumps({"summary": summary,
                               "leaked": [list(k) + [v] for k, v in leaked.items()]}, indent=2) + "\n",
                   encoding="utf-8")
    print(json.dumps(summary, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
