"""Provider-free import tests; all review writes are isolated synthetic fixtures."""
import argparse
import hashlib
import importlib.util
import json
import sys
import tempfile
import threading
import unittest
from contextlib import ExitStack
from copy import deepcopy
from datetime import date, timedelta
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.dont_write_bytecode = True
from x_factory import hunter_draft_v0_1 as bridge

spec = importlib.util.spec_from_file_location('factory_server', ROOT / 'scripts/mission_control_server.py')
server_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(server_module)


def fixture():
    run = bridge.source_run()
    p = deepcopy(run['qualified_prospects'][1])
    p['prospect_id'] = 'synthetic-hunter-fixture'
    p['company_name'] = 'Synthetic Hunter Fixture — NOT A REAL PROSPECT'
    p['website'] = 'https://example.com/'
    p['location'] = 'Fictional test location'
    p['why_hunter_selected'] = 'Synthetic fixture for local form testing; no prospect was researched or qualified.'
    p['score_rationale'] = 'Fixture arithmetic only, not a commercial ranking.'
    p['factory_intake_brief']['anything_else_about_company'] = 'UNAPPROVED_RESEARCH_SENTINEL: never place this in client_context or Knowledge Bank.'
    p['factory_intake_brief']['system_prompt_brief'] = ('Provide a fictional local service concierge for this synthetic test. Answer only approved questions, collect a request, clarify missing details, and prepare a staff review summary. Do not invent company facts, promise availability, dispatch, book or send anything. ')
    for i, s in enumerate(p['public_sources']):
        s['observed_on'] = date.today().isoformat()
        s['url'] = f'https://example.com/fixture-{i}'
        s['title'] = f'Synthetic source {i}'
        s['claim'] = 'Synthetic test evidence, not an observation about a real business.'
    p['browser_audit']['checked_on'] = date.today().isoformat()
    p['factory_intake_brief']['website_sources_for_factory_review'] = [s['url'] for s in p['public_sources']]
    run['qualified_prospects'] = [p]
    run['metrics']['qualified_prospects'] = 1
    return run


class DraftTests(unittest.TestCase):
    def setUp(self):
        self.run = fixture()
        self.temp = tempfile.TemporaryDirectory(prefix='hunter-draft-test-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / 'synthetic.json'
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(patch.object(bridge, 'SOURCE_PATH', self.source))
        self.stack.enter_context(patch.object(bridge, 'REVIEW_ROOT', self.root / 'reviews'))
        self.save_source()

    def save_source(self):
        self.source.write_text(json.dumps(self.run), encoding='utf-8')
        self.stack.enter_context(patch.object(bridge, 'SOURCE_SHA256', hashlib.sha256(self.source.read_bytes()).hexdigest()))

    def request(self):
        r = bridge.review_prospect({'source_id': bridge.SOURCE_ID, 'prospect_id': 'synthetic-hunter-fixture'})
        fields = {**r['fields'], 'x_agent_name': 'Test Ava', 'presence_mode': 'TEXT_ONLY'}
        return {'source_id': bridge.SOURCE_ID, 'prospect_id': 'synthetic-hunter-fixture',
                'snapshot_sha256': r['snapshot_sha256'], 'chassis_sha256': r['chassis']['chassis_sha256'],
                'fields': fields, 'owner_confirmed': True}

    def test_read_only_review_keeps_research_separate(self):
        r = bridge.review_prospect({'source_id': bridge.SOURCE_ID, 'prospect_id': 'synthetic-hunter-fixture'})
        self.assertFalse((self.root / 'reviews').exists())
        self.assertEqual(r['fields']['x_agent_name'], '')
        self.assertEqual(r['fields']['presence_mode'], '')
        self.assertNotIn('client_context', r['fields'])
        self.assertNotIn('UNAPPROVED_RESEARCH_SENTINEL', json.dumps(r['fields']))
        self.assertNotIn('knowledge_package_id', r['fields'])

    def test_accept_saves_only_review_and_blocks_duplicate(self):
        req = self.request()
        result = bridge.accept_draft(req)
        self.assertFalse(result['mission_created'])
        self.assertFalse(result['knowledge_approved'])
        self.assertEqual(result['provider_calls'], 0)
        record = json.loads(next((self.root / 'reviews').glob('*.json')).read_text(encoding='utf-8'))
        self.assertEqual(record['snapshot']['research_status'], 'UNAPPROVED_RESEARCH')
        self.assertIn('x_agent_name', record['owner_edits'])
        with self.assertRaisesRegex(bridge.HunterDraftError, 'already has'):
            bridge.accept_draft(req)
        self.assertEqual(len(list((self.root / 'reviews').glob('*'))), 1)
        saved = bridge.reopen_draft({key: req[key] for key in ('source_id', 'prospect_id')})
        self.assertEqual(saved['fields'], result['fields'])
        self.assertEqual(len(list((self.root / 'reviews').glob('*'))), 1)
        target = next((self.root / 'reviews').glob('*.json'))
        tampered = json.loads(target.read_text(encoding='utf-8')); tampered['fields']['purpose'] = 'Changed after the review'
        target.write_text(json.dumps(tampered), encoding='utf-8')
        with self.assertRaisesRegex(bridge.HunterDraftError, 'changed'):
            bridge.reopen_draft({key: req[key] for key in ('source_id', 'prospect_id')})

    def test_rejects_authority_context_and_knowledge_injection(self):
        for field in ['client_context', 'knowledge_package_id', 'optional_module_ids', 'approved', 'mission_id']:
            req = self.request(); req['fields'][field] = 'injected'
            with self.assertRaises(bridge.HunterDraftError): bridge.accept_draft(req)
        req = self.request(); req['owner_confirmed'] = False
        with self.assertRaises(bridge.HunterDraftError): bridge.accept_draft(req)

    def test_rejects_bad_inputs_without_writing(self):
        for field, value in [('purpose', 'x' * 2001), ('client_name', ' ' * 5), ('x_agent_name', ''), ('presence_mode', 'AUTO'), ('additional_requirements', 'x' * 3000), ('additional_boundaries', 'No limits')]:
            req = self.request(); req['fields'][field] = value
            with self.assertRaises(bridge.HunterDraftError): bridge.accept_draft(req)
        self.assertFalse((self.root / 'reviews').exists())

    def test_drift_rejected(self):
        req = self.request(); req['snapshot_sha256'] = '0' * 64
        with self.assertRaisesRegex(bridge.HunterDraftError, 'changed during'): bridge.accept_draft(req)
        req = self.request(); req['chassis_sha256'] = '0' * 64
        with self.assertRaisesRegex(bridge.HunterDraftError, 'changed during'): bridge.accept_draft(req)
        self.source.write_text('{}')
        with self.assertRaisesRegex(bridge.HunterDraftError, 'source has changed'): bridge.list_prospects()

    def test_hold_and_stale_cannot_apply(self):
        p = self.run['qualified_prospects'][0]
        with patch.object(bridge, 'BLOCKED', {p['prospect_id']: 'HOLD / BLOCKED_SOURCE'}):
            with self.assertRaisesRegex(bridge.HunterDraftError, 'HOLD'): bridge.accept_draft(self.request())
        p['public_sources'][0]['observed_on'] = (date.today() - timedelta(days=8)).isoformat()
        self.save_source()
        with self.assertRaisesRegex(bridge.HunterDraftError, 'seven-day'): bridge.accept_draft(self.request())

    def test_scoring_evidence_and_version_rejected(self):
        original = deepcopy(self.run)
        for change in ['score', 'evidence', 'version', 'extra_brief']:
            self.run = deepcopy(original)
            p = self.run['qualified_prospects'][0]
            if change == 'score': p['overall_score'] = 100
            if change == 'evidence': p['public_sources'] = []
            if change == 'version': self.run['schema_version'] = 'hunter.run.v0.1'
            if change == 'extra_brief': p['factory_intake_brief']['execute'] = 'build'
            self.save_source()
            with self.assertRaises(bridge.HunterDraftError): bridge.list_prospects()

    def test_arbitrary_paths_urls_and_multiple_prospects_rejected(self):
        for req in [{'source_id': 'https://example.com', 'prospect_id': 'synthetic-hunter-fixture'},
                    {'source_id': bridge.SOURCE_ID, 'prospect_id': '../auth.json'},
                    {'source_id': bridge.SOURCE_ID, 'prospect_id': ['one', 'two']},
                    {'source_id': bridge.SOURCE_ID, 'prospect_id': 'synthetic-hunter-fixture', 'path': 'C:/secret'}]:
            with self.assertRaises(bridge.HunterDraftError): bridge.review_prospect(req)

    def test_http_route_has_no_execution_side_effects(self):
        server = ThreadingHTTPServer(('127.0.0.1', 0), server_module.MissionControlHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
        try:
            with ExitStack() as guards:
                for name in ['create_mission', 'commission_chassis', 'approve_knowledge_package', 'capture_website_knowledge', 'complete_local_draft', 'create_local_repo', 'request_governed_run', 'request_repo_promotion']:
                    guards.enter_context(patch.object(server_module, name, side_effect=AssertionError('Execution forbidden during import')))
                req = self.request()
                url = f'http://127.0.0.1:{server.server_port}/api/hunter/accept-draft'
                bad = Request(url, json.dumps(req).encode(), {'Content-Type': 'application/json', 'Origin': 'https://untrusted.example'})
                with self.assertRaises(HTTPError) as caught: urlopen(bad)
                self.assertEqual(caught.exception.code, 403)
                good = Request(url, json.dumps(req).encode(), {'Content-Type': 'application/json'})
                with urlopen(good) as response: self.assertEqual(json.load(response)['status'], 'OWNER_REVIEWED_DRAFT_ONLY')
        finally:
            server.shutdown(); server.server_close(); thread.join()


def serve_fixture(port):
    case = DraftTests(); case.setUp()
    # Visible synthetic fixture only; no real prospect can be accepted here.
    class FixtureHandler(server_module.MissionControlHandler):
        def do_POST(self):
            if self.path not in {'/api/hunter/review', '/api/hunter/accept-draft', '/api/hunter/reopen-draft'}:
                self.send_json(403, {'error': 'Synthetic review server: no other writes allowed.'}); return
            super().do_POST()
    server = ThreadingHTTPServer(('127.0.0.1', port), FixtureHandler)
    print(f'SYNTHETIC HUNTER REVIEW ONLY http://127.0.0.1:{port}/', flush=True)
    try: server.serve_forever()
    except KeyboardInterrupt: pass
    finally: server.server_close(); case.doCleanups()


if __name__ == '__main__':
    if '--serve-fixture' in sys.argv:
        serve_fixture(8894)
    else:
        unittest.main()
