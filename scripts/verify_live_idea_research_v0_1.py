"""Explicit, bounded public-source canary. Never runs on import or without flag."""
import argparse
import json
import sys
import tempfile
import time
from pathlib import Path

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from x_factory import idea_intake_v0_1 as idea
from x_factory import idea_research_v0_1 as research

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--run-public-canary', action='store_true', required=True)
    parser.parse_args()
    folder = Path(tempfile.mkdtemp(prefix='live-research-', dir=ROOT / 'verification'))
    idea.IDEA_ROOT = folder / 'ideas'
    research.JOB_ROOT = folder / 'jobs'
    draft = idea.prepare_idea({'seed': 'An informational guide for visitors asking about the Python Software Foundation.',
                              'company_name': 'Python Software Foundation', 'website': 'https://www.python.org/psf/',
                              'purpose': 'Help visitors understand the Python Software Foundation using its public website and prepare questions for staff review. No donations, transactions, or outreach.'})
    job = research.start_research(draft)
    print(json.dumps({'job_id': job['job_id'], 'folder': str(folder)}), flush=True)
    deadline = time.monotonic() + 195
    while time.monotonic() < deadline:
        result = research.get_job(job['job_id'])
        if result['status'] in {'NEEDS_REVIEW', 'FAILED', 'CANCELLED'}:
            print(json.dumps({key: result.get(key) for key in ('status', 'message', 'usage', 'result_sha256')}), flush=True)
            if result.get('result'):
                print(json.dumps({'sources': [item['url'] for item in result['result']['sources']], 'identity_status': result['result']['identity_status'], 'summary': result['result']['summary']}), flush=True)
            raise SystemExit(0 if result['status'] == 'NEEDS_REVIEW' and result.get('result', {}).get('sources') else 1)
        time.sleep(.5)
    research.cancel_research(job['job_id'])
    raise SystemExit('Public canary timed out.')
