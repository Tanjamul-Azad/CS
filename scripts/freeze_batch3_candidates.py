"""Freeze the ordered candidate list for the third held-out batch (workstream H).

Applies the batch-2 selection rule (artifact/held-out-batch2-candidates.json,
"selection_rule") as code, over the same sources, with a new seed. Every server
already used in development, the first held-out set and its reserves, or the
second batch's candidate list is excluded, so batch 3 contains only servers
never looked at before. Metadata only: nothing is installed or launched.

    python scripts/freeze_batch3_candidates.py
"""

from __future__ import annotations

import hashlib
import json
import random
import re
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "data" / "processed" / "registry_candidates.json"
SCALE = ROOT / "data" / "processed" / "scale_run.json"
OUT = ROOT / "artifact" / "held-out-batch3-candidates.json"
SEED = "heldout-batch3-2026-10-09"
TAKE = 45  # ordered list length; screening stops once enough pass eligibility

SURFACE = re.compile(r"\b(file|files|note|notes|memory|memories|document|documents|docs?|"
                     r"sqlite|markdown|journal|diary|knowledge|todo|task|tasks|bookmark|"
                     r"snippet|wiki|vault|notebook)\b", re.I)
LOCAL = re.compile(r"\b(local|local-first|sqlite|markdown|on-disk|on disk|folder|directory|"
                   r"vault|offline|private|filesystem|file system)\b", re.I)
REMOTE = re.compile(r"(https?://|\bweb\b|\bwebsite|\bemail|\bupload|\bshare\b|\bonline\b|"
                    r"\bscreenshot|\bquote|\bpaid\b|\brss\b|\bfeed\b|\bdeploy|\bsubscription|"
                    r"\bcloud\b|\bapi key|\bgithub\b|\bslack\b|\bnotion\b|\bgoogle\b|"
                    r"\bdropbox\b|\bs3\b|\bremote\b|\bsaas\b|\bhosted\b)", re.I)


def ids_from(path: Path, *keys: str) -> set[str]:
    if not path.exists():
        return set()
    data = json.loads(path.read_text(encoding="utf-8"))
    out: set[str] = set()

    def walk(node):
        if isinstance(node, dict):
            for k, v in node.items():
                if k in ("id", "server_id") and isinstance(v, str):
                    out.add(v)
                else:
                    walk(v)
        elif isinstance(node, list):
            for v in node:
                if isinstance(v, str) and "/" in v:
                    out.add(v)
                else:
                    walk(v)
    walk(data)
    return out


def main() -> None:
    used = set()
    for name in ("held-out-manifest.json", "held-out-candidates.json",
                 "held-out-batch2-candidates.json", "held-out-batch2-manifest.json",
                 "held-out-batch2-pinned.json"):
        used |= ids_from(ROOT / "artifact" / name)
    registry = {r["server_id"]: r for r in json.loads(REGISTRY.read_text(encoding="utf-8"))}
    scale = {r["server_id"]: r for r in json.loads(SCALE.read_text(encoding="utf-8"))}
    kept, network_excluded, counts = [], [], {"ok_launch": 0, "pkg": 0, "surface": 0}
    for sid, run in scale.items():
        if run.get("status") != "ok" or sid in used:
            continue
        counts["ok_launch"] += 1
        meta = registry.get(sid)
        if not meta or meta.get("registry_type") not in ("npm", "pypi"):
            continue
        counts["pkg"] += 1
        text = f"{meta.get('title') or ''} {meta.get('description') or ''}"
        # Batch 2 required both cues; that rule leaves only 15 unused servers,
        # too few for a 10-server batch after attrition. Batch 3 requires
        # either cue. The local, no-network requirement is still enforced by
        # pre-effect eligibility: the container has no network, and the honest
        # workflow's effect must land in the client-selected folder.
        if not (SURFACE.search(text) or LOCAL.search(text)):
            continue
        counts["surface"] += 1
        if REMOTE.search(text):
            network_excluded.append(sid)
            continue
        kept.append({"id": sid, "ecosystem": meta["registry_type"],
                     "package": meta["identifier"], "write_tool": run.get("write_tool"),
                     "text": text.strip()[:240]})
    kept.sort(key=lambda r: r["id"])
    random.Random(SEED).shuffle(kept)
    result = {
        "schema_version": 1, "status": "FROZEN_BEFORE_ANY_OUTCOME",
        "selected_utc_date": date.today().isoformat(),
        "purpose": "third held-out batch (workstream H): pin-time templates after development "
                   "changes 5-7, on servers never used in development or earlier batches",
        "source": "data/processed/registry_candidates.json joined with data/processed/scale_run.json",
        "source_sha256": {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                          for p in (REGISTRY, SCALE)},
        "selection_rule": [
            "not used in development, the first held-out set or its reserves, or batch 2",
            "scale-run status 'ok' (launched without credentials, answered tools/list, exposed a write tool)",
            "npm or PyPI stdio package",
            "title/description names a local surface (SURFACE regex) OR a local-storage cue "
            "(LOCAL regex), both in scripts/freeze_batch3_candidates.py; batch 2 required both, "
            "which leaves too few unused servers; the local, no-network requirement is enforced "
            "by pre-effect eligibility",
            "description states no network dependency (REMOTE regex)",
            f"remaining servers sorted by id, shuffled with seed '{SEED}', first {TAKE} taken; "
            "screening stops once at least 10 pass eligibility",
        ],
        "replacement_rule": "a server is skipped only for pre-effect install, launch, handshake, or "
                            "honest-workflow incompatibility, never for any EffectSeal or baseline outcome",
        "counts": {**counts, "after_network_rule": len(kept), "excluded_used": len(used)},
        "network_excluded": sorted(network_excluded),
        "ordered_candidates": kept[:TAKE],
    }
    OUT.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(result["counts"], indent=2))
    for i, r in enumerate(result["ordered_candidates"][:12], 1):
        print(f"{i:2d} {r['id']} ({r['ecosystem']}) write={r['write_tool']}")


if __name__ == "__main__":
    main()
