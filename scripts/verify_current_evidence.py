"""Check the active network evidence offline, including controls and real races."""
import datetime as dt
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'scripts'), str(ROOT / 'experiments'), str(ROOT / 'src')]
from verify_network_bundle import verify
from mcpgate.request_templates import RequestObservation, infer_request_template
import network_postmark_pilot as P
from measure_integrated_network import percentiles
import analyze_matched_judges as J
import reanalyze_local_capacity as C

def check_hashes(path):
    errors = []
    hashes = json.loads((path / 'SHA256SUMS.json').read_text(encoding='utf-8'))
    for name, digest in hashes.items():
        target = (path / name).resolve()
        if not target.is_relative_to(path.resolve()) or not target.is_file():
            errors.append('missing/unsafe member: ' + name)
        elif hashlib.sha256(target.read_bytes()).hexdigest() != digest:
            errors.append('hash mismatch: ' + name)
    return errors

def main():
    pointers = json.loads((ROOT / 'artifact/paper-evidence-20261009.json').read_text(encoding='utf-8'))
    results = []
    for key in ['network_matched', 'additional_network_held_out', 'network_named', 'network_postmark']:
        result = verify(ROOT / 'artifact/results' / pointers[key])
        result['key'] = key
        results.append(result)
    for key in ['network_integrated', 'network_crosssession', 'additional_selection']:
        path = ROOT / 'artifact/results' / pointers[key]
        errors = check_hashes(path)
        if key == 'network_integrated':
            r = json.loads((path / 'result.json').read_text(encoding='utf-8'))
            valid = all(x['effects'] == 1 and x['statuses'].count(200) == 1
                        and x['statuses'].count(403) == 7 for x in r['races'])
            if not valid or len(r['races']) != r['trials'] or r['restart_replay_status'] != 403 or not r['all_pass']:
                errors.append('race/restart result differs')
            if {k: percentiles(v) for k, v in r['samples_ns'].items()} != r['timings']:
                errors.append('timing percentiles differ')
        elif key == 'network_crosssession':
            r = json.loads((path / 'result.json').read_text(encoding='utf-8'))
            for condition in r['results']:
                sessions = condition['sessions']
                for s in sessions:
                    template = infer_request_template('sendEmail', [RequestObservation(p['args'], P.observation(p, 'call'),
                        dt.datetime.fromisoformat(p['started'])) for p in s['pins']],
                        credential_headers=frozenset({P.TOKEN_HEADER.lower()}))
                    if template.to_json() != s['template']:
                        errors.append('control template differs: ' + condition['condition'])
                faithful = all(P.oracle(p)['faithful_effect'] for s in sessions for p in s['pins'])
                if faithful != condition['training_effects_faithful'] or (sessions[0]['template'] == sessions[1]['template']) != condition['templates_agree']:
                    errors.append('control verdict differs: ' + condition['condition'])
        else:
            rows = [json.loads(line) for line in (path / 'screening.jsonl').read_text(encoding='utf-8').splitlines()]
            sets = json.loads((path / 'sets.json').read_text(encoding='utf-8'))
            if len(rows) != sets['screened'] or [x['name'] for x in rows if x.get('qualified')] != sets['held_out'] or sets['development']:
                errors.append('selection qualifiers differ')
        results.append({'key': key, 'passed': not errors, 'errors': errors})
    judge = json.loads((ROOT / 'artifact/results' / pointers['judge_matched_sensitivity']).read_text(encoding='utf-8'))
    inputs = [ROOT / 'artifact/results' / n for n in ['llm_judge_transcripts_v2.json', 'llm_judge_v2.json', 'llm_judge_ollama_v2.json']]
    errors = []
    if any(hashlib.sha256(p.read_bytes()).hexdigest() != judge['source_hashes'][p.name] for p in inputs):
        errors.append('judge source hash differs')
    if json.loads(json.dumps(J.analyze(inputs))) != judge['models']:
        errors.append('judge matched pairs/rates differ')
    results.append({'key': 'judge_matched_sensitivity', 'passed': not errors, 'errors': errors})
    capacities = json.loads((ROOT / 'artifact/results' / pointers['local_capacity_reanalysis']).read_text(encoding='utf-8'))
    errors = [] if C.analyze() == capacities['rows'] else ['local capacity reanalysis differs']
    results.append({'key': 'local_capacity_reanalysis', 'passed': not errors, 'errors': errors})
    if pointers.get('clean_linux_reproduction'):
        path = ROOT / 'artifact/results' / pointers['clean_linux_reproduction']
        errors = check_hashes(path)
        summary = (path / 'summary.txt').read_text().splitlines()
        provenance = json.loads((path / 'provenance.json').read_text())
        if len(summary) != provenance['steps_passed'] or any(not s.startswith('PASS ') for s in summary) or provenance['container_exit_code'] != 0:
            errors.append('clean Linux reproduction status differs')
        results.append({'key': 'clean_linux_reproduction', 'passed': not errors, 'errors': errors})
    print(json.dumps(results, indent=2))
    return 0 if all(r['passed'] for r in results) else 1

if __name__ == '__main__':
    raise SystemExit(main())
