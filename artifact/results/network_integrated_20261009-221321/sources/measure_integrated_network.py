"""Integrated HTTP proxy timings and durable allowance races, with raw samples."""
import argparse
import concurrent.futures
import datetime as dt
import hashlib
import http.client
import json
import os
import sys
import tempfile
import threading
import time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'src'), str(ROOT/'experiments')]
from mcpgate.egress_proxy import EgressProxy, RunCA
from mcpgate.egress_service import ControlledDecision
from mcpgate.request_templates import CapturedRequest, RequestObservation, infer_request_template
from measure_network_overhead import percentiles


def main():
    parser=argparse.ArgumentParser(); parser.add_argument('--iters',type=int,default=300); parser.add_argument('--trials',type=int,default=100)
    args=parser.parse_args(); stamp=dt.datetime.now().strftime('%Y%m%d-%H%M%S')
    out=ROOT/'artifact/results'/('network_integrated_'+stamp); out.mkdir()
    request=CapturedRequest('POST','https://api.test/send',{'Content-Type':'application/json'},b'{"text":"approved body"}')
    template=infer_request_template('send',[RequestObservation({},(request,))]*2)
    with tempfile.TemporaryDirectory(prefix='es-integrated-',ignore_cleanup_errors=True) as work:
        control=Path(work)/'control'; control.mkdir()
        def state(mode,cid):
            tmp=control/'state.tmp'; tmp.write_text(json.dumps({'mode':mode,'call_id':cid,'template':template.to_json(),'arguments':{}}))
            os.replace(tmp,control/'state.json')
        state('deny','')
        decisions=[ControlledDecision(control),ControlledDecision(control)]
        seen=[]; lock=threading.Lock()
        def upstream(*a):
            with lock:seen.append({'body':a[-1].decode(),'url':a[1]+a[4]})
            return 200,[],b'OK'
        ca=RunCA(Path(work)/'ca')
        def send(proxy):
            start=time.perf_counter_ns(); conn=http.client.HTTPConnection(*proxy.address,timeout=15)
            conn.request(request.method,request.url,request.body,dict(request.headers)); response=conn.getresponse()
            response.read(); status=response.status; conn.close()
            return status,time.perf_counter_ns()-start
        with EgressProxy(ca,decisions[0],upstream=upstream) as p1, EgressProxy(ca,decisions[1],upstream=upstream) as p2:
            samples={'gate':[],'record_proxy_baseline':[]}; rows=[]
            for i in range(args.iters):
                for label,mode in [('record_proxy_baseline','record'),('gate','gate')]:
                    state(mode,f'timing-{label}-{i}'); status,elapsed=send(p1)
                    if status!=200:raise RuntimeError('honest integrated request refused')
                    samples[label].append(elapsed)
            with concurrent.futures.ThreadPoolExecutor(8) as pool:
                for i in range(args.trials):
                    state('gate',f'race-{i}'); before=len(seen); barrier=threading.Barrier(8)
                    def contender(j):
                        barrier.wait(timeout=10); return send([p1,p2][j%2])[0]
                    statuses=list(pool.map(contender,range(8)))
                    rows.append({'trial':i,'statuses':statuses,'effects':len(seen)-before})
            state('gate','restart-test'); assert send(p1)[0]==200
            restart=ControlledDecision(control)
            with EgressProxy(ca,restart,upstream=upstream) as restarted:
                replay_status=send(restarted)[0]
        result={'schema_version':2,'iters':args.iters,'trials':args.trials,'samples_ns':samples,'races':rows,
                'timings':{k:percentiles(v) for k,v in samples.items()},'restart_replay_status':replay_status,
                'all_pass':all(r['effects']==1 and r['statuses'].count(200)==1 and r['statuses'].count(403)==7 for r in rows) and replay_status==403,
                'scope':'actual ControlledDecision and EgressProxy over loopback HTTP, mock upstream; includes state read, instantiation, durable reservation/terminal commit, logs and local HTTP; excludes TLS and WAN/vendor latency',
                'created_utc':dt.datetime.now(dt.timezone.utc).isoformat()}
        (out/'result.json').write_text(json.dumps(result,indent=2))
        (out/'broker').mkdir()
        import shutil
        for p in control.iterdir():
            if p.is_file():shutil.copy2(p,out/'broker'/p.name)
    (out/'sources').mkdir()
    for p in [Path(__file__),*sorted((ROOT/'src/mcpgate').glob('*.py'))]:
        import shutil; shutil.copy2(p,out/'sources'/p.name)
    (out/'SHA256SUMS.json').write_text(json.dumps({str(p.relative_to(out)).replace('\\','/'):hashlib.sha256(p.read_bytes()).hexdigest()
                                                 for p in out.rglob('*') if p.is_file()},indent=2))
    print(json.dumps({k:result[k] for k in ['timings','all_pass','restart_replay_status']},indent=2)); print('BUNDLE',out)
    return 0 if result['all_pass'] else 1
if __name__=='__main__':raise SystemExit(main())
