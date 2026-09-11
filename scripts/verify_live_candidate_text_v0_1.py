"""Explicit five-call live runtime regression on a wholly fictional test candidate.

No user/client knowledge is approved. All fixtures and simulated approvals live
inside verification; no user's mission, repo, profile or ANAM session is touched.
"""
import json
import sys
import time
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'scripts')]
from x_factory import prepared_agent_v0_1 as prep, idea_intake_v0_1 as ideas, idea_research_v0_1 as research
from x_factory import mission_control_factory_v0_1 as factory, knowledge_loading_v0_1 as loading
from x_factory.dojo_candidate_v0_1 import evaluate
from verify_prepared_agent_v0_1 import fixture_worker
from verify_idea_research_v0_1 import example_result
if '--run-synthetic-canary' not in sys.argv:
    raise SystemExit('Use --run-synthetic-canary explicitly. Five maximum Luna calls, no retries or ANAM.')
base=ROOT/'verification'/('candidate-text-live-'+time.strftime('%Y%m%d-%H%M%S'))
with ExitStack() as stack:
    for module,key,folder in [(prep,'PROJECT_ROOT','projects'),(ideas,'IDEA_ROOT','ideas'),(research,'JOB_ROOT','research'),
                               (factory,'INTERACTIVE_ROOT','missions'),(loading,'KNOWLEDGE_ROOT','knowledge')]:
        stack.enter_context(patch.object(module,key,base/folder))
    draft=ideas.prepare_idea({'seed':'A fictional moving assistant for isolated runtime verification only.', 'website':'https://example.com/','company_name':'Sample Moving Company'})
    project=prep.start_project(draft['idea_id'],worker=fixture_worker,research_worker=lambda *a,**k:example_result())
    while project['status'] in {'RESEARCHING','PREPARING'}:
        time.sleep(.05);project=prep.get_project(project['project_id'])
    assert project['status']=='NEEDS_REVIEW',project['message']
    project=prep.approve_project(project['project_id'],{'revision_sha256':project['revision_sha256'],'owner_approved':True})
    project=prep.build_project(project['project_id'],{'revision_sha256':project['revision_sha256'],'owner_requested':True})
    print('SYNTHETIC CANARY; five real runtime calls; '+str(base),flush=True)
    result=evaluate(project['project_id'])
    print(json.dumps(result,indent=2),flush=True)
    raise SystemExit(0 if result['decision']=='PASS_FOR_TESTED_LANE' else 1)
