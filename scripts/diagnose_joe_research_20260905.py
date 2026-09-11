"""One explicitly invoked public-company diagnostic; no approval or build."""
import json,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from x_factory import idea_research_v0_1 as research, idea_intake_v0_1 as ideas
if '--run' not in sys.argv:raise SystemExit('Requires --run; maximum eight research calls, no retries, specialist calls, approval or build.')
base=ROOT/'verification'/('joe-research-diagnostic-'+time.strftime('%Y%m%d-%H%M%S'))
ideas.IDEA_ROOT=base/'ideas';research.JOB_ROOT=base/'research'
draft=ideas.prepare_idea({'seed':'A public-company intake guide for Joe Rushing Plumbing, Heating & Air Conditioning.',
    'company_name':'Joe Rushing Plumbing, Heating & Air Conditioning','website':'https://joerushing.com/',
    'purpose':'Prepare a sourced home-service intake guide and human handoff. No diagnosis, dispatch, quotes or external actions.'})
job=research.start_research(draft);print(str(base),flush=True)
while job['status'] in {'QUEUED','RUNNING'}:
    time.sleep(.5);job=research.get_job(job['job_id'])
print(json.dumps({k:job.get(k) for k in ('status','message','usage','result_sha256')}),flush=True)
raise SystemExit(0 if job['status']=='NEEDS_REVIEW' else 1)
