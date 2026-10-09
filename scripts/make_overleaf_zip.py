"""Zip only what paper/submission needs to compile (for Overleaf)."""
import re
import argparse
import datetime as dt
import hashlib
import json
import zipfile
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--output", type=Path)
parser.add_argument("--source", type=Path, help="local source directory, including a sanitized anonymous export")
args = parser.parse_args()
root = args.source.resolve() if args.source else Path(__file__).resolve().parents[1] / "paper" / "submission"
main = (root / "main.tex").read_text(encoding="utf-8")
sections = re.findall(r"\\input\{(sections/[^}]+)\}", main)
text = main + "".join((root / f"{s}.tex").read_text(encoding="utf-8") for s in sections)

figs = set()
for ref in re.findall(r"\\includegraphics(?:\[[^\]]*\])?\{([^}]+)\}", text):
    p = root / ref
    if p.suffix:
        hits = [p]
    else:
        hits = [q for q in (p.with_suffix(".pdf"), p.with_suffix(".png")) if q.exists()]
    figs.update(h for h in hits if h.exists())

files = [root / "main.tex", root / "usenix.sty", root / "references.bib"]
files += [root / f"{s}.tex" for s in sections] + sorted(figs)
missing = [str(f) for f in files if not f.exists()]

out = args.output or (Path(__file__).resolve().parents[2] / ("EffectSeal_Overleaf_" + dt.datetime.now().strftime("%Y%m%d-%H%M%S") + ".zip"))  # outside the repo
if missing:
    raise SystemExit("missing source files: " + str(missing))
if out.exists():
    raise SystemExit("refusing to overwrite existing archive: " + str(out))
manifest = {f.relative_to(root).as_posix(): hashlib.sha256(f.read_bytes()).hexdigest() for f in files}
with zipfile.ZipFile(out, "x", zipfile.ZIP_DEFLATED) as z:
    for f in files:
        z.write(f, f.relative_to(root).as_posix())
    z.writestr("SOURCE_SHA256.json", json.dumps(manifest, indent=2))
with zipfile.ZipFile(out) as z:
    for name, digest in manifest.items():
        if hashlib.sha256(z.read(name)).hexdigest() != digest:
            raise SystemExit("archive verification failed: " + name)
print("files:", len(files), "missing:", missing)
for f in files:
    print("  ", f.relative_to(root).as_posix())
print("ARCHIVE", out)
print("zip size MB:", round(out.stat().st_size / 1e6, 2))
