"""Pin the semantics of the controlled baseline comparison."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "experiments"))

from run_gateway_eval import (Attack, INTENT, World, run_detector,  # noqa: E402
                              run_path_policy, run_plain_sandbox, score)


def _path_attack() -> Attack:
    return Attack("path_diversion", "test", lambda args: {**args, "path": "elsewhere"})


def _content_attack() -> Attack:
    return Attack(
        "content_substitution", "test",
        lambda args: {**args, "content": "attacker"},
    )


def test_plain_sandbox_does_not_add_a_per_call_effect_policy(tmp_path):
    attack = _content_attack()
    result = run_plain_sandbox(attack, tmp_path)
    outcome = score(World(tmp_path).state(), attack)
    assert result["sandboxed"] is True
    assert outcome["attack_prevented"] is False
    assert outcome["task_completed"] is False


def test_path_policy_blocks_diversion_but_not_allowed_path_content(tmp_path):
    path_root = tmp_path / "path"
    path_attack = _path_attack()
    path_result = run_path_policy(path_attack, path_root)
    assert path_result["blocked"] is True
    assert score(World(path_root).state(), path_attack)["attack_prevented"] is True

    content_root = tmp_path / "content"
    content_attack = _content_attack()
    content_result = run_path_policy(content_attack, content_root)
    assert content_result["blocked"] is False
    assert score(World(content_root).state(), content_attack)["attack_prevented"] is False


def test_response_auditor_surfaces_path_diversion_but_does_not_prevent_it(tmp_path):
    attack = _path_attack()
    result = run_detector(attack, tmp_path)
    outcome = score(World(tmp_path).state(), attack)
    assert result["alerted"] is True
    assert result["blocked"] is False
    assert outcome["attack_prevented"] is False
