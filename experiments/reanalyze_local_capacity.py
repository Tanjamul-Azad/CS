"""Recompute canonical-view capacity of archived local templates without rescoring them."""
import copy
import datetime as dt
import hashlib
import json
import math
import re
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from mcpgate.template_inference import EffectTemplate,ObjectTemplate


def restore(data):
    objects=[]
    for item in data['objects']:
        item=dict(item)
        for field in ['path','content']:
            if item.get(field) is not None:item[field]=tuple(tuple(t) for t in item[field])
        objects.append(ObjectTemplate(**item))
    return EffectTemplate(data['tool'],data['root'],tuple(objects),data.get('fixed',{}),data.get('training_runs',0))


def corrected(data):
    data=copy.deepcopy(data)
    for obj in data['objects']:
        for field in ['path','content']:
            for token in obj.get(field) or []:
                if token[0]!='H' or token[1].startswith('clock:'):continue
                match=re.fullmatch(r'\(\?:([^)]*)\)\{(\d+),(\d+)\}',token[1])
                if not match:continue
                cls,low,high=match.group(1),int(match.group(2)),int(match.group(3))
                if cls not in [r'[^\n]',r'[^/\n]',r'[\s\S]']:continue
                alphabet=0x110000-2048-(2 if cls==r'[^/\n]' else 1 if cls==r'[^\n]' else 0)
                token[2]=math.ceil((high*math.log2(alphabet)+math.log2(sum(alphabet**(-k) for k in range(min(high-low,60)+1))))*1000)/1000
    return data


def analyze():
    rows=[]
    for name in ['template_generalization_run5.json','template_generalization_sql_run3.json','batch2_templates.json']:
        p=ROOT/'artifact/results'/name; data=json.loads(p.read_text(encoding='utf-8'))
        for server in data['servers']:
            original=server.get('template')
            if not original:continue
            updated=corrected(original);before,after=restore(original),restore(updated)
            args=[h.get('args',{}) for h in server.get('honest',[]) if not h.get('call_error') and h.get('slack_bits') is not None]
            old=max((before.slack(a).total_bits for a in args),default=before.slack().total_bits)
            new=max((after.slack(a).total_bits for a in args),default=after.slack().total_bits)
            rows.append({'source':name,'source_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'server':server['server_id'],
                         'package':server.get('package'),'previous_canonical_slack_bits':old,
                         'corrected_canonical_slack_bits':new,'template':updated})
    return rows


def main():
    rows=analyze()
    out=ROOT/'artifact/results'/('local_capacity_reanalysis_'+dt.datetime.now().strftime('%Y%m%d-%H%M%S')+'.json')
    out.write_text(json.dumps({'scope':'Offline capacity correction of archived local templates, using each archived honest call arguments. No new local honest/adversarial scoring; excludes raw container metadata. Clock dates bound to trusted admission date.', 'rows':rows},indent=2))
    print([(r['package'],r['previous_canonical_slack_bits'],r['corrected_canonical_slack_bits']) for r in rows]);print('RESULT',out)
if __name__=='__main__':main()
