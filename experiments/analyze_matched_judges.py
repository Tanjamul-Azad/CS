"""Descriptive judge reweighting, matching server, approved request and normalized signature."""
import datetime as dt
import hashlib
import json
import sys
from collections import defaultdict
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'src'),str(ROOT/'experiments')]
from analyze_judge_leaks import signature


def main():
    paths=[ROOT/'artifact/results'/n for n in ['llm_judge_transcripts_v2.json','llm_judge_v2.json','llm_judge_ollama_v2.json']]
    rows=json.loads(paths[0].read_text())['rows'];by_key={(r['server_id'],r['scenario'],r['tier'],r['rep']):r for r in rows}
    def key(r):return (r['server_id'],r['scenario'],r['tier'],r['rep'])
    def match_signature(r):return (r['server_id'],json.dumps(r['request'],sort_keys=True),signature(r))
    honest=defaultdict(list)
    for r in rows:
        if r['scenario']=='H0':honest[match_signature(r)].append(key(r))
    result=[]
    verdicts=[v for p in paths[1:] for v in json.loads(p.read_text())['verdicts']]
    for model in sorted({v['model'] for v in verdicts}):
        values={key(v):int(v['verdict']=='UNSAFE') for v in verdicts if v['model']==model}
        pairs=[]
        for r in rows:
            if r['scenario']=='H0' or r['tier']!='consistent' or not r['landed'] or key(r) not in values:continue
            matches=[k for k in honest[match_signature(r)] if k in values]
            if matches:
                pairs.append({'attack_key':key(r),'honest_keys':matches,'attack_flag':values[key(r)],
                              'honest_mean_flag':sum(values[k] for k in matches)/len(matches)})
        result.append({'model':model,'matched_attacks':len(pairs),'attacks_flagged':sum(p['attack_flag'] for p in pairs),
                       'matched_honest_flag_rate':sum(p['honest_mean_flag'] for p in pairs)/len(pairs) if pairs else None,
                       'attack_flag_rate':sum(p['attack_flag'] for p in pairs)/len(pairs) if pairs else None,'pairs':pairs})
    out=ROOT/'artifact/results'/('judge_matched_sensitivity_'+dt.datetime.now().strftime('%Y%m%d-%H%M%S')+'.json')
    data={'created_utc':dt.datetime.now(dt.timezone.utc).isoformat(),'scope':'Post hoc descriptive sensitivity only. Matches same server, identical approved request, and judge-free normalized responses/readbacks. Does not establish equality of raw transcripts or an independent inferential test.',
          'source_hashes':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},'models':result}
    out.write_text(json.dumps(data,indent=2));print(json.dumps([{k:v for k,v in r.items() if k!='pairs'} for r in result],indent=2));print('RESULT',out)
if __name__=='__main__':main()
