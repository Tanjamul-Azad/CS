"""The network admission model: the full design holds, each ablation breaks
exactly the invariant its mechanism protects (mirror of formal/EffectSealNet.tla)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "formal"))
from check_net_model import CONFIGS, check  # noqa: E402

EXPECTED = {
    "NetFull": None,
    "NetNoPreSend": "OnlyApprovedSent",
    "NetNoCredInjection": "NoCredentialLeak",
    "NetNotConfined": "OnlyApprovedSent",
    "NetNoAtomicCount": "SendBound",
    "NetNoReplayGuard": "SendBound",
}


def test_each_mechanism_is_necessary_and_full_design_holds():
    for name, flags in CONFIGS.items():
        result = check(flags)
        if EXPECTED[name] is None:
            assert result["result"] == "all invariants hold"
            assert result["distinct_states"] == 441  # TLC: formal/tlc/NetFull.log
        else:
            assert result["invariants"] == [EXPECTED[name]], name
