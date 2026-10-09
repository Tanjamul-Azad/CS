"""Generate current network tables directly from explicitly selected bundles."""
from __future__ import annotations
import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LABELS = {
    'io.opentweet/mcp': 'opentweet',
}

def load_rows(bundle):
    return [json.loads(line) for line in (bundle / 'results.jsonl').read_text(encoding='utf-8').splitlines()]

def tables(pointers):
    original = load_rows(ROOT / 'artifact/results' / pointers['network_matched'])
    additional = load_rows(ROOT / 'artifact/results' / pointers['additional_network_held_out'])
    sections = []
    for rows, additional_set in [(original, False), (additional, True)]:
        lines = [r'\begin{table}[h]', r'\centering\footnotesize',
            r'\caption{' + ('Additional held-out cohort. ' if additional_set else 'Original network cohort. ')
            + r'Slack bounds the canonical view. Fixed send variants exclude no-ops; adaptive variants mutate every JSON string leaf. Counts measure check-level refusal.}',
            r'\label{tab:' + ('netextra' if additional_set else 'netservers') + '}',
            r'\setlength{\tabcolsep}{3pt}', r'\begin{tabular}{@{}llrll@{}}', r'\toprule',
            r'Server & Set & Bits & Fixed & Adaptive \\', r'\midrule']
        for i, row in enumerate(rows):
            name = LABELS.get(row['name'], row['name'].split('/')[-1]).replace('_', r'\_')
            if additional_set:
                name = ['bighub', 'inter-bank', 'conekta', 'index365', 'opedd'][i]
            elif 'boostedchat' in row['name']:
                name = 'travel'
            split = 'Held' if additional_set or i >= 6 else 'Dev'
            if not row.get('qualified'):
                lines.append(name + ' & ' + split + r' & \multicolumn{3}{l}{no template} \\')
                continue
            fixed = [v for k, v in row['attacks'].items() if k != 'A8_silent_noop']
            n = sum(v['applicable'] for v in fixed)
            stopped = sum(v['effectseal_stops'] for v in fixed)
            a = row['adaptive']
            adaptive = f"{a['stopped']}/{a['applicable']}" if a['applicable'] else '--'
            lines.append(f"{name} & {split} & {row['slack_bits']:.1f} & {stopped}/{n} & {adaptive}" + r' \\')
        lines += [r'\bottomrule', r'\end{tabular}', r'\end{table}']
        sections.append('\n'.join(lines))
    return '\n\n'.join(sections) + '\n'

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--update-manuscript', action='store_true')
    args = parser.parse_args()
    pointers = json.loads((ROOT / 'artifact/paper-evidence-20261009.json').read_text(encoding='utf-8'))
    tex = tables(pointers)
    if args.update_manuscript:
        path = ROOT / 'paper/submission/sections/E-supplementary.tex'
        if not path.exists():
            raise SystemExit('Private manuscript is absent; obtain the source package first.')
        source = path.read_text(encoding='utf-8')
        begin, end = '% BEGIN GENERATED NETWORK TABLES', '% END GENERATED NETWORK TABLES'
        if begin not in source or end not in source:
            raise SystemExit('Missing manuscript table markers; refusing an ambiguous replacement.')
        source = re.sub(re.escape(begin) + r'.*?' + re.escape(end),
                        lambda _: begin + '\n' + tex + end, source, flags=re.S)
        path.write_text(source, encoding='utf-8')
        print('Updated', path)
    else:
        print(tex)
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
