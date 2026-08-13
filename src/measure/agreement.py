"""
Inter-annotator agreement and classifier validation.

The A0-A3 classifier is a heuristic instrument. Its output is the paper's
headline number, so its error has to be characterised rather than
assumed. Two things are needed and they are different:

  1. AGREEMENT between two human annotators (Cohen's kappa) -- shows the
     codebook is well enough specified that the label is reproducible.
     Without this, "we labelled them" means nothing.

  2. ACCURACY of the automatic classifier against the human gold standard
     -- per-class precision/recall, since a systematic bias toward or
     away from A0 moves the headline directly.

Report both. High kappa with poor classifier accuracy means the concept
is sound but the code is wrong; low kappa means the concept itself is
underspecified and no amount of code fixes it.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

CLASSES = ("A0", "A1", "A2", "A3")


def cohens_kappa(a: list[str], b: list[str]) -> float:
    """Chance-corrected agreement between two annotators.

    kappa = (po - pe) / (1 - pe). Returns 1.0 for perfect agreement,
    0.0 for agreement no better than chance, negative for worse.
    """
    if len(a) != len(b):
        raise ValueError("annotation lists must be the same length")
    n = len(a)
    if n == 0:
        return 0.0

    po = sum(1 for x, y in zip(a, b) if x == y) / n
    ca, cb = Counter(a), Counter(b)
    pe = sum((ca[c] / n) * (cb[c] / n) for c in set(a) | set(b))
    if abs(1 - pe) < 1e-12:
        return 1.0
    return (po - pe) / (1 - pe)


def interpret_kappa(k: float) -> str:
    """Landis & Koch (1977) bands. Conventional, and worth citing as such."""
    if k < 0.0:
        return "worse than chance"
    if k < 0.20:
        return "slight"
    if k < 0.40:
        return "fair"
    if k < 0.60:
        return "moderate"
    if k < 0.80:
        return "substantial"
    return "almost perfect"


@dataclass
class ClassMetrics:
    label: str
    support: int
    precision: float
    recall: float

    @property
    def f1(self) -> float:
        if self.precision + self.recall == 0:
            return 0.0
        return 2 * self.precision * self.recall / (self.precision + self.recall)


def classifier_report(gold: list[str], pred: list[str]) -> list[ClassMetrics]:
    """Per-class precision/recall of the automatic classifier vs humans."""
    out = []
    for c in CLASSES:
        tp = sum(1 for g, p in zip(gold, pred) if g == c and p == c)
        fp = sum(1 for g, p in zip(gold, pred) if g != c and p == c)
        fn = sum(1 for g, p in zip(gold, pred) if g == c and p != c)
        out.append(ClassMetrics(
            label=c,
            support=sum(1 for g in gold if g == c),
            precision=tp / (tp + fp) if tp + fp else 0.0,
            recall=tp / (tp + fn) if tp + fn else 0.0,
        ))
    return out


def confusion(gold: list[str], pred: list[str]) -> dict[tuple[str, str], int]:
    return Counter(zip(gold, pred))


def print_validation(gold: list[str], pred: list[str], title: str = "") -> None:
    print(f"\n{'='*64}")
    print(f"CLASSIFIER VALIDATION{(' -- ' + title) if title else ''}")
    print("=" * 64)
    acc = sum(1 for g, p in zip(gold, pred) if g == p) / max(len(gold), 1)
    print(f"  n={len(gold)}  overall accuracy={100*acc:.1f}%")

    print(f"\n  {'class':6} {'support':>8} {'precision':>10} {'recall':>8} {'F1':>7}")
    for m in classifier_report(gold, pred):
        print(f"  {m.label:6} {m.support:8} {100*m.precision:9.1f}% "
              f"{100*m.recall:7.1f}% {100*m.f1:6.1f}%")

    print("\n  confusion (gold -> predicted)")
    cm = confusion(gold, pred)
    print("        " + "".join(f"{c:>6}" for c in CLASSES))
    for g in CLASSES:
        row = "".join(f"{cm.get((g,p),0):6}" for p in CLASSES)
        print(f"  {g:6}" + row)

    # The number that matters most for the headline.
    a0_gold = sum(1 for g in gold if g == "A0")
    a0_pred = sum(1 for p in pred if p == "A0")
    if a0_gold:
        bias = (a0_pred - a0_gold) / len(gold)
        print(f"\n  A0 bias: classifier says {100*a0_pred/len(gold):.1f}%, "
              f"humans say {100*a0_gold/len(gold):.1f}% "
              f"({100*bias:+.1f} points)")
        print("  This bias applies directly to the headline and must be")
        print("  reported alongside it, not silently corrected.")
