"""Real HTTP/browser/build flow with synthetic sources, no provider or user-state writes."""
import os
import subprocess
import sys
import tempfile
import threading
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'scripts')]
import mission_control_server as server
from x_factory import prepared_agent_v0_1 as prep, idea_intake_v0_1 as idea, idea_research_v0_1 as research
from x_factory import knowledge_loading_v0_1 as loading, mission_control_factory_v0_1 as factory
from x_factory import hermes_idea_research_v0_1 as transport
from x_factory import candidate_text_runtime_v0_1 as runtime
from verify_idea_research_v0_1 import example_result
from verify_prepared_agent_v0_1 import fixture_worker

def runtime_fixture(system,prompt,**kwargs):
    return {'output':{'reply':'The reviewed information lists packing and local moving services.',
        'supporting_entry_ids':['K-0001'],'handoff':{'request_summary':None,'facts':[],'unknowns':[],'corrections':[]}},
        'execution_mode':'HERMES_INFERENCE','usage':{'model_calls':1,'tool_calls':0}}

with tempfile.TemporaryDirectory(prefix='factory-prepared-browser-') as temporary, ExitStack() as stack:
    base=Path(temporary)
    for module,key,value in [(prep,'PROJECT_ROOT',base/'projects'),(idea,'IDEA_ROOT',base/'ideas'),
            (research,'JOB_ROOT',base/'research'),(loading,'KNOWLEDGE_ROOT',base/'knowledge'),
            (factory,'INTERACTIVE_ROOT',base/'missions'),(server,'INTERACTIVE_ROOT',base/'missions'),(research,'_default_worker',lambda *a,**k:example_result()),
            (transport,'run_specialist',fixture_worker),(runtime,'run_model',runtime_fixture)]:
        stack.enter_context(patch.object(module,key,value))
    httpd=server.ThreadingHTTPServer(('127.0.0.1',0),server.MissionControlHandler)
    thread=threading.Thread(target=httpd.serve_forever,daemon=True);thread.start()
    try:
        result=subprocess.run([os.environ.get('STUDIO_TEST_NODE','node'),str(ROOT/'scripts/verify_prepared_agent_browser.cjs')],cwd=ROOT,
            env=dict(os.environ,STUDIO_TEST_URL=f'http://127.0.0.1:{httpd.server_port}',STUDIO_TEST_ISOLATED='1'))
    finally:
        httpd.shutdown();httpd.server_close();thread.join(5)
    raise SystemExit(result.returncode)
