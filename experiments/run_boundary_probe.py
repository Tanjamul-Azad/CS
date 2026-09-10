"""
M2 -- does a real boundary confine a real adversarial server, and how much
of a per-call authorization does it actually enforce?

Runs `experiments/boundary/probe.py` inside the project's container, where
enforcement is real: the protected directory belongs to the gateway's user
and is not writable by the user the untrusted server runs as. The server
is a separate OS process that actively attacks -- symlinks, pre-opened
descriptors, child processes, writes after responding -- and every verdict
is decided by an observer reading the filesystem, never by the server's
own account.

This replaces the same-process callback used in tests/test_gateway.py.
That callback could show a proposal being validated; it could not show
execution authority actually removed, because a Python function that does
not write has only chosen not to.

    python experiments/run_boundary_probe.py
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "processed" / "boundary_probe.json"
IMAGE = "mcpaudit-runner:latest"
DOCKER_ENV = {**os.environ, "MSYS_NO_PATHCONV": "1", "MSYS2_ARG_CONV_EXCL": "*"}


def run() -> list[dict]:
    # Runs as root inside the container so the gateway user can own
    # /protected while the server drops to `sandbox`. Nothing is mounted
    # from the host: the protected area lives and dies with the container.
    cmd = ["docker", "run", "--rm", "--user", "0:0",
           "--memory=512m", "--cpus=1", "--pids-limit=256",
           "--security-opt=no-new-privileges",
           "--entrypoint", "python3", IMAGE, "/app/boundary/probe.py"]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300,
                          env=DOCKER_ENV)
    if proc.returncode != 0:
        print("probe failed inside the container:\n", proc.stderr[-3000:])
        sys.exit(1)
    return json.loads(proc.stdout)


def report(rows: list[dict]) -> None:
    print("=" * 96)
    print("PRELIMINARY CONTROL EXPERIMENT -- executor-mediated gateway with")
    print("coarse process isolation, paired against an undefended control")
    print("=" * 96)
    print("\nThis is NOT milestone M2. M2 requires the CONFINED SERVER to")
    print("perform the effect while a generic boundary enforces the contract.")
    print("Here the gateway performs it through a per-tool FilesystemExecutor,")
    print("and the server cannot write at all -- so the authorization-to-")
    print("boundary translation problem, which is the actual research")
    print("question, is untested. See docs/25 for what M2 needs.\n")

    by = {}
    for r in rows:
        by.setdefault(r["scenario"], {})[r["condition"]] = r

    print(f"{'scenario':<22}{'undefended':>12}{'defended':>10}"
          f"{'completion':>16}  blocked by")
    print("-" * 96)
    for name, pair in by.items():
        u, d = pair.get("undefended", {}), pair.get("defended", {})
        print(f"{name:<22}{u.get('confinement_verdict', '-'):>12}"
              f"{d.get('confinement_verdict', '-'):>10}"
              f"{d.get('completion_verdict', '-'):>16}"
              f"  {d.get('blocked_by', '-')}")

    # Prevention coverage, defined only where the undefended control shows
    # a real unauthorized effect. Counting scenarios instead would let an
    # attack the server could never have pulled off inflate the rate.
    landed_undefended = [n for n, p in by.items()
                         if p.get("undefended", {}).get("confinement_verdict")
                         == "VIOLATED"]
    prevented = [n for n in landed_undefended
                 if by[n].get("defended", {}).get("confinement_verdict")
                 != "VIOLATED"]

    print("\n" + "=" * 96)
    print("  PREVENTION COVERAGE -- over attacks the undefended control")
    print("  actually demonstrated, not over scenarios we wrote")
    print(f"\n    demonstrated undefended : {len(landed_undefended)}"
          f"  ({', '.join(landed_undefended) or 'none'})")
    print(f"    prevented when defended : {len(prevented)}")
    if landed_undefended:
        print(f"    coverage                : "
              f"{100*len(prevented)/len(landed_undefended):.0f}%")
    else:
        print("    coverage                : undefined -- no attack landed "
              "even undefended")

    never = [n for n in by if n not in landed_undefended
             and n not in ("honest", "silent_noop")]
    if never:
        print(f"\n  Attacks that did NOT land even undefended: {', '.join(never)}")
        print("  These contribute nothing to a prevention rate. Counting them")
        print("  would credit the defense for an attack that never worked.")

    d_rows = [r for r in rows if r["condition"] == "defended"]
    violated = [r for r in d_rows if r["confinement_verdict"] == "VIOLATED"]
    unknown = [r for r in d_rows if r["confinement_verdict"] == "UNKNOWN"]
    if violated:
        print("\n  CONFINEMENT VIOLATED under the defense:")
        for r in violated:
            print(f"    {r['scenario']:<22} {', '.join(r['unauthorized_effects'])}")
    if unknown:
        print("\n  UNKNOWN -- the evidence does not settle it:")
        for r in unknown:
            print(f"    {r['scenario']:<22} {r['unknown_reason']}")

    print("\n  MECHANISM ATTRIBUTION -- what did the blocking, and only for")
    print("  the attacks the undefended control actually demonstrated:")
    mech: dict[str, list[str]] = {}
    for name in landed_undefended:
        mech.setdefault(by[name]["defended"].get("blocked_by", "-"), []).append(name)
    for k, names in sorted(mech.items(), key=lambda kv: -len(kv[1])):
        print(f"    {k:<20} {len(names):>2}  {', '.join(names)}")
    print("\n  These are different jobs. A boundary sees paths and")
    print("  permissions; it cannot tell that a proposed destination is the")
    print("  wrong one or that the payload was substituted. Those refusals")
    print("  came from the contract, and no amount of sandboxing supplies")
    print("  them. Confinement is not authorization.")

    # What the OS refused, according to the server itself. Recorded as
    # the adversary's own account and cross-checked against observation.
    print("\n  bypass attempts the server REPORTED making (defended run):")
    for r in d_rows:
        for a in r["server_claimed_attempts"]:
            print(f"    {r['scenario']:<22} {a}")

    print("\n  NOT EVIDENCE. These lines are written by the adversary. The")
    print("  observer proves no forbidden effect landed; it does NOT prove")
    print("  the syscall was attempted and refused by the kernel -- a server")
    print("  that skipped the attempt entirely would look identical here.")
    print("  Establishing that needs a trusted syscall record: strace from")
    print("  the parent, auditd/eBPF, a seccomp-notify log, or FUSE")
    print("  mediation. Until then read 'blocked (PermissionError)' as an")
    print("  unverified claim, not a measurement.")


def main() -> None:
    rows = run()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(rows, indent=1), encoding="utf-8")
    report(rows)
    print(f"\nwrote {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
