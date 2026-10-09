"""File-arm baselines: what AgentBound, ToolHive, and srt enforce on local
filesystem effects, with the literal evidence gathered and the mapping to the
matched filesystem conditions already measured.

On a local file server the matched harness already runs the exact container the
three tools configure: a read-only root filesystem, one writable bind mount for
the client-selected area, and no network. Their file-effect guarantee therefore
coincides with conditions the paper already reports, so this records the
mechanism and evidence rather than re-running identical containers.

  ToolHive   --isolate-network: a network host:port allow-list, no filesystem
             rule in its permission profile -> no file mediation -> PLAIN_SANDBOX.
  AgentBound FSAccess {path, read, write}: a writable bind mount of the granted
             path(s). Binds destination, not content -> STATIC_LP (per-path
             grant) or PLAIN_SANDBOX (whole-directory grant).
  srt        filesystem.allowWrite (allow-only): a per-path write boundary ->
             STATIC_LP. Its Windows host-OS enforcement (srt-sandbox account +
             working-tree ACEs) did not engage in our virtualized environment,
             recorded below; the mechanism is taken from its documented policy.

The matched numbers these map onto (artifact/results/matched_filesystem.json):
PLAIN_SANDBOX 9/31 attacks prevented, STATIC_LP 18/31, EffectSeal 31/31, each
at 5/5 honest completion.

    python experiments/make_file_baselines.py
"""

from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MATCHED = ROOT / "artifact" / "results" / "matched_filesystem.json"
OUT = ROOT / "artifact" / "results" / "file_baselines.json"


def matched_by_condition() -> dict:
    data = json.loads(MATCHED.read_text(encoding="utf-8"))
    cells = [c for s in data["servers"] for c in s.get("cells", [])]
    out = {}
    for cond in ("NONE", "PLAIN_SANDBOX", "MBA", "STATIC_LP", "MCPGATE"):
        cc = [c for c in cells if c["condition"] == cond]
        h0 = [c for c in cc if c["scenario"] == "H0"]
        atk = [c for c in cc if c["mutation_attempted"]]
        out[cond] = {"honest_completed": sum(c["authorized_effect"] for c in h0),
                     "honest_total": len(h0),
                     "attacks_prevented": sum(c["prevented"] for c in atk),
                     "attacks_total": len(atk)}
    return out


def main() -> int:
    conditions = matched_by_condition()
    baselines = {
        "ToolHive": {
            "version": "v0.51.4", "ran_literally": False,
            "enforcement_object": "network host:port allow-list (--isolate-network)",
            "filesystem_rule": "none; the permission profile has no filesystem-write field",
            "file_arm_class": "PLAIN_SANDBOX",
            "reason": ("ToolHive governs only egress; on a --network=none file server it "
                       "mediates no file write, so its file guarantee is the container "
                       "blast radius, identical to PLAIN_SANDBOX."),
        },
        "AgentBound": {
            "artifact": "FSE 2026, doi 10.5281/zenodo.19571298", "ran_literally": False,
            "enforcement_object": "FSAccess {path, read, write} -> writable bind mount of granted path",
            "filesystem_rule": "mounts only granted paths writable; binds destination, not content",
            "file_arm_class": "STATIC_LP (per-path grant) or PLAIN_SANDBOX (whole-directory grant)",
            "reason": ("A writable bind mount of /sandbox is exactly the matched container. It "
                       "stops writes outside the granted path (already impossible under the "
                       "read-only root) but admits any content or extra file within it, as "
                       "STATIC_LP does."),
        },
        "srt": {
            "package": "@anthropic-ai/sandbox-runtime", "version": "0.0.79", "ran_literally": True,
            "windows_install": "completed (srt-sandbox account + WFP filters provisioned)",
            "enforcement_object": "filesystem.allowWrite (allow-only write list)",
            "filesystem_rule": "per-path write boundary; deny-by-default outside allowWrite",
            "file_arm_class": "STATIC_LP",
            "literal_attempt": {
                "c_drive": "refused: working directory on C: reported as DRIVE_REMOTE under the "
                           "sandbox logon (per-user drive mappings absent in the virtualized env)",
                "f_drive": "ran, but filesystem enforcement did not engage: with an EMPTY "
                           "allowWrite a write to the workspace still succeeded, and --debug "
                           "showed WFP non-elevated (BFE enumeration admin-only) with no "
                           "working-tree ACE taking effect",
                "conclusion": "environment limitation, not srt policy; a literal file number "
                              "from this host would misrepresent srt, so its guarantee is taken "
                              "from the documented allow-only write mechanism (STATIC_LP class)",
            },
        },
    }
    result = {
        "schema_version": 1,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "phase": "FILE_ARM_BASELINES_MECHANISM_AND_MAPPING",
        "note": ("On local file effects AgentBound, ToolHive, and srt enforce the container "
                 "configuration the matched harness already runs (read-only root, one writable "
                 "client-area mount, no network). Their file guarantees therefore coincide with "
                 "measured conditions rather than adding a new number."),
        "matched_source": "artifact/results/matched_filesystem.json",
        "matched_conditions": conditions,
        "baselines": baselines,
        "takeaway": ("Every destination- or sandbox-class file baseline lands at PLAIN_SANDBOX "
                     f"({conditions['PLAIN_SANDBOX']['attacks_prevented']}/"
                     f"{conditions['PLAIN_SANDBOX']['attacks_total']} attacks prevented) or "
                     f"STATIC_LP ({conditions['STATIC_LP']['attacks_prevented']}/"
                     f"{conditions['STATIC_LP']['attacks_total']}); EffectSeal prevents "
                     f"{conditions['MCPGATE']['attacks_prevented']}/"
                     f"{conditions['MCPGATE']['attacks_total']}, all at "
                     f"{conditions['MCPGATE']['honest_completed']}/"
                     f"{conditions['MCPGATE']['honest_total']} honest completion."),
    }
    OUT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"matched_conditions": conditions,
                      "takeaway": result["takeaway"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
