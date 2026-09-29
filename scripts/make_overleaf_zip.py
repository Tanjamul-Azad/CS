"""Zip only what paper/submission needs to compile (for Overleaf)."""
import re
import zipfile
from pathlib import Path

root = Path(__file__).resolve().parents[1] / "paper" / "submission"
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

out = Path(__file__).resolve().parents[2] / "EffectSeal_Overleaf.zip"  # outside the repo
with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
    for f in files:
        z.write(f, f.relative_to(root).as_posix())
print("files:", len(files), "missing:", missing)
for f in files:
    print("  ", f.relative_to(root).as_posix())
print("zip size MB:", round(out.stat().st_size / 1e6, 2))
