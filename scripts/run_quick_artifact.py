"""Run the offline quick artifact and preserve auditable result metadata.

This runner deliberately excludes Docker, third-party package installation,
network calls, and the still-failing submission-readiness gate.  It verifies
the checked-in implementation and demonstrations that are expected to run on a
fresh local checkout once ``artifact/requirements-quick.txt`` is installed.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
import platform
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PARENT = ROOT / "artifact" / "results" / "quick"
COMMANDS = (
    ("pytest", (sys.executable, "-m", "pytest", "-q")),
    ("theorem1", (sys.executable, "experiments/demo_theorem1.py")),
    ("effect_oracle", (sys.executable, "experiments/run_effect_oracle.py")),
    ("gateway_eval", (sys.executable, "experiments/run_gateway_eval.py")),
    ("controlled_ablations", (
        sys.executable, "experiments/run_mediator_ablations.py"
    )),
    ("concurrency_eval", (
        sys.executable, "experiments/run_concurrency_eval.py"
    )),
    ("exact_write_baseline", (
        sys.executable, "experiments/run_exact_write_baseline.py",
        "--repetitions", "100",
    )),
    ("matched_filesystem_table", (
        sys.executable, "scripts/summarize_matched.py",
    )),
    ("matched_stats", (sys.executable, "scripts/matched_stats.py")),
    ("figures", (sys.executable, "scripts/make_submission_figures.py")),
    ("usenix_source", (
        sys.executable, "scripts/prepare_usenix_source.py", "--check",
    )),
    ("reference_gate", (sys.executable, "scripts/verify_refs.py")),
)
PACKAGES = ("httpx", "mcp", "pydantic", "pytest", "requests")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _git(*args: str) -> str | None:
    try:
        result = subprocess.run(
            ("git", *args), cwd=ROOT, check=False, capture_output=True,
            text=True, encoding="utf-8", errors="replace",
        )
    except OSError:
        return None
    return result.stdout.strip() if result.returncode == 0 else None


def _versions() -> dict[str, str | None]:
    versions: dict[str, str | None] = {}
    for name in PACKAGES:
        try:
            versions[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            versions[name] = None
    return versions


def _safe_run_dir(parent: Path) -> Path:
    resolved_parent = parent.resolve()
    try:
        resolved_parent.relative_to(ROOT.resolve())
    except ValueError as exc:
        raise ValueError("output parent must stay inside the repository") from exc
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    candidate = resolved_parent / stamp
    suffix = 1
    while candidate.exists():
        candidate = resolved_parent / f"{stamp}-{suffix}"
        suffix += 1
    candidate.mkdir(parents=True)
    return candidate


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output-parent", type=Path, default=DEFAULT_PARENT,
        help="repository-internal parent for a new timestamped result directory",
    )
    args = parser.parse_args()
    run_dir = _safe_run_dir(args.output_parent)

    records: list[dict[str, object]] = []
    all_passed = True
    for name, command in COMMANDS:
        started = time.perf_counter()
        result = subprocess.run(
            command, cwd=ROOT, check=False, capture_output=True, text=True,
            encoding="utf-8", errors="replace", env=os.environ.copy(),
        )
        elapsed = time.perf_counter() - started
        stdout_path = run_dir / f"{name}.stdout.txt"
        stderr_path = run_dir / f"{name}.stderr.txt"
        stdout_path.write_text(result.stdout, encoding="utf-8")
        stderr_path.write_text(result.stderr, encoding="utf-8")
        records.append({
            "name": name,
            "command": list(command),
            "exit_code": result.returncode,
            "elapsed_seconds": round(elapsed, 6),
            "stdout": stdout_path.name,
            "stdout_sha256": _sha256(stdout_path),
            "stderr": stderr_path.name,
            "stderr_sha256": _sha256(stderr_path),
        })
        all_passed &= result.returncode == 0
        print(f"{name}: exit={result.returncode} elapsed={elapsed:.2f}s")

    status = _git("status", "--porcelain")
    metadata = {
        "schema_version": 1,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "git_commit": _git("rev-parse", "HEAD"),
        "git_dirty": None if status is None else bool(status),
        "python": sys.version,
        "python_executable": sys.executable,
        "platform": platform.platform(),
        "machine": platform.machine(),
        "packages": _versions(),
        "commands": records,
        "all_commands_passed": all_passed,
    }
    metadata_path = run_dir / "run.json"
    metadata_path.write_text(
        json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8",
    )

    manifest_path = run_dir / "MANIFEST.sha256"
    manifest_lines = [
        f"{_sha256(path)}  {path.name}"
        for path in sorted(run_dir.iterdir(), key=lambda item: item.name)
        if path.is_file() and path != manifest_path
    ]
    manifest_path.write_text("\n".join(manifest_lines) + "\n", encoding="utf-8")
    print(f"result_dir: {run_dir.relative_to(ROOT)}")
    print(f"all_commands_passed: {all_passed}")
    return 0 if all_passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
