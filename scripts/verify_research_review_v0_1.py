"""Isolated review-boundary and guarded public-tool regression tests."""
import asyncio
import gzip
import json
import sys
import tempfile
import threading
import time
import unittest
import zlib
from contextlib import ExitStack
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from x_factory import idea_intake_v0_1 as idea
from x_factory import idea_research_v0_1 as research
from x_factory import idea_research_review_v0_1 as review
from x_factory import knowledge_loading_v0_1 as loading
from x_factory import public_research_tools_v0_1 as public
from x_factory import chassis_depot_v0_1 as depot
from verify_idea_research_v0_1 import example_result


def public_resolver(*args, **kwargs):
    return [(2, 1, 6, '', ('93.184.216.34', 443))]


class ResearchReviewTests(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.root = Path(self.stack.enter_context(tempfile.TemporaryDirectory(prefix='factory-research-review-')))
        self.stack.enter_context(patch.object(idea, 'IDEA_ROOT', self.root / 'ideas'))
        self.stack.enter_context(patch.object(research, 'JOB_ROOT', self.root / 'jobs'))
        self.stack.enter_context(patch.object(loading, 'KNOWLEDGE_ROOT', self.root / 'knowledge'))
        self.create = self.stack.enter_context(patch.object(depot, 'create_mission', side_effect=AssertionError('No build allowed')))
        self.capture = self.stack.enter_context(patch.object(idea, 'capture_website_knowledge', side_effect=AssertionError('No knowledge capture at review')))
        self.draft = idea.prepare_idea({'seed': 'Create a receptionist for a moving company.'})

    def finished(self, draft=None, envelope=None):
        envelope = deepcopy(envelope) if envelope is not None else example_result()
        job = research.start_research(draft or self.draft, worker=lambda *args, **kwargs: envelope)
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline:
            current = research.get_job(job['job_id'])
            if current['status'] in {'NEEDS_REVIEW', 'FAILED', 'CANCELLED'}:
                self.assertEqual(current['status'], 'NEEDS_REVIEW', current.get('message'))
                return current
            time.sleep(0.01)
        self.fail('Synthetic worker did not complete.')

    def request(self, job):
        return {'owner_requested': True, 'job_id': job['job_id'],
                'draft_sha256': self.draft['draft_sha256'], 'result_sha256': job['result_sha256'],
                'purpose': 'Welcome first-time visitors and prepare an intake brief for the moving team.',
                'selected_chassis_id': 'role-reception-intake'}

    def test_review_creates_a_new_selected_role_draft_without_knowledge_or_build(self):
        job = self.finished()
        result = review.review_direction(self.draft['idea_id'], self.request(job))
        fresh = result['draft']
        self.assertNotEqual(fresh['idea_id'], self.draft['idea_id'])
        self.assertEqual(idea.get_idea(self.draft['idea_id']), self.draft)
        self.assertEqual(idea.get_idea(fresh['idea_id']), fresh)
        self.assertEqual(fresh['fields']['client_name'], 'Sample Moving Company')
        self.assertEqual(fresh['website'], 'https://example.com/')
        self.assertEqual(fresh['fields']['purpose'], self.request(job)['purpose'])
        self.assertEqual(fresh['recommendation']['recommended']['chassis_id'], 'role-reception-intake')
        self.assertEqual(fresh['recommendation']['selected_by'], 'OWNER_EXPLICIT_CHOICE')
        self.assertFalse(result['review']['knowledge_approved'])
        self.assertFalse(result['review']['mission_created'])
        self.assertFalse((self.root / 'knowledge').exists())
        self.assertEqual(result['review']['result_sha256'], job['result_sha256'])
        receipt = json.loads(idea._draft_path(fresh['idea_id']).with_name('research-review.json').read_text())
        self.assertEqual(receipt, result['review'])
        self.create.assert_not_called()
        self.capture.assert_not_called()

    def test_wrong_job_hash_draft_or_review_authority_blocks_new_draft(self):
        job = self.finished()
        second = idea.prepare_idea({'seed': 'Create an onboarding guide for new clients.'})
        other_job = self.finished(second)
        request = self.request(job)
        before = set((self.root / 'ideas').iterdir())
        for changes in [{'job_id': other_job['job_id']}, {'result_sha256': '0' * 64},
                        {'draft_sha256': '0' * 64}, {'owner_requested': False},
                        {'owner_requested': 1}, {'knowledge_approved': True}]:
            with self.subTest(changes=changes):
                with self.assertRaises(idea.IdeaIntakeError):
                    review.review_direction(self.draft['idea_id'], request | changes)
                self.assertEqual(set((self.root / 'ideas').iterdir()), before)

    def test_active_or_terminally_failed_job_cannot_be_reviewed(self):
        release = threading.Event()
        def worker(*args, **kwargs):
            release.wait(2)
            return example_result()
        running = research.start_research(self.draft, worker=worker)
        try:
            request = {'owner_requested': True, 'job_id': running['job_id'],
                       'draft_sha256': self.draft['draft_sha256'], 'result_sha256': '0' * 64,
                       'purpose': 'Create a receptionist for moving inquiries.', 'selected_chassis_id': 'role-reception-intake'}
            with self.assertRaises(idea.IdeaIntakeError):
                review.review_direction(self.draft['idea_id'], request)
            research.cancel_research(running['job_id'])
            with self.assertRaises(idea.IdeaIntakeError):
                review.review_direction(self.draft['idea_id'], request)
        finally:
            release.set()
            # Ensure the worker unwinds before temporary roots are unpatched.
            deadline = time.monotonic() + 2
            while running['job_id'] in research._ACTIVE and time.monotonic() < deadline:
                time.sleep(0.01)

    def test_ambiguous_identity_requires_explicit_name_and_website(self):
        envelope = example_result()
        second = deepcopy(envelope['research']['company_candidates'][0])
        second['name'] = 'Sample Moving'
        envelope['research']['company_candidates'].append(second)
        envelope['research']['identity_status'] = 'AMBIGUOUS'
        job = self.finished(envelope=envelope)
        for additions in [{}, {'company_name': 'Chosen Company'}, {'website': 'https://example.com/'}]:
            with self.assertRaisesRegex(idea.IdeaIntakeError, 'More than one company'):
                review.review_direction(self.draft['idea_id'], self.request(job) | additions)
        result = review.review_direction(self.draft['idea_id'], self.request(job) | {
            'company_name': 'Chosen Company', 'website': 'https://example.com/'})
        self.assertEqual(result['draft']['fields']['client_name'], 'Chosen Company')
        self.assertEqual(result['draft']['website'], 'https://example.com/')
        self.assertFalse(result['review']['knowledge_approved'])

    def test_modified_saved_job_result_and_stale_draft_are_not_reviewable(self):
        job = self.finished()
        request = self.request(job)
        path = idea._draft_path(self.draft['idea_id'])
        changed = deepcopy(self.draft)
        changed['fields']['purpose'] = 'A newly edited job after research has completed.'
        changed['draft_sha256'] = idea._digest({k: v for k, v in changed.items() if k != 'draft_sha256'})
        path.write_text(json.dumps(changed), encoding='utf-8')
        with self.assertRaises(idea.IdeaIntakeError):
            review.review_direction(self.draft['idea_id'], request | {'draft_sha256': changed['draft_sha256']})
        path.write_text(json.dumps(self.draft), encoding='utf-8')
        result_path = research.JOB_ROOT / job['job_id'] / 'result.json'
        changed_result = json.loads(result_path.read_text())
        changed_result['summary'] = 'Edited after validation.'
        result_path.write_text(json.dumps(changed_result), encoding='utf-8')
        with self.assertRaises(research.IdeaResearchError):
            review.review_direction(self.draft['idea_id'], request)

    def test_review_recommendation_preserves_no_fit(self):
        result = review.recommendation('Build an autonomous stock trading agent that will execute trades.')
        self.assertEqual(result['fit_status'], 'NO_FIT')
        self.assertIsNone(result['recommended'])
        self.assertTrue(result['role_recommendation']['capability_gaps'])

    def test_non_string_review_fields_fail_with_plain_text_error(self):
        job = self.finished()
        request = self.request(job)
        before = set((self.root / 'ideas').iterdir())
        for field in ['job_id', 'result_sha256', 'draft_sha256', 'purpose', 'selected_chassis_id', 'company_name', 'website']:
            for value in [None, 12, True, ['text'], {'text': 'value'}]:
                with self.subTest(field=field, value=value):
                    with self.assertRaisesRegex(idea.IdeaIntakeError, 'must be plain text'):
                        review.review_direction(self.draft['idea_id'], request | {field: value})
                    self.assertEqual(set((self.root / 'ideas').iterdir()), before)
        self.create.assert_not_called()
        self.capture.assert_not_called()


class PublicToolsTests(unittest.TestCase):
    RESULT = b'<a class="result-link" href="https://example.com/about">Example Company</a>'

    def search(self, response, query='Example company flooring repair'):
        calls = []
        def fake_fetch(url):
            calls.append(url)
            return response
        with patch.object(public.socket, 'getaddrinfo', public_resolver), patch.object(public, '_default_fetch', fake_fetch):
            result = json.loads(public.search_public(query))
        return result, calls

    def test_search_preserves_query_and_marks_results_as_unread_leads(self):
        result, calls = self.search((200, {'content-type': 'text/html'}, self.RESULT), 'Example HVAC & plumbing')
        self.assertEqual(len(calls), 1)
        self.assertEqual(parse_qs(urlsplit(calls[0]).query)['q'], ['Example HVAC & plumbing'])
        self.assertTrue(result['success'])
        self.assertEqual(result['data']['web'][0]['url'], 'https://example.com/about')
        self.assertIn('Search result only', result['data']['web'][0]['description'])

    def test_search_rejects_non200_empty_and_access_challenges(self):
        for status, body in [(403, self.RESULT), (302, self.RESULT), (200, b''),
                             (200, b'<p>Please verify you are human.</p>'),
                             (200, b'<p>Please verify you are human.</p>' + self.RESULT)]:
            with self.subTest(status=status, body=body[:60]):
                result, calls = self.search((status, {'content-type': 'text/html'}, body))
                self.assertIn('error', result)
                self.assertNotIn('success', result)
                self.assertEqual(len(calls), 1)

    def test_extract_private_target_never_reaches_fetch(self):
        with patch.object(public.socket, 'getaddrinfo', return_value=[(2, 1, 6, '', ('127.0.0.1', 80))]), \
             patch.object(public, '_default_fetch', side_effect=AssertionError('Private fetch forbidden')) as fetch:
            result = json.loads(asyncio.run(public.extract_public(['http://127.0.0.1/private'])))
        self.assertIn('error', result['results'][0])
        fetch.assert_not_called()

    def test_extract_retains_good_text_despite_malformed_links(self):
        calls = []
        def fake_fetch(url):
            calls.append(url)
            return 200, {'content-type': 'text/html'}, b'''<title>Example Company</title>
            <main><p>We repair flooring and interior doors for customers.</p>
            <a href="http://[broken">Malformed link</a><a href="/services">Services</a>
            <a href="https://outside.example/">Outside link</a></main>'''
        with patch.object(public.socket, 'getaddrinfo', public_resolver), patch.object(public, '_default_fetch', fake_fetch):
            result = json.loads(asyncio.run(public.extract_public(['https://example.com/'])))
        page = result['results'][0]
        self.assertNotIn('error', page)
        self.assertIn('We repair flooring', page['content'])
        self.assertEqual(page['same_site_links'], ['https://example.com/services'])
        self.assertEqual(calls, ['https://example.com/'])

    def test_decoded_fetch_accepts_valid_gzip_and_deflate_html(self):
        html = b'<html><title>Example Services</title><p>We repair interior doors.</p></html>'
        for encoding, compressor in [('gzip', lambda body: gzip.compress(body, mtime=0)), ('deflate', zlib.compress)]:
            with self.subTest(encoding=encoding):
                headers = {'content-type': 'text/html', 'content-encoding': encoding}
                with patch.object(public, '_default_fetch', return_value=(200, headers, compressor(html))) as fetch:
                    status, actual_headers, decoded = public._decoded_fetch('https://example.com/')
                self.assertEqual(status, 200)
                self.assertEqual(actual_headers, {'content-type': 'text/html'})
                self.assertNotIn('content-encoding', actual_headers)
                self.assertEqual(decoded, html)
                fetch.assert_called_once_with('https://example.com/')

    def test_compressed_content_is_readable_in_search_and_extraction(self):
        html = b'<title>Example Services</title><p>We repair interior doors.</p>' + self.RESULT
        for encoding, compressor in [('gzip', lambda body: gzip.compress(body, mtime=0)), ('deflate', zlib.compress)]:
            with self.subTest(encoding=encoding):
                response = (200, {'content-type': 'text/html', 'content-encoding': encoding}, compressor(html))
                search, _ = self.search(response)
                self.assertTrue(search['success'])
                self.assertEqual(search['data']['web'][0]['title'], 'Example Company')
                with patch.object(public.socket, 'getaddrinfo', public_resolver), patch.object(public, '_default_fetch', return_value=response):
                    extracted = json.loads(asyncio.run(public.extract_public(['https://example.com/'])))
                page = extracted['results'][0]
                self.assertNotIn('error', page)
                self.assertEqual(page['title'], 'Example Services')
                self.assertIn('We repair interior doors.', page['content'])
                self.assertNotIn('\ufffd', page['content'])

    def test_decompression_rejects_expansion_past_one_megabyte(self):
        expanded = b'x' * (public.MAX_RESPONSE_BYTES + 1)
        for encoding, compressor in [('gzip', lambda body: gzip.compress(body, mtime=0)), ('deflate', zlib.compress)]:
            with self.subTest(encoding=encoding):
                compressed = compressor(expanded)
                self.assertLess(len(compressed), public.MAX_RESPONSE_BYTES)
                response = (200, {'content-type': 'text/html', 'content-encoding': encoding}, compressed)
                with patch.object(public, '_default_fetch', return_value=response):
                    with self.assertRaisesRegex(ValueError, 'decoded limit'):
                        public._decoded_fetch('https://example.com/')
                result, _ = self.search(response)
                self.assertIn('error', result)
                with patch.object(public.socket, 'getaddrinfo', public_resolver), patch.object(public, '_default_fetch', return_value=response):
                    extracted = json.loads(asyncio.run(public.extract_public(['https://example.com/'])))
                self.assertIn('error', extracted['results'][0])
                self.assertNotIn('content', extracted['results'][0])

    def test_malformed_truncated_or_unsupported_compression_is_rejected(self):
        html = b'<p>Normal complete HTML page with useful source content.</p>'
        gzip_body = gzip.compress(html, mtime=0)
        deflate_body = zlib.compress(html)
        cases = [
            ('gzip', b'not-gzip'), ('deflate', b'not-deflate'),
            ('gzip', gzip_body[:-4]), ('deflate', deflate_body[:-2]),
            ('gzip', gzip_body + b'trailing garbage'), ('deflate', deflate_body + b'trailing garbage'),
            ('br', b'unsupported-compression'), ('gzip, deflate', gzip_body),
        ]
        for encoding, body in cases:
            with self.subTest(encoding=encoding, length=len(body)):
                response = (200, {'content-type': 'text/html', 'content-encoding': encoding}, body)
                with patch.object(public, '_default_fetch', return_value=response):
                    with self.assertRaises((ValueError, zlib.error)):
                        public._decoded_fetch('https://example.com/')
                result, _ = self.search(response)
                self.assertIn('error', result)
                self.assertNotIn('success', result)


if __name__ == '__main__':
    unittest.main(verbosity=2)
