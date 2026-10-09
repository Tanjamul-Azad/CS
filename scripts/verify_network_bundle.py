"""Offline re-inference, request replay and aggregate verification of v2 bundles."""
import argparse
import datetime as dt
import hashlib
import json
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'src'), str(ROOT / 'experiments')]
import network_matched_eval as E
from mcpgate.request_templates import RequestObservation, infer_request_template

def verify(path):
    errors = []
    hashes = json.loads((path / 'SHA256SUMS.json').read_text(encoding='utf-8'))
    for name, digest in hashes.items():
        target = (path / name).resolve()
        if not target.is_relative_to(path.resolve()):
            errors.append('unsafe manifest path'); continue
        if not target.is_file() or hashlib.sha256(target.read_bytes()).hexdigest() != digest:
            errors.append('hash mismatch: ' + name)
    if (path / 'trials.jsonl').exists():
        import network_postmark_pilot as P
        meta = json.loads((path / 'meta.json').read_text(encoding='utf-8'))
        trials = [json.loads(line) for line in (path / 'trials.jsonl').read_text(encoding='utf-8').splitlines()]
        pins = [t for t in trials if t['phase'] == 'pin']
        for phase, tool in [('startup', '__startup__'), ('call', 'sendEmail')]:
            template = infer_request_template(tool, [RequestObservation({} if phase == 'startup' else p['args'],
                P.observation(p, phase), dt.datetime.fromisoformat(p['started'])) for p in pins],
                credential_headers=frozenset({P.TOKEN_HEADER.lower()}))
            if template.to_json() != meta['templates'][phase]:errors.append('Postmark template differs: ' + phase)
        for t in trials:
            if P.oracle(t) != t['oracle'] or P.gate_outcome(t) != t['gate_outcome']:
                errors.append('Postmark oracle differs: ' + t['call_id'])
        if P.summarize(trials) != json.loads((path / 'summary.json').read_text(encoding='utf-8')):
            errors.append('Postmark summary differs')
        return {'bundle': str(path), 'trials_checked': len(trials), 'hashes_checked': len(hashes), 'errors': errors, 'passed': not errors}
    rows = [json.loads(line) for line in (path / 'results.jsonl').read_text(encoding='utf-8').splitlines()]
    checked = 0
    for row in rows:
        if not row.get('qualified'):
            continue
        evidence = row['evidence']
        pins = [p for p in evidence['pins'] if p['call_id'] in evidence['inference_pin_ids']]
        fixed = {k: row['entry']['args'][k] for k in row['fixed_fields']}
        template = infer_request_template(row['tool'], [RequestObservation(p['args'],
            tuple(E.captured(r) for r in p['requests']), dt.datetime.fromisoformat(p['started'])) for p in pins], fixed=fixed)
        if template.to_json() != evidence['template']:
            errors.append(row['name'] + ': re-inferred template differs')
        if round(template.slack(), 3) != row['slack_bits']:
            errors.append(row['name'] + ': slack differs')
        for case in evidence['cases']:
            variant = [E.captured(r) for r in case['variant']]
            actual = E.sequence_verdict(template, case['args'], variant, dt.datetime.fromisoformat(case['now']))
            if actual != case['verdict'] or E.destination_stops(row['approved_host'], variant) != case['destination_stops']:
                errors.append(row['name'] + ': request replay differs')
            checked += 1
        for attack, saved in row['attacks'].items():
            cases = [c for c in evidence['cases'] if c['family'] == 'fixed' and c['attack'] == attack]
            expected = {'applicable': len(cases), 'effectseal_stops': sum(c['verdict']['outcome'] != 'ADMITTED' for c in cases),
                        'destination_stops': sum(c['destination_stops'] for c in cases)}
            if expected != saved:
                errors.append(row['name'] + ': aggregate attack count differs')
        completed, blocked = 0, 0
        honest = evidence['honest']
        for trial in honest:
            admitted = bool(trial['requests']) and all(r['admitted'] for r in trial['requests'])
            sent = [r for r in trial['far_side'] if r['call_id'].endswith('/call')]
            completed += admitted and not trial['error'] and len(sent) >= 1
            blocked += not admitted
        if {'calls': len(honest), 'completed': completed, 'blocked': blocked} != row['honest']:
            errors.append(row['name'] + ': honest outcome count differs')
    if E.summarize(rows) != json.loads((path / 'summary.json').read_text(encoding='utf-8')):
        errors.append('summary differs from recorded rows')
    return {'bundle': str(path), 'servers': len(rows), 'cases_replayed': checked,
            'hashes_checked': len(hashes), 'errors': errors, 'passed': not errors}

if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('bundle', type=Path)
    args = parser.parse_args(); result = verify(args.bundle)
    print(json.dumps(result, indent=2)); raise SystemExit(0 if result['passed'] else 1)
