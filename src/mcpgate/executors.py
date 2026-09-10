"""
Trusted executors -- the only components in the system holding a real
capability.

Each executor implements one small family of effects and is held by the
gateway, never by the server. They are deliberately narrow: an executor
that could perform anything would be as dangerous as the arrangement this
design replaces.

The cost this represents is the architecture's main limitation and should
be reported as a number rather than a caveat: an effect with no trusted
executor cannot be mediated, so the fraction of a real tool ecosystem that
a gateway can cover is bounded by how many executors exist. That fraction
is measured in the accompanying experiment.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from .contract import EffectProposal


@dataclass
class FilesystemExecutor:
    """Writes files, and only inside a root it is given.

    Two independent guards, because they fail differently. The gateway's
    contract check stops a proposal that names the wrong path; this
    executor's root confinement stops a path that escapes the sandbox even
    if the contract were wrong or absent. A capability should not depend on
    the correctness of the policy in front of it.
    """

    root: Path
    operations: frozenset[str] = frozenset({"write_file", "read_file",
                                            "delete_file", "list_files"})
    written: list[Path] = field(default_factory=list)

    def _resolve(self, raw: str) -> Path:
        # resolve() first, THEN compare: "a/../../etc/passwd" only reveals
        # itself as an escape once normalised, and comparing the raw
        # string would pass it straight through.
        p = (self.root / raw).resolve()
        root = self.root.resolve()
        if p != root and root not in p.parents:
            raise PermissionError(
                f"path escapes the executor's root: {raw!r} -> {p}")
        return p

    def perform(self, proposal: EffectProposal):
        op = proposal.operation
        args = proposal.arguments

        if op == "write_file":
            p = self._resolve(args["path"])
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(str(args.get("content", "")), encoding="utf-8")
            self.written.append(p)
            return {"ok": True, "path": str(p.relative_to(self.root.resolve())),
                    "bytes": len(str(args.get("content", "")))}

        if op == "read_file":
            p = self._resolve(args["path"])
            if not p.exists():
                return {"ok": False, "error": "no such file"}
            return {"ok": True, "content": p.read_text(encoding="utf-8")}

        if op == "delete_file":
            p = self._resolve(args["path"])
            existed = p.exists()
            if existed:
                p.unlink()
            return {"ok": True, "deleted": existed}

        if op == "list_files":
            root = self.root.resolve()
            return {"ok": True,
                    "files": sorted(str(q.relative_to(root))
                                    for q in root.rglob("*") if q.is_file())}

        raise ValueError(f"executor does not implement {op!r}")


# Which arguments a contract binds exactly. Both the destination and the
# payload qualify: `path` decides WHERE the effect lands and `content`
# decides WHAT lands, and an integrity mechanism that bound only the first
# would permit a server to write attacker-chosen bytes to the approved
# file -- which is the same compromise by a different route. An earlier
# version of this set bound only `path`, and the head-to-head experiment
# caught it by letting a content-substitution attack straight through.
FILESYSTEM_BINDING_FIELDS = {"path", "content"}
