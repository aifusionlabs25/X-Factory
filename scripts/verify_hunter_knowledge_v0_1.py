"""Synthetic, provider-free Hunter -> fact review regression. Never builds missions."""
import json
import sys
import threading
from copy import deepcopy
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen
import unittest

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from verify_hunter_draft_v0_1 import DraftTests, bridge, server_module
from x_factory import hunter_knowledge_v0_1 as preparation
from x_factory import knowledge_loading_v0_1 as loading
from x_factory.knowledge_compiler_v0_1 import review_compilation
from x_factory.website_ingestion_v0_1 import capture_website_knowledge, WebsiteCaptureError


def public_resolver(*args, **kwargs):
    return [(2, 1, 6, '', ('93.184.216.34', 443))]


def fake_fetch(url):
    if not url.startswith('https://example.com/'):
        raise AssertionError('External website fetch forbidden in fixture')
    if url.endswith('/missing'):
        return 404, {'content-type': 'text/html'}, b'Not found'
    return 200, {'content-type': 'text/html'}, b'''<html><head><title>Fictional Service Company</title></head>
    <body><main><h1>Services</h1><p>We repair water heaters and air conditioning systems.</p>
    <h2>Service area</h2><p>We serve customers in Fictional City.</p>
    <h2>Pricing policy</h2><p>Final pricing requires staff review.</p>
    <a href="/services">Services</a><a href="/missing">Retired page</a></main></body></html>'''


class KnowledgeTests(DraftTests):
    def setUp(self):
        super().setUp()
        self.stack.enter_context(patch.object(loading, 'KNOWLEDGE_ROOT', self.root / 'knowledge'))
        self.stack.enter_context(patch.object(preparation, 'PREPARATION_ROOT', self.root / 'preparations'))
        self.calls = []

    def capture(self, value, **kwargs):
        def fetch(url):
            self.calls.append(url)
            return fake_fetch(url)
        return capture_website_knowledge(value, resolver=public_resolver, fetcher=fetch, **kwargs)

    def accepted_plan(self):
        bridge.accept_draft(self.request())
        return preparation.knowledge_plan({'source_id': bridge.SOURCE_ID, 'prospect_id': 'synthetic-hunter-fixture'})

    def prepare_request(self, plan):
        return {key: plan[key] for key in ('source_id', 'prospect_id', 'plan_sha256')} | {'owner_requested': True}

    def test_plan_is_read_only_requires_saved_review(self):
        req = {'source_id': bridge.SOURCE_ID, 'prospect_id': 'synthetic-hunter-fixture'}
        with self.assertRaises(bridge.HunterDraftError): preparation.knowledge_plan(req)
        plan = self.accepted_plan()
        self.assertFalse((self.root / 'knowledge').exists())
        self.assertFalse((self.root / 'preparations').exists())
        self.assertEqual(self.calls, [])
        self.assertEqual(len(plan['sources']), 3)
        self.assertEqual(plan['fields']['x_agent_name'], 'Test Ava')

    def test_preparation_retains_fact_review_gate_and_separates_research(self):
        plan = self.accepted_plan()
        req = self.prepare_request(plan)
        result = preparation.prepare_knowledge(req, capture=self.capture)
        self.assertFalse(result['knowledge_approved'])
        self.assertFalse(result['mission_created'])
        self.assertEqual(result['provider_calls'], 0)
        self.assertIsNone(result['compilation']['latest_review'])
        package_id = result['package']['package_id']
        with self.assertRaises(loading.KnowledgeLoadingError): loading.commissioning_reference(package_id)
        sources = ' '.join(p.read_text() for p in (self.root / 'knowledge' / package_id / 'files').iterdir())
        self.assertNotIn('UNAPPROVED_RESEARCH_SENTINEL', sources)
        self.assertNotIn(plan['fields']['purpose'], sources)
        self.assertIn('water heaters', sources)
        self.assertEqual(result['package']['website_capture']['skipped_pages'], [{
            'url': 'https://example.com/missing', 'reason': 'HTTP_404', 'source': 'DISCOVERED_LINK'}])
        self.assertLessEqual(len(self.calls), 6)
        outline_ids = [i for s in result['outline'] for i in s['entry_ids']]
        self.assertCountEqual(outline_ids, [e['entry_id'] for e in result['compilation']['entries']])
        self.assertEqual(result['outline'][-1]['status'], 'NEEDS_OWNER_INFORMATION')
        calls = len(self.calls)
        repeated = preparation.prepare_knowledge(req, capture=self.capture)
        self.assertEqual(repeated['package']['package_id'], package_id)
        self.assertEqual(len(self.calls), calls, 'Same plan must reuse exact draft without a second fetch')
        # Only an independent, explicit owner review makes these facts attachable.
        comp = result['compilation']
        review_compilation(package_id, {'compilation_id': comp['compilation_id'], 'decisions': [
            {'entry_id': e['entry_id'], 'decision': 'APPROVE'} for e in comp['entries']]})
        self.assertGreater(loading.commissioning_reference(package_id)['approved_entries'], 0)
        self.assertFalse((self.root / 'missions').exists())

    def test_forged_request_and_drift_block_before_fetch(self):
        plan = self.accepted_plan()
        req = self.prepare_request(plan)
        for changes in ({'owner_requested': False}, {'owner_requested': 1}, {'plan_sha256': '0' * 64},
                        {'url': 'https://outside.example/'}, {'approve': True}):
            with self.assertRaises(bridge.HunterDraftError): preparation.prepare_knowledge(req | changes, capture=self.capture)
        target = bridge.receipt_path('synthetic-hunter-fixture')
        record = json.loads(target.read_text())
        record['fields']['purpose'] = 'Tampered purpose'
        target.write_text(json.dumps(record))
        with self.assertRaises(bridge.HunterDraftError): preparation.prepare_knowledge(req, capture=self.capture)
        self.assertEqual(self.calls, [])

    def test_hold_and_source_drift_block_preparation(self):
        plan = self.accepted_plan()
        with patch.object(bridge, 'BLOCKED', {'synthetic-hunter-fixture': 'HOLD'}):
            with self.assertRaises(bridge.HunterDraftError): preparation.prepare_knowledge(self.prepare_request(plan), capture=self.capture)
        self.source.write_text('{}')
        with self.assertRaises(bridge.HunterDraftError): preparation.prepare_knowledge(self.prepare_request(plan), capture=self.capture)
        self.assertEqual(self.calls, [])

    def test_company_job_binding_and_receipt_integrity(self):
        plan = self.accepted_plan()
        req = self.prepare_request(plan)
        result = preparation.prepare_knowledge(req, capture=self.capture)
        package_id = result['package']['package_id']
        preparation.assert_knowledge_identity(package_id, plan['fields']['client_name'], plan['fields']['purpose'])
        for company, purpose in [('Unrelated Company', plan['fields']['purpose']), (plan['fields']['client_name'], 'A different job')]:
            with self.assertRaises(loading.KnowledgeLoadingError): preparation.assert_knowledge_identity(package_id, company, purpose)
        target = self.root / 'preparations' / (plan['plan_sha256'] + '.json')
        receipt = json.loads(target.read_text())
        receipt['package_id'] = 'kp-unrelated'
        target.write_text(json.dumps(receipt))
        before = len(self.calls)
        with self.assertRaises(bridge.HunterDraftError): preparation.prepare_knowledge(req, capture=self.capture)
        self.assertEqual(len(self.calls), before)

    def test_changed_company_cannot_reach_build(self):
        from x_factory import chassis_depot_v0_1 as chassis
        plan = self.accepted_plan()
        result = preparation.prepare_knowledge(self.prepare_request(plan), capture=self.capture)
        comp = result['compilation']
        review_compilation(result['package']['package_id'], {'compilation_id': comp['compilation_id'], 'decisions': [
            {'entry_id': e['entry_id'], 'decision': 'APPROVE'} for e in comp['entries']]})
        request = {**plan['fields'], 'client_name': 'Unrelated Company', 'client_context': '',
                   'knowledge_package_id': result['package']['package_id'], 'optional_module_ids': []}
        with patch.object(chassis, 'create_mission', side_effect=AssertionError('No build allowed')):
            with self.assertRaisesRegex(chassis.ChassisDepotError, 'different company'):
                chassis.commission_chassis(bridge.CHASSIS_ID, request)

    def test_outside_source_is_not_followed(self):
        p = self.run['qualified_prospects'][0]
        p['public_sources'][1]['url'] = 'https://outside.example/review'
        p['factory_intake_brief']['website_sources_for_factory_review'] = [s['url'] for s in p['public_sources']]
        self.save_source()
        plan = self.accepted_plan()
        self.assertEqual(len(plan['excluded_sources']), 1)
        preparation.prepare_knowledge(self.prepare_request(plan), capture=self.capture)
        self.assertTrue(all(url.startswith('https://example.com/') for url in self.calls))

    def test_challenge_private_redirect_and_timeout_create_no_knowledge(self):
        plan = self.accepted_plan()
        for mode in ('challenge', 'private', 'redirect', 'timeout'):
            def fetch(url):
                if mode == 'timeout': raise WebsiteCaptureError('Website timed out')
                if mode == 'redirect': return 302, {'location': 'https://outside.example/'}, b''
                return 200, {'content-type': 'text/html'}, b'<title>Robot Challenge Screen</title><p>Please verify you are human before continuing.</p>'
            def resolver(*args, **kwargs):
                return [(2, 1, 6, '', ('127.0.0.1', 80))] if mode == 'private' else public_resolver()
            def capture(value, **kwargs):
                return capture_website_knowledge(value, resolver=resolver, fetcher=fetch, **kwargs)
            with self.assertRaises(WebsiteCaptureError): preparation.prepare_knowledge(self.prepare_request(plan), capture=capture)
            self.assertFalse((self.root / 'knowledge').exists())
            self.assertFalse((self.root / 'preparations').exists())

    def test_seed_boundary_and_empty_page_budget(self):
        with self.assertRaises(WebsiteCaptureError):
            capture_website_knowledge({'url': 'https://example.com/', 'label': 'Synthetic'}, seed_urls=['https://outside.example/'], fetcher=fake_fetch, resolver=public_resolver)
        attempted = []
        def fetch(url):
            attempted.append(url)
            if url.endswith('/'): return 200, {'content-type': 'text/html'}, ('<p>We repair air conditioners in Fictional City.</p>' + ''.join(f'<a href="/p-{i}">Link {i}</a>' for i in range(100))).encode()
            return 200, {'content-type': 'text/plain'}, b''
        capture_website_knowledge({'url': 'https://example.com/', 'label': 'Synthetic'}, fetcher=fetch, resolver=public_resolver)
        self.assertEqual(len(attempted), 6)

    def test_http_prepare_cannot_build_approve_facts_or_cross_origin(self):
        plan = self.accepted_plan()
        self.stack.enter_context(patch.object(preparation, 'capture_website_knowledge', self.capture))
        for name in ['create_mission', 'commission_chassis', 'review_compilation', 'complete_local_draft', 'create_local_repo', 'request_governed_run']:
            self.stack.enter_context(patch.object(server_module, name, side_effect=AssertionError('Forbidden side effect')))
        server = ThreadingHTTPServer(('127.0.0.1', 0), server_module.MissionControlHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
        try:
            url = f'http://127.0.0.1:{server.server_port}/api/hunter/prepare-knowledge'
            payload = json.dumps(self.prepare_request(plan)).encode()
            with self.assertRaises(HTTPError) as error:
                urlopen(Request(url, payload, {'Content-Type': 'application/json', 'Origin': 'https://outside.example'}))
            self.assertEqual(error.exception.code, 403)
            self.assertEqual(self.calls, [])
            with urlopen(Request(url, payload, {'Content-Type': 'application/json'})) as response:
                result = json.load(response)
                self.assertIsNone(result['compilation']['latest_review'])
                self.assertFalse(result['mission_created'])
        finally:
            server.shutdown(); server.server_close(); thread.join()


def serve_fixture():
    case = KnowledgeTests(); case.setUp()
    case.stack.enter_context(patch.object(preparation, 'capture_website_knowledge', case.capture))
    case.stack.enter_context(patch.object(server_module, 'list_missions', lambda: []))
    class FixtureHandler(server_module.MissionControlHandler):
        def do_POST(self):
            if not (self.path.startswith('/api/hunter/') or self.path.endswith('/compilation/review')):
                self.send_json(403, {'error': 'Synthetic knowledge review only. No build.'}); return
            super().do_POST()
    server = ThreadingHTTPServer(('127.0.0.1', 8894), FixtureHandler)
    print('SYNTHETIC KNOWLEDGE REVIEW http://127.0.0.1:8894/ (no external network or real approval)', flush=True)
    try: server.serve_forever()
    except KeyboardInterrupt: pass
    finally: server.server_close(); case.doCleanups()


if __name__ == '__main__':
    if '--serve-fixture' in sys.argv: serve_fixture()
    else: unittest.main()
