from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PLAN = ROOT / "artifact" / "held-out-evaluation-plan.json"
MANIFEST = ROOT / "artifact" / "held-out-manifest.json"


def test_plan_is_frozen_before_outcomes_and_bound_to_manifest() -> None:
    plan = json.loads(PLAN.read_text(encoding="utf-8"))
    assert plan["status"] == "FROZEN_PRE_OUTCOME"
    assert plan["outcomes_observed_before_freeze"] is False
    assert plan["source_manifest_sha256"] == hashlib.sha256(
        MANIFEST.read_bytes()
    ).hexdigest()


def test_all_frozen_servers_have_one_plan() -> None:
    plan = json.loads(PLAN.read_text(encoding="utf-8"))
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    planned = [row["id"] for row in plan["server_plans"]]
    frozen = [row["id"] for row in manifest["servers"]]
    assert planned == frozen
    assert len(planned) == len(set(planned)) == 10


def test_five_conditions_and_scenario_partition_are_explicit() -> None:
    plan = json.loads(PLAN.read_text(encoding="utf-8"))
    assert [row["id"] for row in plan["conditions"]] == [
        "NONE", "MBA", "STATIC_LP", "PLAIN_SANDBOX", "MCPGATE"
    ]
    scenarios = {row["id"] for row in plan["scenario_catalog"]}
    for server in plan["server_plans"]:
        applicable = set(server["applicable"])
        not_applicable = set(server["not_applicable"])
        assert applicable.isdisjoint(not_applicable)
        assert applicable | not_applicable == scenarios


def test_stochastic_cases_have_one_hundred_repetitions() -> None:
    repetitions = json.loads(PLAN.read_text(encoding="utf-8"))["repetitions"]
    assert repetitions["overlap_per_server_condition"] >= 100
    assert repetitions["background_writer_per_applicable_server_condition"] >= 100

