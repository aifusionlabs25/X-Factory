"""Offline, versioned compilation repair of a preserved public canary response."""
import sys
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from x_factory import prepared_agent_v0_1 as p
base=ROOT/'verification/prepared-live-20260905-132548/projects'
project_id='project-380abd35843b19ecc0e4780a'
with patch.object(p,'PROJECT_ROOT',base):
    value=p.get_project(project_id)
    if value['status']!='NEEDS_ATTENTION':raise SystemExit('Recovery already handled or state changed')
    record=next((base/project_id/'troy').rglob('accepted.json'))
    saved=p.read(record)
    assert p.digest(saved['output'])==saved['receipt']['output_sha256']
    prompt=p.finalize_prompt(saved['output'],value['knowledge'])
    fields={**value['fields'],'personality':saved['output']['personality']}
    final=p.publish(project_id,fields=fields,system_prompt=prompt,prompt_notes=saved['output'],status='NEEDS_REVIEW',
        message='Prepared public canary recovered by a versioned deterministic binding-index repair. No model retry or approval.',
        stages=[*value['stages'],saved['receipt'],{'actor':'binding compiler','execution_mode':'DETERMINISTIC_COMPILE',
            'usage':{'model_calls':0,'tool_calls':0},'input_sha256':p.digest(saved['output']),'output_sha256':p.sha256(prompt.encode())}])
    print('REVIEWABLE: '+str(base/project_id)+' revision '+str(final['revision']))
