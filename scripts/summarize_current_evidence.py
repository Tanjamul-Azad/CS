"""Generate network summary and per-server tables from selected raw bundles."""
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
        lines = [r'\begin{table}[H]', r'\centering\footnotesize',
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


def summary_table(pointers):
    original = load_rows(ROOT / 'artifact/results' / pointers['network_matched'])
    additional = load_rows(ROOT / 'artifact/results' / pointers['additional_network_held_out'])
    cohorts = [
        ('Original: development', original[:6]),
        ('Original: held-out', original[6:]),
        ('Original: total', original),
        (r'Additional: held-out$^*$', additional),
    ]
    lines = [
        r'\begin{table*}[t]', r'\centering\small',
        r'\caption{Network admission across cohorts. Templates reports coverage; other counts are conditional on coverage. Fixed and adaptive counts report check-level refusal, excluding no-ops. Original total includes the two preceding rows. $^*$The additional cohort contains five qualifiers from 40 screened candidates; the target was six. These are mock-API protocol outcomes, not verified vendor task completion.}',
        r'\label{tab:network-summary}',
        r'\begin{tabular*}{\textwidth}{@{\extracolsep{\fill}}lrrrr@{}}',
        r'\toprule',
        r'Cohort & Templates & Honest admitted & Fixed refused & Adaptive refused \\',
        r'\midrule',
    ]
    for name, rows in cohorts:
        covered = [row for row in rows if row.get('qualified')]
        honest_n = sum(row['honest']['calls'] for row in covered)
        honest_admitted = sum(row['honest']['calls'] - row['honest']['blocked'] for row in covered)
        fixed = [variant for row in covered for key, variant in row['attacks'].items()
                 if key != 'A8_silent_noop']
        fixed_n = sum(variant['applicable'] for variant in fixed)
        fixed_stopped = sum(variant['effectseal_stops'] for variant in fixed)
        adaptive_n = sum(row['adaptive']['applicable'] for row in covered)
        adaptive_stopped = sum(row['adaptive']['stopped'] for row in covered)

        def count_rate(numerator, denominator):
            if not denominator:
                return '--'
            percent = f'{100 * numerator / denominator:.1f}'.removesuffix('.0')
            return f'{numerator}/{denominator} ({percent}' + r'\%)'

        cells = [name, count_rate(len(covered), len(rows)),
                 f'{honest_admitted}/{honest_n}', count_rate(fixed_stopped, fixed_n),
                 count_rate(adaptive_stopped, adaptive_n)]
        if name == 'Original: total':
            lines.append(r'\midrule')
        lines.append(' & '.join(cells) + r' \\')
        if name == 'Original: total':
            lines.append(r'\midrule')
    lines += [r'\bottomrule', r'\end{tabular*}', r'\end{table*}']
    return '\n'.join(lines) + '\n'


def replace_marked_table(path, name, tex):
    source = path.read_text(encoding='utf-8')
    begin, end = f'% BEGIN GENERATED NETWORK {name}', f'% END GENERATED NETWORK {name}'
    if source.count(begin) != 1 or source.count(end) != 1:
        raise SystemExit('Missing or duplicate manuscript table markers: ' + str(path))
    source = re.sub(re.escape(begin) + r'.*?' + re.escape(end),
                    lambda _: begin + '\n' + tex + end, source, flags=re.S)
    path.write_text(source, encoding='utf-8')
    print('Updated', path)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--update-manuscript', action='store_true')
    parser.add_argument('--summary', action='store_true', help='print the main-paper cohort summary')
    args = parser.parse_args()
    pointers = json.loads((ROOT / 'artifact/paper-evidence-20261009.json').read_text(encoding='utf-8'))
    tex = tables(pointers)
    if args.update_manuscript:
        path = ROOT / 'paper/submission/sections/E-supplementary.tex'
        if not path.exists():
            raise SystemExit('Private manuscript is absent; obtain the source package first.')
        replace_marked_table(path, 'TABLES', tex)
        replace_marked_table(ROOT / 'paper/submission/sections/07-results.tex',
                             'SUMMARY', summary_table(pointers))
    else:
        print(summary_table(pointers) if args.summary else tex)
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
