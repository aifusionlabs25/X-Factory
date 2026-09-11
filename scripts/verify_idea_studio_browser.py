"""Exercise the real local HTTP/UI flow with isolated drafts and synthetic sources."""
import os
import subprocess
import sys
import tempfile
import threading
from contextlib import ExitStack
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'scripts'))
import mission_control_server as server
from x_factory import idea_intake_v0_1 as idea
from x_factory import knowledge_loading_v0_1 as loading
from x_factory import idea_research_v0_1 as research
from x_factory.website_ingestion_v0_1 import capture_website_knowledge


def fixture_capture(payload):
    def fetch(url):
        if not url.startswith('https://example.com/'):
            raise AssertionError('Unexpected fixture URL')
        return 200, {'content-type': 'text/html'}, b'''<html><head><title>Studio Test Services</title></head>
        <body><main><h1>Our services</h1><p>We repair water heaters and air conditioning systems.</p>
        <h2>Service area</h2><p>We serve customers in Fictional City.</p>
        <h2>Pricing policy</h2><p>Final pricing requires staff review.</p></main></body></html>'''
    return capture_website_knowledge(payload, resolver=lambda *a, **k: [(2, 1, 6, '', ('93.184.216.34', 443))], fetcher=fetch)


RESEARCH_CALLS = []


def fixture_research(prompt, *, work_dir, limits, cancel_event):
    """Exercise real persistence/validation, never import the provider runner."""
    RESEARCH_CALLS.append(prompt)
    if cancel_event.wait(0.4):
        raise RuntimeError('Synthetic research was cancelled')
    now = datetime.now(timezone.utc)
    statement = 'We repair water heaters and air conditioning systems.'
    text = 'Studio Test Services. ' + statement
    return {
        'research': {
            'identity_status': 'RESOLVED',
            'company_candidates': [{'name': 'Studio Test Services', 'website': 'https://example.com/', 'source_ids': ['S1']}],
            'sources': [{'source_id': 'S1', 'url': 'https://example.com/', 'title': 'Studio Test Services',
                         'observed_on': now.date().isoformat(), 'excerpt': text}],
            'findings': [{'finding_id': 'F1', 'statement': statement, 'source_ids': ['S1']}],
            'uncertainties': ['Confirm coverage and pricing with the owner before approving company facts.'],
            'proposed_purpose': 'Help homeowners ask approved questions and prepare home-service requests for a structured staff handoff. Do not confirm bookings or invent prices.',
            'role_requirements': [{'description': 'Keep service requests separate from general questions.', 'basis': 'OWNER_INTENT', 'source_ids': []},
                                  {'description': 'Prepare a reviewed water-heater service topic.', 'basis': 'SOURCE_EVIDENCE', 'source_ids': ['S1']}],
            'summary': 'A home-service intake assistant is proposed; company facts still require separate owner review.',
        },
        'source_evidence': [{'url': 'https://example.com/', 'title': 'Studio Test Services',
                             'retrieved_at': now.isoformat(), 'text': text, 'access_status': 'FETCHED'}],
        'usage': {'model_calls': 0, 'tool_calls': 0},
    }


def forbid_build(*args, **kwargs):
    raise AssertionError('The browser regression may not execute a Factory build')


if __name__ == '__main__':
    if os.environ.get('STUDIO_LEGACY_FLOW') != '1':
        # The supported owner journey now requires populated unapproved drafts.
        # Retain the old direction-only test solely as an explicit legacy check.
        raise SystemExit(subprocess.call([sys.executable,'-B',str(ROOT/'scripts/verify_prepared_agent_browser.py')]))
    with tempfile.TemporaryDirectory(prefix='factory-studio-qa-') as temp:
        temp = Path(temp)
        with ExitStack() as patches:
            for module, attribute, value in (
                (idea, 'IDEA_ROOT', temp / 'ideas'),
                (loading, 'KNOWLEDGE_ROOT', temp / 'knowledge'),
                (research, 'JOB_ROOT', temp / 'research'),
                (research, '_default_worker', fixture_research),
                (idea, 'capture_website_knowledge', fixture_capture),
                (server, 'capture_website_knowledge', fixture_capture),
                (server, 'commission_chassis', forbid_build),
            ):
                patches.enter_context(patch.object(module, attribute, value))
            httpd = server.ThreadingHTTPServer(('127.0.0.1', 0), server.MissionControlHandler)
            thread = threading.Thread(target=httpd.serve_forever, daemon=True)
            thread.start()
            env = dict(os.environ, STUDIO_TEST_URL=f'http://127.0.0.1:{httpd.server_port}', STUDIO_TEST_ISOLATED='1')
            try:
                result = subprocess.run([os.environ.get('STUDIO_TEST_NODE', 'node'), str(ROOT / 'scripts/verify_idea_studio_browser.cjs')], cwd=ROOT, env=env)
                if result.returncode == 0 and not os.environ.get('STUDIO_INSPECT_ONLY'):
                    assert len(RESEARCH_CALLS) == 1, 'Exactly one fake R&D job should run; no automatic research/retries'
            finally:
                httpd.shutdown()
                httpd.server_close()
                thread.join(timeout=5)
            raise SystemExit(result.returncode)
