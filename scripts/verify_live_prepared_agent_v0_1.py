"""Explicit public-only canary: research + three draft calls, no approval/build."""
import json
import sys
import time
from pathlib import Path
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from x_factory import prepared_agent_v0_1 as prep, idea_intake_v0_1 as ideas, idea_research_v0_1 as research

if '--run-public-canary' not in sys.argv:
    raise SystemExit('Use --run-public-canary explicitly. Maximum 8 research + 3 drafting calls; no retry, approval or build.')
base=ROOT/'verification'/('prepared-live-'+time.strftime('%Y%m%d-%H%M%S'))
with patch.object(prep,'PROJECT_ROOT',base/'projects'), patch.object(ideas,'IDEA_ROOT',base/'ideas'), patch.object(research,'JOB_ROOT',base/'research'):
    draft=ideas.prepare_idea({'seed':'An information guide for the Python Software Foundation: explain its mission and public participation options, identify the right public resource, and prepare unanswered questions for human review. No donations, memberships or messages may be submitted.',
                              'company_name':'Python Software Foundation','website':'https://www.python.org/psf/'})
    value=prep.start_project(draft['idea_id'])
    print('PUBLIC CANARY '+value['project_id'],flush=True)
    last=None
    while value['status'] in {'RESEARCHING','PREPARING'}:
        if value['message'] != last:
            print(value['message'],flush=True);last=value['message']
        time.sleep(1)
        value=prep.get_project(value['project_id'])
    print(json.dumps({'status':value['status'],'message':value['message'],'entries':len(value['knowledge']),
                     'prompt_characters':len(value['system_prompt']),'stages':value['stages'],'root':str(base)},indent=2),flush=True)
    raise SystemExit(0 if value['status']=='NEEDS_REVIEW' else 1)
