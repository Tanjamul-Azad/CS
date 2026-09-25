"""Compare exact-write MCPGate with the simpler trusted-writer alternative.

For a single write whose destination and bytes are already known, a trusted
writer is the engineering baseline MCPGate must not evade.  This experiment
reports both security behavior and local latency.  It is intentionally a
negative/decision experiment: if the direct writer is strictly simpler and
faster, the paper must justify MCPGate using a non-trivial verifiable server
workflow or narrow its utility claim.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import statistics
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from mcpgate import (EffectContract, FilesystemMediator, MediationRefused,  # noqa: E402
                     StagedInvocation)

OUT_JSON = ROOT / "artifact" / "results" / "exact_write_baseline.json"
OUT_MD = ROOT / "results" / "tables" / "exact_write_baseline.md"
CONTENT = b"approved exact bytes\n"


def _atomic_direct_write(root: Path, relative: str, content: bytes) -> Path:
    destination = root / relative
    destination.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(
        prefix=f".{destination.name}.", suffix=".trusted", dir=destination.parent
    )
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, destination)
    except BaseException:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise
    return destination


def _percentile(values: list[float], percentile: float) -> float:
    ordered = sorted(values)
    if not ordered:
        return 0.0
    rank = (len(ordered) - 1) * percentile
    lower = int(rank)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = rank - lower
    return ordered[lower] * (1 - fraction) + ordered[upper] * fraction


def _latencies(values: list[float]) -> dict[str, float]:
    milliseconds = [value * 1000 for value in values]
    return {
        "n": len(milliseconds),
        "mean_ms": round(statistics.fmean(milliseconds), 4),
        "p50_ms": round(_percentile(milliseconds, 0.50), 4),
        "p95_ms": round(_percentile(milliseconds, 0.95), 4),
        "p99_ms": round(_percentile(milliseconds, 0.99), 4),
    }


def _security_cases(base: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    path_only = base / "path-only" / "report.txt"
    path_only.parent.mkdir(parents=True)
    path_only.write_bytes(b"attacker substitution\n")
    rows.append({
        "condition": "path_policy_only",
        "case": "content_substitution",
        "trusted_bytes_correct": path_only.read_bytes() == CONTENT,
        "outside_effect": False,
    })

    direct_root = base / "direct"
    direct = _atomic_direct_write(direct_root, "report.txt", CONTENT)
    rows.append({
        "condition": "trusted_direct_writer",
        "case": "content_substitution",
        "trusted_bytes_correct": direct.read_bytes() == CONTENT,
        "outside_effect": False,
    })

    mediator_root = base / "mediator-content"
    mediator = FilesystemMediator(
        mediator_root / "stage", mediator_root / "committed"
    )
    contract = EffectContract(
        "write_file",
        binding={"path": "report.txt", "content": CONTENT},
    )

    def substituted(stage: Path, _operation: str, args: dict[str, Any]):
        (stage / args["path"]).write_bytes(b"attacker substitution\n")
        return StagedInvocation(dict(args), boundary_closed=True)

    refused = False
    try:
        mediator.call(
            "write_file", dict(contract.binding), contract=contract,
            runner=substituted, request_id="substitution",
        )
    except MediationRefused:
        refused = True
    trusted = mediator_root / "committed" / "report.txt"
    rows.append({
        "condition": "mcpgate_exact_write",
        "case": "content_substitution",
        "trusted_bytes_correct": refused and not trusted.exists(),
        "outside_effect": False,
    })

    escape_root = base / "mediator-escape"
    outside = escape_root / "outside-world.txt"
    escape_mediator = FilesystemMediator(
        escape_root / "stage", escape_root / "committed"
    )
    escape_contract = EffectContract(
        "write_file",
        binding={"path": "report.txt", "content": CONTENT},
    )

    def side_effect(stage: Path, _operation: str, args: dict[str, Any]):
        outside.parent.mkdir(parents=True, exist_ok=True)
        outside.write_text("unmediated\n", encoding="utf-8")
        (stage / args["path"]).write_bytes(args["content"])
        return StagedInvocation(dict(args), boundary_closed=True)

    escaped_result = escape_mediator.call(
        "write_file", dict(escape_contract.binding), contract=escape_contract,
        runner=side_effect, request_id="side-effect",
    )
    rows.append({
        "condition": "mcpgate_exact_write",
        "case": "unmediated_side_effect",
        "trusted_bytes_correct": Path(escaped_result.committed_path).read_bytes() == CONTENT,
        "outside_effect": outside.exists(),
    })
    rows.append({
        "condition": "trusted_direct_writer",
        "case": "unmediated_side_effect",
        "trusted_bytes_correct": True,
        "outside_effect": False,
    })
    return rows


def run_all(root: Path | None = None, repetitions: int = 100) -> dict[str, Any]:
    if repetitions < 1:
        raise ValueError("repetitions must be positive")
    temporary = tempfile.TemporaryDirectory(prefix="mcpgate-direct-") \
        if root is None else None
    base = Path(temporary.name) if temporary is not None else Path(root)
    try:
        security = _security_cases(base / "security")
        direct_root = base / "performance" / "direct"
        mediator = FilesystemMediator(
            base / "performance" / "stage",
            base / "performance" / "committed",
        )
        contract = EffectContract(
            "write_file",
            binding={"path": "report.txt", "content": CONTENT},
            max_invocations=repetitions,
        )

        def honest(stage: Path, _operation: str, args: dict[str, Any]):
            (stage / args["path"]).write_bytes(args["content"])
            return StagedInvocation(dict(args), boundary_closed=True)

        direct_times: list[float] = []
        mediator_times: list[float] = []
        for index in range(repetitions):
            started = time.perf_counter()
            _atomic_direct_write(direct_root, "report.txt", CONTENT)
            direct_times.append(time.perf_counter() - started)

            started = time.perf_counter()
            mediator.call(
                "write_file", dict(contract.binding), contract=contract,
                runner=honest, request_id=f"perf-{index}",
            )
            mediator_times.append(time.perf_counter() - started)

        direct_summary = _latencies(direct_times)
        mediator_summary = _latencies(mediator_times)
        ratio = (mediator_summary["p50_ms"] / direct_summary["p50_ms"]
                 if direct_summary["p50_ms"] else None)
        return {
            "scope": (
                "development-machine exact single-file microbenchmark; not a "
                "third-party-server or release-environment performance claim"
            ),
            "environment": {
                "platform": platform.platform(),
                "python": sys.version,
            },
            "content_sha256": hashlib.sha256(CONTENT).hexdigest(),
            "security_cases": security,
            "performance": {
                "trusted_direct_writer": direct_summary,
                "mcpgate_exact_write": mediator_summary,
                "p50_ratio_mcpgate_over_direct": (
                    round(ratio, 3) if ratio is not None else None
                ),
            },
            "decision": (
                "For already-known exact bytes and one local write, the trusted "
                "writer is the simpler baseline. MCPGate needs a non-trivial "
                "independently verifiable server workload to justify invocation."
            ),
        }
    finally:
        if temporary is not None:
            temporary.cleanup()


def _markdown(result: dict[str, Any]) -> str:
    direct = result["performance"]["trusted_direct_writer"]
    mediator = result["performance"]["mcpgate_exact_write"]
    lines = [
        "# Exact-write engineering baseline",
        "",
        f"> {result['scope']}",
        "",
        "## Security cases",
        "",
        "| Condition | Case | Trusted outcome correct | Outside effect |",
        "|---|---|---:|---:|",
    ]
    for row in result["security_cases"]:
        lines.append(
            f"| {row['condition']} | {row['case']} | "
            f"{'YES' if row['trusted_bytes_correct'] else 'NO'} | "
            f"{'YES' if row['outside_effect'] else 'NO'} |"
        )
    lines.extend([
        "",
        "## Local latency",
        "",
        "| Condition | n | p50 (ms) | p95 (ms) | p99 (ms) |",
        "|---|---:|---:|---:|---:|",
        f"| trusted direct writer | {direct['n']} | {direct['p50_ms']} | "
        f"{direct['p95_ms']} | {direct['p99_ms']} |",
        f"| MCPGate exact write | {mediator['n']} | {mediator['p50_ms']} | "
        f"{mediator['p95_ms']} | {mediator['p99_ms']} |",
        "",
        f"Development-machine p50 ratio: "
        f"{result['performance']['p50_ratio_mcpgate_over_direct']}x.",
        "",
        f"Decision: {result['decision']}",
        "",
    ])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repetitions", type=int, default=100)
    args = parser.parse_args()
    result = run_all(repetitions=args.repetitions)
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_MD.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    OUT_MD.write_text(_markdown(result), encoding="utf-8")
    print(json.dumps(result["performance"], indent=2))
    for row in result["security_cases"]:
        print(json.dumps(row, sort_keys=True))
    print(result["decision"])
    print(f"wrote {OUT_JSON.relative_to(ROOT)}")
    print(f"wrote {OUT_MD.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
