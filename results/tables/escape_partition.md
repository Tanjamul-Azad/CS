# Verification escape channels

Which structural escape each server offers. ENUM (enumeration) is the most common and was never implemented as a typed check, which is the direct explanation for 0% detection. NONE is the structural floor: no client-side check exists there at any budget.

| Escape available | Servers | Share |
|---|---|---|
| ENUM | 558 | 45.9% |
| NONE | 308 | 25.3% |
| ENUM+SNAP | 258 | 21.2% |
| SNAP | 47 | 3.9% |
| CONS+ENUM+SNAP | 26 | 2.1% |
| CONS+ENUM | 17 | 1.4% |
| CONS | 2 | 0.2% |
| **any escape** | 908 | 74.7% |

*Source: `data/processed/escape_partition.json`. Regenerate with `python experiments/make_results.py`.*
