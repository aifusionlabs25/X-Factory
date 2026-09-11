"""Provider-free own-idea -> public source draft -> fact review regressions."""
import json
import sys
import tempfile
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from x_factory import idea_intake_v0_1 as idea
from x_factory import knowledge_loading_v0_1 as loading
from x_factory import chassis_depot_v0_1 as chassis
from x_factory.knowledge_compiler_v0_1 import review_compilation
from x_factory.website_ingestion_v0_1 import capture_website_knowledge, WebsiteCaptureError


def public_resolver(*args, **kwargs):
    return [(2, 1, 6, '', ('93.184.216.34', 443))]


class IdeaTests(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.root = Path(self.stack.enter_context(tempfile.TemporaryDirectory()))
        self.stack.enter_context(patch.object(idea, 'IDEA_ROOT', self.root / 'ideas'))
        self.stack.enter_context(patch.object(loading, 'KNOWLEDGE_ROOT', self.root / 'knowledge'))
        self.calls = []

    def capture(self, value):
        def fetch(url):
            self.calls.append(url)
            self.assertTrue(url.startswith('https://example.com/'))
            return 200, {'content-type': 'text/html'}, b'''<html><head><title>Fictional Services</title></head>
            <body><main><h1>Our services</h1><p>We repair water heaters and air conditioning systems.</p>
            <h2>Our service area</h2><p>We serve customers in Fictional City.</p>
            <h2>Pricing policy</h2><p>Final pricing requires staff review.</p>
            <a href="/services">Services</a><a href="https://outside.example/">External site</a></main></body></html>'''
        return capture_website_knowledge(value, resolver=public_resolver, fetcher=fetch)

    def draft(self, **updates):
        return idea.prepare_idea({'seed': 'An assistant for home service requests',
                                  'company_name': 'Fictional Services',
                                  'website': 'https://example.com/', **updates})

    def request(self, draft):
        return {'idea_id': draft['idea_id'], 'draft_sha256': draft['draft_sha256'], 'owner_requested': True}

    def test_prepare_all_entry_types_without_network_or_mission(self):
        with patch.object(idea, 'capture_website_knowledge', side_effect=AssertionError('No implicit capture')):
            for seed, kind in [('Make a receptionist for plumbing firms', 'IDEA'),
                               ('Fictional Plumbing Company', 'COMPANY_NAME'),
                               ('example.com', 'WEBSITE'),
                               ('https://x.com/someone/status/12345', 'X_POST')]:
                draft = idea.prepare_idea({'seed': seed})
                self.assertEqual(draft['seed_kind'], kind)
                self.assertEqual(idea.get_idea(draft['idea_id']), draft)
                self.assertEqual(draft['provider_calls'], 0)
                self.assertFalse(draft['mission_created'])
                self.assertFalse(draft['knowledge_approved'])
                recommendation = draft['recommendation']
                self.assertIn(recommendation['fit_status'], {'FIT', 'POSSIBLE_FIT', 'NO_FIT'})
                if recommendation['recommended'] is None:
                    self.assertEqual(recommendation['fit_status'], 'NO_FIT')
                else:
                    self.assertTrue(recommendation['recommended']['chassis_id'])
                self.assertEqual(draft['fields']['client_context'], '')
        self.assertFalse((self.root / 'knowledge').exists())

    def test_owner_purpose_flows_unchanged_to_recommendation(self):
        purpose = 'Help visitors compare approved flooring repair options, then prepare a staff handoff.'
        for seed in ['An assistant for home service requests', 'https://x.com/someone/status/12345']:
            draft = self.draft(seed=seed, purpose=purpose, post_text='A different opportunity in pet boarding.')
            self.assertEqual(draft['fields']['purpose'], purpose)
            self.assertEqual(draft['recommendation']['owner_intent'], purpose)

    def test_x_owner_context_and_pasted_use_case_shape_the_proposed_job(self):
        seed = 'Build a guide for first-time pet owners. https://x.com/someone/status/12345'
        post = 'Pet boarding customers need help comparing approved care options and preparing intake questions.'
        draft = self.draft(seed=seed, post_text=post)
        purpose = draft['fields']['purpose']
        self.assertIn('first-time pet owners', purpose)
        self.assertIn('Pet boarding customers', purpose)
        self.assertIn('unverified design inspiration', purpose)
        self.assertIn('Owner-pasted post', purpose)
        self.assertEqual(draft['fields']['client_context'], '')
        self.assertEqual(draft['recommendation']['owner_intent'], ' '.join(purpose.split()))
        self.assertLessEqual(len(purpose), 2000)
        result = idea.research_idea(self.request(draft), capture=self.capture)
        files = loading._package_root(result['package']['package_id']) / 'files'
        sources = ' '.join(path.read_text(encoding='utf-8') for path in files.iterdir())
        self.assertNotIn('pet owners', sources)
        self.assertNotIn('Pet boarding', sources)
        self.assertIn('water heaters', sources)
        link_only = self.draft(seed='https://x.com/someone/status/12345')
        self.assertTrue(any('generic starting draft' in notice for notice in link_only['notices']))
        self.assertTrue(any('post text or describe the agent job' in item for item in link_only['missing_information']))
        pasted_only = self.draft(seed='https://x.com/someone/status/12345', post_text=post)
        self.assertIn('Pet boarding customers', pasted_only['fields']['purpose'])
        self.assertFalse(any('post text or describe the agent job' in item for item in pasted_only['missing_information']))

    def test_name_or_post_requires_real_company_context(self):
        for seed in ['Fictional Plumbing Company', 'https://x.com/someone/status/12345']:
            draft = idea.prepare_idea({'seed': seed})
            with self.assertRaisesRegex(idea.IdeaIntakeError, 'public company website'):
                idea.research_idea(self.request(draft), capture=self.capture)
        draft = idea.prepare_idea({'seed': 'https://example.com/'})
        with self.assertRaisesRegex(idea.IdeaIntakeError, 'company or project name'):
            idea.research_idea(self.request(draft), capture=self.capture)
        self.assertEqual(self.calls, [])

    def test_post_inspiration_never_becomes_knowledge(self):
        draft = self.draft(seed='https://x.com/someone/status/12345', post_text='INSPIRATION_ONLY_SENTINEL: This company gives every service away free.')
        result = idea.research_idea(self.request(draft), capture=self.capture)
        package_id = result['package']['package_id']
        self.assertFalse(result['knowledge_approved'])
        self.assertFalse(result['mission_created'])
        self.assertEqual(result['provider_calls'], 0)
        self.assertIsNone(result['compilation']['latest_review'])
        self.assertGreater(len(result['compilation']['entries']), 0)
        source_text = ' '.join(p.read_text(encoding='utf-8') for p in (self.root / 'knowledge' / package_id / 'files').iterdir())
        self.assertNotIn('INSPIRATION_ONLY_SENTINEL', source_text)
        self.assertNotIn(draft['fields']['purpose'], source_text)
        self.assertIn('water heaters', source_text)
        self.assertTrue(all('x.com' not in url for url in self.calls))
        with self.assertRaises(loading.KnowledgeLoadingError):
            loading.commissioning_reference(package_id)
        # Independent owner fact review remains the only route into a build.
        comp = result['compilation']
        review_compilation(package_id, {'compilation_id': comp['compilation_id'], 'decisions': [
            {'entry_id': e['entry_id'], 'decision': 'APPROVE'} for e in comp['entries']]})
        self.assertGreater(loading.commissioning_reference(package_id)['approved_entries'], 0)

    def test_research_reuses_exact_capture_without_new_requests(self):
        draft = self.draft()
        first = idea.research_idea(self.request(draft), capture=self.capture)
        count = len(self.calls)
        second = idea.research_idea(self.request(draft), capture=self.capture)
        self.assertFalse(first['reused'])
        self.assertTrue(second['reused'])
        self.assertEqual(first['package']['package_id'], second['package']['package_id'])
        self.assertEqual(len(self.calls), count)

    def test_commissioning_requires_review_and_preserves_prepared_identity(self):
        # Exercise the real commissioning validation and payload mapping, while
        # replacing only the final mission writer. No real candidate is built.
        with patch.object(chassis, 'create_mission', return_value={'mission_id': 'fixture-no-build'}) as create:
            draft = self.draft(purpose='Help home-service customers describe water heater problems and prepare a staff handoff.')
            result = idea.research_idea(self.request(draft), capture=self.capture)
            create.assert_not_called()
            self.assertIsNone(result['compilation']['latest_review'])
            self.assertFalse(result['knowledge_approved'])
            self.assertFalse(result['mission_created'])
            package_id = result['package']['package_id']
            chassis_id = draft['recommendation']['recommended']['chassis_id']
            request = {**draft['fields'], 'x_agent_name': 'Test Ava',
                       'knowledge_package_id': package_id, 'optional_module_ids': []}
            with self.assertRaisesRegex(chassis.ChassisDepotError, 'Owner Review Desk'):
                chassis.commission_chassis(chassis_id, request)
            create.assert_not_called()

            comp = result['compilation']
            review_compilation(package_id, {'compilation_id': comp['compilation_id'], 'decisions': [
                {'entry_id': entry['entry_id'], 'decision': 'APPROVE'} for entry in comp['entries']]})
            # Reviewing facts also does not commission anything automatically.
            create.assert_not_called()
            for changes in [{'client_name': 'Unrelated Company'},
                            {'purpose': 'Help pet owners compare boarding services and prepare an intake.'}]:
                with self.assertRaisesRegex(chassis.ChassisDepotError, 'different company or job'):
                    chassis.commission_chassis(chassis_id, request | changes)
                create.assert_not_called()

            record = chassis.commission_chassis(chassis_id, request)
            create.assert_called_once()
            mission_payload = create.call_args.args[0]
            self.assertEqual(mission_payload['client_name'], draft['fields']['client_name'])
            self.assertEqual(mission_payload['purpose'], draft['fields']['purpose'])
            self.assertEqual(mission_payload['x_agent_name'], 'Test Ava')
            self.assertEqual(mission_payload['knowledge_package']['package_id'], package_id)
            self.assertEqual(mission_payload['knowledge_package']['manifest_sha256'], result['package']['manifest_sha256'])
            self.assertIn('CMP-CLIENT-KNOWLEDGE-PACK', mission_payload['selected_optional_modules'])
            self.assertEqual(record['commissioning_summary']['commissioned_instance_intent'], draft['fields']['purpose'])
            self.assertFalse(record['commissioning_summary']['production_approved'])
            self.assertFalse((self.root / 'missions').exists())

    def test_commissioning_blocks_changed_source_binding(self):
        draft = self.draft()
        result = idea.research_idea(self.request(draft), capture=self.capture)
        comp = result['compilation']
        package_id = result['package']['package_id']
        review_compilation(package_id, {'compilation_id': comp['compilation_id'], 'decisions': [
            {'entry_id': entry['entry_id'], 'decision': 'APPROVE'} for entry in comp['entries']]})
        binding_path = loading._package_root(package_id) / 'idea-preparation-binding.v0.1.json'
        binding = json.loads(binding_path.read_text(encoding='utf-8'))
        binding['client_name'] = 'Tampered company'
        binding_path.write_text(json.dumps(binding), encoding='utf-8')
        request = {**draft['fields'], 'x_agent_name': 'Test Ava',
                   'knowledge_package_id': package_id, 'optional_module_ids': []}
        with patch.object(chassis, 'create_mission', side_effect=AssertionError('No real build')) as create:
            with self.assertRaisesRegex(chassis.ChassisDepotError, 'source binding changed'):
                chassis.commission_chassis(draft['recommendation']['recommended']['chassis_id'], request)
            create.assert_not_called()

    def test_request_scope_integrity_and_identity_binding(self):
        draft = self.draft()
        request = self.request(draft)
        for changes in [{'owner_requested': False}, {'owner_requested': 1}, {'draft_sha256': '0' * 64},
                        {'url': 'https://elsewhere.example/'}, {'approve': True}, {'idea_id': '../escape'}]:
            with self.assertRaises(idea.IdeaIntakeError):
                idea.research_idea(request | changes, capture=self.capture)
        self.assertEqual(self.calls, [])
        result = idea.research_idea(request, capture=self.capture)
        package_id = result['package']['package_id']
        fields = draft['fields']
        idea.assert_idea_knowledge_identity(package_id, fields['client_name'], fields['purpose'])
        for name, purpose in [('Different Company', fields['purpose']), (fields['client_name'], 'A different job')]:
            with self.assertRaises(loading.KnowledgeLoadingError):
                idea.assert_idea_knowledge_identity(package_id, name, purpose)
        path = idea._draft_path(draft['idea_id'])
        changed = dict(draft, website='https://elsewhere.example/')
        path.write_text(json.dumps(changed), encoding='utf-8')
        with self.assertRaises(idea.IdeaIntakeError):
            idea.research_idea(request, capture=self.capture)

    def test_invalid_inputs_never_fetch_or_persist(self):
        for request in [{'seed': 'abc', 'approve': True}, {'seed': ['not text']},
                        {'seed': 'https://127.0.0.1/'}, {'seed': 'https://localhost/'},
                        {'seed': 'https://name:password@example.com/'},
                        {'seed': 'Fine idea', 'website': 'file:///etc/passwd'},
                        {'seed': 'Fine idea', 'website': 'https://x.com/user/status/123'},
                        {'seed': 'Fine idea', 'purpose': 'password=do-not-save-me'}]:
            with self.assertRaises((idea.IdeaIntakeError, WebsiteCaptureError)):
                idea.prepare_idea(request)
        self.assertFalse((self.root / 'ideas').exists())
        self.assertEqual(self.calls, [])

    def test_private_dns_blocks_before_download(self):
        draft = self.draft()
        def private_capture(value):
            return capture_website_knowledge(value,
                resolver=lambda *args, **kwargs: [(2, 1, 6, '', ('127.0.0.1', 80))],
                fetcher=lambda url: self.fail('Private address reached fetch'))
        with self.assertRaises(WebsiteCaptureError):
            idea.research_idea(self.request(draft), capture=private_capture)
        self.assertFalse((self.root / 'knowledge').exists())


if __name__ == '__main__':
    unittest.main(verbosity=2)
