"""Fail-closed full artifact orchestrator for the submission release.

The quick runner is intentionally portable.  This runner is intentionally not:
it refuses to start the expensive/untrusted evaluation unless the human labels,
held-out manifest, Linux host, Docker daemon, exact locks, and clean Git state
are all ready.  A refusal is a useful result because it prevents a partial run
from being mistaken for submission evidence.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PARENT = ROOT / "artifact" / "results" / "full"
LABEL_A = Path("data/processed/labels_annotator_A.tsv")
LABEL_B = Path("data/processed/labels_annotator_B.tsv")
HELD_OUT = Path("artifact/held-out-manifest.json")
CANDIDATES = Path("artifact/held-out-candidates.json")
SERVER_LOCK = Path("artifact/server-lock.json")
FULL_LOCK = Path("artifact/requirements-full-linux.txt")
ANNOTATION_FREEZE = Path("artifact/round2-annotation-freeze.json")
GIVEN_COLUMNS = ("server_id", "tool", "description", "input_fields", "siblings")
REQUIRED_SERVER_FIELDS = (
    "id", "ecosystem", "package", "version", "integrity",
    "workflow_class", "tool", "runner",
)
EXACT_VERSION = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+(?:[-+][0-9A-Za-z.-]+)?$")


def _read_tsv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def _check_labels(root: Path) -> list[str]:
    issues: list[str] = []
    paths = (root / LABEL_A, root / LABEL_B)
    if not all(path.exists() for path in paths):
        return ["both Round-2 annotator TSV files must exist"]
    rows_a, rows_b = (_read_tsv(path) for path in paths)
    sample_path = root / "data" / "processed" / "label_sheet.tsv"
    sample_rows = _read_tsv(sample_path) if sample_path.exists() else []
    if len(rows_a) != 265 or len(rows_b) != 265:
        issues.append(
            f"Round-2 sheets must each contain 265 rows (found {len(rows_a)} and {len(rows_b)})"
        )
    if len(rows_a) == len(rows_b):
        for index, (left, right) in enumerate(zip(rows_a, rows_b), start=2):
            if any(left.get(key) != right.get(key) for key in GIVEN_COLUMNS):
                issues.append(f"annotator sheets differ in given columns at TSV line {index}")
                break
    if len(sample_rows) != len(rows_a):
        issues.append("frozen label_sheet.tsv row count differs from annotator sheets")
    else:
        for index, (sample, row) in enumerate(zip(sample_rows, rows_a), start=2):
            if any(sample.get(key) != row.get(key) for key in GIVEN_COLUMNS):
                issues.append(f"annotator sheets differ from frozen sample at TSV line {index}")
                break
    for name, rows in (("A", rows_a), ("B", rows_b)):
        invalid = Counter()
        for row in rows:
            label = (row.get("label") or "").strip().upper()
            check = (row.get("check") or "").strip()
            conflict = (row.get("hint_conflict") or "").strip().lower()
            if label not in {"A0", "A1", "A2", "A3"}:
                invalid["label"] += 1
            if not check:
                invalid["check"] += 1
            if conflict not in {"y", "n"}:
                invalid["hint_conflict"] += 1
        if invalid:
            details = ", ".join(f"{key}={value}" for key, value in invalid.items())
            issues.append(f"annotator {name} has incomplete/invalid cells: {details}")
    return issues


def _check_annotation_freeze(root: Path) -> list[str]:
    path = root / ANNOTATION_FREEZE
    if not path.exists():
        return ["artifact/round2-annotation-freeze.json is missing"]
    try:
        freeze = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        return [f"Round-2 annotation freeze is invalid JSON: {error}"]
    files = freeze.get("files")
    if not isinstance(files, dict):
        return ["Round-2 annotation freeze has no file hash map"]
    immutable = (
        "data/processed/label_sheet.tsv",
        "data/processed/label_sheet.corpus_archive.jsonl",
        "data/processed/label_split.json",
        "docs/14-labeling-codebook.md",
    )
    issues: list[str] = []
    for relative in immutable:
        expected = files.get(relative)
        target = root / relative
        if not isinstance(expected, str) or not re.fullmatch(r"[0-9a-fA-F]{64}", expected):
            issues.append(f"annotation freeze lacks a valid hash for {relative}")
        elif not target.exists():
            issues.append(f"annotation freeze target is missing: {relative}")
        elif _sha256(target).lower() != expected.lower():
            issues.append(f"annotation freeze hash mismatch: {relative}")
    return issues


def _check_server_lock(root: Path) -> list[str]:
    path = root / SERVER_LOCK
    if not path.exists():
        return ["artifact/server-lock.json is missing"]
    try:
        entry = json.loads(path.read_text(encoding="utf-8"))["filesystem_mcp"]
    except (json.JSONDecodeError, KeyError, TypeError):
        return ["artifact/server-lock.json has no valid filesystem_mcp entry"]
    issues = []
    if not EXACT_VERSION.fullmatch(str(entry.get("version", ""))):
        issues.append("filesystem-mcp must have an exact semantic version")
    if not re.fullmatch(r"sha512-[0-9A-Za-z+/=]+", str(entry.get("integrity", ""))):
        issues.append("filesystem-mcp must have an npm sha512 integrity")
    return issues


def _check_candidates(root: Path) -> list[str]:
    path = root / CANDIDATES
    if not path.exists():
        return ["artifact/held-out-candidates.json is missing"]
    try:
        inventory = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        return [f"held-out candidate inventory is invalid JSON: {error}"]
    issues: list[str] = []
    primary = inventory.get("primary")
    if not isinstance(primary, list) or len(primary) != 10:
        return ["held-out candidate inventory must contain exactly 10 primary entries"]
    ids = [entry.get("id") for entry in primary if isinstance(entry, dict)]
    if len(set(ids)) != 10:
        issues.append("held-out primary candidate IDs must be unique")
    counts = Counter(
        entry.get("workflow_class_candidate") for entry in primary
        if isinstance(entry, dict)
    )
    for workflow_class in ("EXACT", "CONSTRAINED", "UNDERSPECIFIED"):
        if counts[workflow_class] < 2:
            issues.append(f"candidate class {workflow_class} has fewer than two primaries")
    for index, entry in enumerate(primary, start=1):
        if not isinstance(entry, dict):
            issues.append(f"candidate #{index} is not an object")
            continue
        if not EXACT_VERSION.fullmatch(str(entry.get("version", ""))):
            issues.append(f"candidate {entry.get('id', index)!r} lacks an exact version")
        integrity = str(entry.get("integrity", ""))
        if not re.fullmatch(r"(?:sha512-[0-9A-Za-z+/=]+|sha256:[0-9a-f]{64})", integrity):
            issues.append(f"candidate {entry.get('id', index)!r} has invalid integrity")
    return issues


def _check_held_out(root: Path) -> tuple[list[str], list[list[str]]]:
    path = root / HELD_OUT
    if not path.exists():
        return ["artifact/held-out-manifest.json is missing"], []
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        return [f"held-out manifest is invalid JSON: {error}"], []
    issues: list[str] = []
    if manifest.get("status") != "FROZEN":
        issues.append("held-out manifest status is not FROZEN")
    servers = manifest.get("servers")
    if not isinstance(servers, list):
        return issues + ["held-out manifest servers must be a list"], []
    minimum = int(manifest.get("minimum_independent_servers", 10))
    ids = [server.get("id") for server in servers if isinstance(server, dict)]
    if len(servers) < minimum or len(set(ids)) < minimum:
        issues.append(
            f"held-out set needs {minimum} independent unique servers; found {len(set(ids))}"
        )
    classes = manifest.get("claimed_workflow_classes")
    if not isinstance(classes, list) or not classes:
        issues.append("held-out manifest must name at least one claimed workflow class")
        classes = []
    per_class = int(manifest.get("minimum_per_claimed_workflow_class", 2))
    counts = Counter(
        server.get("workflow_class") for server in servers
        if isinstance(server, dict)
    )
    for workflow_class in classes:
        if counts[workflow_class] < per_class:
            issues.append(
                f"workflow class {workflow_class} needs {per_class} servers; found {counts[workflow_class]}"
            )
    commands: list[list[str]] = []
    for index, server in enumerate(servers, start=1):
        if not isinstance(server, dict):
            issues.append(f"held-out server #{index} is not an object")
            continue
        missing = [field for field in REQUIRED_SERVER_FIELDS if not server.get(field)]
        if missing:
            issues.append(
                f"held-out server {server.get('id', index)!r} is missing {', '.join(missing)}"
            )
            continue
        if not EXACT_VERSION.fullmatch(str(server["version"])):
            issues.append(f"held-out server {server['id']!r} does not use an exact version")
        runner = server["runner"]
        if not isinstance(runner, list) or not runner or not all(
            isinstance(part, str) and part for part in runner
        ):
            issues.append(f"held-out server {server['id']!r} runner must be a command list")
            continue
        commands.append(runner)
    return issues, commands


def _check_full_lock(root: Path) -> list[str]:
    path = root / FULL_LOCK
    if not path.exists():
        return [
            "artifact/requirements-full-linux.txt is missing; generate a transitive hash lock on the release Linux host"
        ]
    text = path.read_text(encoding="utf-8")
    logical: list[str] = []
    current: list[str] = []
    for raw in text.splitlines():
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith("--") and not current:
            continue
        current.append(stripped.removesuffix("\\").strip())
        if not stripped.endswith("\\"):
            logical.append(" ".join(current))
            current = []
    if current:
        logical.append(" ".join(current))
    if not logical or any(
        "==" not in requirement.split()[0]
        or "--hash=sha256:" not in requirement
        for requirement in logical
    ):
        return ["full Linux dependency lock is not exact and hash-pinned"]
    return []


def _git(root: Path, *args: str) -> subprocess.CompletedProcess[str] | None:
    try:
        return subprocess.run(
            ("git", "-c", f"safe.directory={root.as_posix()}", *args),
            cwd=root, check=False, capture_output=True, text=True,
            encoding="utf-8", errors="replace",
        )
    except OSError:
        return None


def preflight(
    root: Path = ROOT, *, check_host: bool = True, require_clean: bool = True,
) -> tuple[list[str], list[list[str]]]:
    issues: list[str] = []
    issues.extend(_check_labels(root))
    issues.extend(_check_annotation_freeze(root))
    issues.extend(_check_server_lock(root))
    issues.extend(_check_candidates(root))
    held_out_issues, held_out_commands = _check_held_out(root)
    issues.extend(held_out_issues)
    issues.extend(_check_full_lock(root))

    if require_clean:
        status = _git(root, "status", "--porcelain")
        if status is None or status.returncode != 0:
            issues.append("Git status could not be read")
        elif status.stdout.strip():
            issues.append("Git worktree is dirty; release evidence requires a committed clean tree")

    if check_host:
        if platform.system() != "Linux":
            issues.append(f"full artifact requires Linux; current host is {platform.system()}")
        docker = shutil.which("docker")
        if docker is None:
            issues.append("Docker executable is unavailable")
        else:
            result = subprocess.run(
                (docker, "info", "--format", "{{.ServerVersion}}"),
                cwd=root, check=False, capture_output=True, text=True,
                encoding="utf-8", errors="replace", timeout=30,
            )
            if result.returncode != 0 or not result.stdout.strip():
                issues.append("Docker daemon is not reachable")
        for binary in ("pdflatex", "bibtex"):
            resolved = shutil.which(binary)
            if resolved is None:
                issues.append(f"{binary} is unavailable for the submission PDF build")
                continue
            result = subprocess.run(
                (resolved, "--version"), cwd=root, check=False,
                capture_output=True, text=True, encoding="utf-8",
                errors="replace", timeout=15,
            )
            if result.returncode != 0:
                issues.append(f"{binary} exists but is not configured successfully")
    return issues, held_out_commands


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _safe_run_dir(parent: Path) -> Path:
    resolved = parent.resolve()
    try:
        resolved.relative_to(ROOT.resolve())
    except ValueError as error:
        raise ValueError("output parent must stay inside the repository") from error
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_dir = resolved / stamp
    suffix = 1
    while run_dir.exists():
        run_dir = resolved / f"{stamp}-{suffix}"
        suffix += 1
    run_dir.mkdir(parents=True)
    return run_dir


def _commands(held_out: list[list[str]]) -> list[tuple[str, list[str]]]:
    commands: list[tuple[str, list[str]]] = [
        ("quick_artifact", [sys.executable, "scripts/run_quick_artifact.py"]),
        ("round2_labels", [
            sys.executable, "experiments/score_labels.py",
            "--a", str(LABEL_A), "--b", str(LABEL_B),
        ]),
        ("integrated_real_server", [
            sys.executable, "experiments/run_m2_real_server.py",
        ]),
    ]
    for index, command in enumerate(held_out, start=1):
        commands.append((f"held_out_{index:02d}", command))
    commands.extend([
        ("figures", [sys.executable, "scripts/make_submission_figures.py"]),
        ("paper_pdf", [sys.executable, "scripts/build_paper_pdf.py"]),
        ("references", [sys.executable, "scripts/verify_refs.py"]),
        ("submission_gate", [
            sys.executable, "scripts/submission_check.py", "--tests",
        ]),
    ])
    return commands


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--preflight-only", action="store_true")
    parser.add_argument(
        "--allow-dirty", action="store_true",
        help="development rehearsal only; never use for release evidence",
    )
    parser.add_argument("--output-parent", type=Path, default=DEFAULT_PARENT)
    args = parser.parse_args()

    issues, held_out = preflight(require_clean=not args.allow_dirty)
    print("Full artifact preflight")
    print("=" * 64)
    if issues:
        for issue in issues:
            print(f"BLOCKED: {issue}")
        print(f"preflight: FAILED ({len(issues)} blocker(s))")
        return 2
    print("preflight: PASS")
    if args.preflight_only:
        return 0

    run_dir = _safe_run_dir(args.output_parent)
    records: list[dict[str, object]] = []
    all_passed = True
    for name, command in _commands(held_out):
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
            "command": command,
            "exit_code": result.returncode,
            "elapsed_seconds": round(elapsed, 6),
            "stdout": stdout_path.name,
            "stdout_sha256": _sha256(stdout_path),
            "stderr": stderr_path.name,
            "stderr_sha256": _sha256(stderr_path),
        })
        print(f"{name}: exit={result.returncode} elapsed={elapsed:.2f}s")
        if result.returncode != 0:
            all_passed = False
            break

    revision = _git(ROOT, "rev-parse", "HEAD")
    metadata = {
        "schema_version": 1,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "git_commit": revision.stdout.strip() if revision and revision.returncode == 0 else None,
        "python": sys.version,
        "platform": platform.platform(),
        "commands": records,
        "all_commands_passed": all_passed,
    }
    metadata_path = run_dir / "run.json"
    metadata_path.write_text(
        json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8",
    )
    manifest_path = run_dir / "MANIFEST.sha256"
    manifest_path.write_text(
        "\n".join(
            f"{_sha256(path)}  {path.name}"
            for path in sorted(run_dir.iterdir(), key=lambda item: item.name)
            if path.is_file() and path != manifest_path
        ) + "\n",
        encoding="utf-8",
    )
    print(f"result_dir: {run_dir.relative_to(ROOT)}")
    print(f"all_commands_passed: {all_passed}")
    return 0 if all_passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
