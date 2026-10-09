"""Evidence tampering and reproduction failures must be visible to reviewers."""
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from verify_current_evidence import check_hashes

def test_evidence_hash_check_refuses_changed_and_escaping_members(tmp_path):
    data = tmp_path / 'traffic.jsonl'
    data.write_text('{"sent":true}\n')
    manifest = {'traffic.jsonl': hashlib.sha256(data.read_bytes()).hexdigest()}
    (tmp_path / 'SHA256SUMS.json').write_text(json.dumps(manifest))
    assert check_hashes(tmp_path) == []
    data.write_text('{"sent":false}\n')
    assert check_hashes(tmp_path) == ['hash mismatch: traffic.jsonl']
    manifest = {'../outside.json': '0' * 64}
    (tmp_path / 'SHA256SUMS.json').write_text(json.dumps(manifest))
    assert check_hashes(tmp_path) == ['missing/unsafe member: ../outside.json']

@pytest.mark.skipif(os.name == 'nt', reason='Linux shell exit-status regression')
def test_clean_linux_runner_propagates_a_failed_step(tmp_path):
    shell = shutil.which('sh')
    assert shell
    bin_dir = tmp_path / 'bin'
    bin_dir.mkdir()
    python = bin_dir / 'python'
    python.write_text('#!/bin/sh\ncase "$*" in *formal/check_model.py*) exit 7;; *) exit 0;; esac\n')
    python.chmod(0o755)
    env = {**os.environ, 'PATH': str(bin_dir) + os.pathsep + os.environ['PATH'],
           'OUT': str(tmp_path / 'out'), 'SKIP_INSTALL': '1'}
    run = subprocess.run([shell, str(ROOT / 'scripts/reproduce_clean_linux.sh')],
                         cwd=ROOT, env=env, capture_output=True, text=True)
    assert run.returncode == 1
    summary = (tmp_path / 'out/summary.txt').read_text()
    assert 'FAIL tla_local_model (exit 7)' in summary
    assert 'PASS figures_network' in summary
