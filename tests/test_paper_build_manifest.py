"""The readiness gate must reject a PDF/source mismatch after a verified build."""
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import submission_check as S

def test_build_manifest_detects_stale_source_and_pdf(tmp_path, monkeypatch):
    source = tmp_path / 'main.tex'
    pdf = tmp_path / 'main.pdf'
    source.write_text('version one')
    pdf.write_bytes(b'PDF one')
    manifest = {'source_sha256': {'main.tex': hashlib.sha256(source.read_bytes()).hexdigest()},
                'pdf_sha256': hashlib.sha256(pdf.read_bytes()).hexdigest()}
    (tmp_path / 'BUILD_MANIFEST.json').write_text(json.dumps(manifest))
    monkeypatch.setattr(S, 'SUBMISSION', tmp_path)
    monkeypatch.setattr(S, 'PDF', pdf)
    assert S.build_manifest_issues() == []
    source.write_text('version two')
    assert S.build_manifest_issues() == ['build source differs: main.tex']
    pdf.write_bytes(b'PDF two')
    assert S.build_manifest_issues() == ['PDF differs from the verified build manifest', 'build source differs: main.tex']
