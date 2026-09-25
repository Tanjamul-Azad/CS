from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from prepare_usenix_source import convert, inline  # noqa: E402


def test_inline_converts_citations_code_and_unicode():
    rendered = inline("Use `tool_name` [@source2026] → 20%.")
    assert r"\texttt{\detokenize{tool_name}}" in rendered
    assert r"\cite{source2026}" in rendered
    assert r"\rightarrow" in rendered
    assert r"20\%" in rendered


def test_converter_omits_working_banner_and_blocker_ledger():
    source = """# Title

> **Working manuscript — not submission-ready.** Banner.

## Abstract

Abstract text.

## 1. Introduction

Body [@key].

## Submission blocker ledger

| Blocker | State |
|---|---|
| x | y |
"""
    rendered = convert(source, manuscript=True)
    assert r"\begin{abstract}" in rendered
    assert r"\section{Introduction}" in rendered
    assert "fig1_mcpgate_architecture.pdf" in rendered
    assert r"\cite{key}" in rendered
    assert "Working manuscript" not in rendered
    assert "Submission blocker" not in rendered


def test_fragment_drops_title_and_demotes_sections():
    rendered = convert("# Appendix\n\n## A. Scope\n\nText.\n", fragment=True)
    assert "# Appendix" not in rendered
    assert r"\subsection{A. Scope}" in rendered
