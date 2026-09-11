"""Execute the worker's actual guard functions with local, synthetic dependencies.

AST extraction avoids importing Hermes, resolving authentication, installing an
audit hook, spawning a child, or making any socket/provider request. These are
boundary unit tests, not a claim that a live Hermes run succeeded.
"""
from __future__ import annotations

import ast
import asyncio
import hashlib
import ipaddress
import json
import os
import sys
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from urllib.parse import urlsplit

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from x_factory import public_research_tools_v0_1 as public

WORKER = ROOT / 'scripts/hermes_idea_research_worker.py'
TREE = ast.parse(WORKER.read_text(encoding='utf-8'))
GUARDS = ('audit', 'blocked', 'check_send', 'guarded_send', 'guarded_async_send',
          'reserve_tool', 'search', 'extract')


def guard_namespace(**overrides):
    definitions = []
    for name in GUARDS:
        matches = [node for node in ast.walk(TREE)
                   if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name]
        if len(matches) != 1:
            raise AssertionError(f'Expected one real worker definition for {name}')
        definitions.append(matches[0])
    namespace = {
        '__name__': 'synthetic_runtime_guard_test', 'json': json, 'threading': threading,
        'hashlib': hashlib, 'ipaddress': ipaddress, 'os': os, 'sys': sys, 'Path': Path,
        'datetime': datetime, 'timezone': timezone, 'urlsplit': urlsplit,
        'work': ROOT / 'verification/synthetic-guard-no-files',
        'request': {'preflight': False}, 'specialist': None, 'blocked_events': [], 'lock': threading.Lock(),
        'state': {'model_calls': 0, 'tool_calls': 0}, 'sent_bodies': set(),
        'max_models': 8, 'max_tools': 12, 'max_sources': 8, 'max_evidence_chars': 80000,
        'evidence': {}, 'source_ids': {}, 'attempted_urls': set(),
        'citation_view': lambda record, source_id: {'source_id': source_id, 'title': record['title']},
    }
    namespace.update(overrides)
    exec(compile(ast.Module(body=definitions, type_ignores=[]), str(WORKER), 'exec'), namespace)
    return namespace


def request(number=0, host='chatgpt.com', path='/backend-api/codex/responses'):
    return SimpleNamespace(url=SimpleNamespace(host=host, path=path), content=f'{{"request":{number}}}'.encode())


class RuntimeGuards(unittest.TestCase):
    def test_specialist_has_one_call_and_no_web_transport(self):
        ns=guard_namespace(specialist={'actor':'troy'},max_models=1,max_tools=0)
        ns['check_send'](request())
        with self.assertRaises(PermissionError):ns['check_send'](request(1))
        with self.assertRaises(PermissionError):ns['check_send'](request(host='example.com',path='/'))
        with self.assertRaises(PermissionError):ns['reserve_tool']()
    def test_parallel_model_calls_never_exceed_eight(self):
        ns = guard_namespace()
        def call(number):
            try:
                ns['check_send'](request(number))
                return True
            except PermissionError:
                return False
        with ThreadPoolExecutor(max_workers=8) as pool:
            accepted = list(pool.map(call, range(24)))
        self.assertEqual(sum(accepted), 8)
        self.assertEqual(ns['state']['model_calls'], 8)

    def test_identical_request_retry_is_blocked_before_transport(self):
        sent = []
        ns = guard_namespace(original_send=lambda client, req: sent.append(req))
        ns['guarded_send'](None, request())
        with self.assertRaises(PermissionError):
            ns['guarded_send'](None, request())
        self.assertEqual(len(sent), 1)
        self.assertEqual(ns['state']['model_calls'], 1)

    def test_async_request_uses_same_counter_and_retry_guard(self):
        sent = []
        async def send(client, req):
            sent.append(req)
        ns = guard_namespace(original_async_send=send)
        asyncio.run(ns['guarded_async_send'](None, request()))
        with self.assertRaises(PermissionError):
            asyncio.run(ns['guarded_async_send'](None, request()))
        self.assertEqual(len(sent), 1)

    def test_refresh_endpoint_and_refresh_method_are_blocked(self):
        ns = guard_namespace()
        for host in ('auth.openai.com', 'login.microsoftonline.com'):
            with self.assertRaises(PermissionError):
                ns['check_send'](request(host=host))
        with self.assertRaises(PermissionError):
            ns['blocked']()
        self.assertEqual(ns['state']['model_calls'], 0)

    def test_tool_budget_stops_before_thirteenth_operation(self):
        ns = guard_namespace()
        for _ in range(12):
            ns['reserve_tool']()
        with self.assertRaises(PermissionError):
            ns['reserve_tool']()
        self.assertEqual(ns['state']['tool_calls'], 12)

    def test_parallel_extract_reserves_sources_and_caps_evidence(self):
        reads = []
        async def backend(urls, format, char_limit):
            reads.extend(urls)
            await asyncio.sleep(0)
            return json.dumps({'results': [{'url': url, 'title': 'Synthetic source', 'content': 'Useful public source content. ' * 3} for url in urls]})
        ns = guard_namespace(original_extract=backend, max_evidence_chars=190)
        async def run():
            return await asyncio.gather(*(ns['extract']([f'https://example.com/page-{i + j}' for j in range(4)]) for i in (0, 4, 8)))
        returned = [json.loads(value) for value in asyncio.run(run())]
        self.assertEqual(len(reads), 8)
        self.assertEqual(len(set(reads)), 8)
        self.assertEqual(len(ns['attempted_urls']), 8)
        self.assertLessEqual(sum(len(row['text']) for row in ns['evidence'].values()), 190)
        self.assertLessEqual(sum(len(row.get('content', '')) for value in returned for row in value.get('results', [])), 190)

    def test_failed_source_is_not_retried(self):
        reads = []
        async def backend(urls, format, char_limit):
            reads.extend(urls)
            return json.dumps({'results': [{'url': url, 'error': 'Unavailable'} for url in urls]})
        ns = guard_namespace(original_extract=backend)
        for _ in range(2):
            asyncio.run(ns['extract'](['https://example.com/unavailable']))
        self.assertEqual(reads, ['https://example.com/unavailable'])
        self.assertEqual(ns['evidence'], {})

    def test_repeated_source_reuses_immutable_snapshot(self):
        reads = []
        async def backend(urls, format, char_limit):
            reads.extend(urls)
            return json.dumps({'results': [{'url': url, 'title': 'Original title', 'content': 'Original source passage remains unchanged.'} for url in urls]})
        ns = guard_namespace(original_extract=backend)
        first = json.loads(asyncio.run(ns['extract'](['https://example.com/'])))
        second = json.loads(asyncio.run(ns['extract'](['https://example.com/'])))
        self.assertEqual(len(reads), 1)
        self.assertEqual(first['results'][0]['content'], second['results'][0]['content'])
        self.assertEqual(len(ns['evidence']), 1)

    def test_challenge_text_is_removed_before_model_disclosure(self):
        async def backend(urls, format, char_limit):
            return json.dumps({'results': [{'url': urls[0], 'content': 'Verify you are human. Challenge instruction text.'}]})
        ns = guard_namespace(original_extract=backend)
        result = json.loads(asyncio.run(ns['extract'](['https://example.com/'])))
        self.assertNotIn('content', result['results'][0])
        self.assertNotIn('Challenge instruction text', json.dumps(result))
        self.assertEqual(ns['evidence'], {})

    def test_extract_allowlist_removes_metadata_and_caps_content_links(self):
        async def backend(urls, format, char_limit):
            return json.dumps({'raw_html': 'UNTRUSTED_EXTRA_METADATA', 'results': [{
                'url': urls[0], 'title': 'T' * 3000, 'content': 'Useful source material. ' * 10000,
                'extra': 'UNTRUSTED_EXTRA_METADATA', 'private_provider_detail': 'UNTRUSTED_EXTRA_METADATA',
                'same_site_links': ['https://other.example/ignore', 'https://example.com/' + 'x' * 3000,
                                    *[f'https://example.com/page-{i}' for i in range(20)]],
            }]})
        ns = guard_namespace(original_extract=backend)
        result = json.loads(asyncio.run(ns['extract'](['https://example.com/'])))
        row = result['results'][0]
        self.assertEqual(set(result), {'results'})
        self.assertEqual(set(row), {'url', 'title', 'content', 'citation', 'same_site_links'})
        self.assertEqual(len(row['content']), 16000)
        self.assertEqual(len(row['title']), 400)
        self.assertNotIn('UNTRUSTED_EXTRA_METADATA', json.dumps(result))
        self.assertLessEqual(len(row['same_site_links']), 12)
        self.assertTrue(all(len(link) <= 2048 and urlsplit(link).hostname == 'example.com' for link in row['same_site_links']))

    def test_extract_errors_are_sanitized_before_model_receives_them(self):
        async def backend(urls, format, char_limit):
            return json.dumps({'results': [{'url': urls[0], 'error': 'PRIVATE_PROVIDER_DETAIL', 'content': 'PRIVATE_PROVIDER_DETAIL'}]})
        ns = guard_namespace(original_extract=backend)
        result = json.loads(asyncio.run(ns['extract'](['https://example.com/'])))
        self.assertEqual(set(result['results'][0]), {'url', 'error'})
        self.assertNotIn('PRIVATE_PROVIDER_DETAIL', json.dumps(result))

    def test_search_wrapper_caps_query_and_sanitizes_all_backends(self):
        called = []
        def backend(query, limit):
            called.append((query, limit))
            return json.dumps({'extra': 'REMOVE_EXTRA', 'data': {'web': [{
                'url': 'https://example.com/', 'title': 'T' * 5000, 'description': 'D' * 5000, 'extra': 'REMOVE_EXTRA',
            }]}})
        ns = guard_namespace(original_search=backend)
        result = json.loads(ns['search']('q' * 2000, limit=50))
        self.assertEqual(called, [('q' * 600, 5)])
        self.assertEqual(len(result['data']['web'][0]['title']), 400)
        self.assertEqual(len(result['data']['web'][0]['description']), 600)
        self.assertNotIn('REMOVE_EXTRA', json.dumps(result))

    def test_private_connect_and_child_process_are_blocked(self):
        ns = guard_namespace(socket=SimpleNamespace(socketpair=None, socket=type('UnusedSocket', (), {})))
        for address in ('127.0.0.1', '10.0.0.1', '169.254.169.254', '::1', 'private.example'):
            with self.assertRaises(PermissionError):
                ns['audit']('socket.connect', (None, (address, 443)))
        with self.assertRaises(PermissionError):
            ns['audit']('subprocess.Popen', ('never-executed',))
        ns['audit']('socket.connect', (None, ('93.184.216.34', 443)))

    def test_preflight_blocks_even_public_connect(self):
        ns = guard_namespace(request={'preflight': True}, socket=SimpleNamespace(socketpair=None, socket=type('UnusedSocket', (), {})))
        with self.assertRaises(PermissionError):
            ns['audit']('socket.connect', (None, ('93.184.216.34', 443)))

    def test_only_exact_socketpair_frame_and_objects_get_exception(self):
        class FakeSocket:
            def getsockname(self):
                return ('127.0.0.1', 51234)
        ns = guard_namespace(request={'preflight': True}, FakeSocket=FakeSocket)
        exec('def synthetic_socketpair():\n    lsock = FakeSocket()\n    csock = FakeSocket()\n    audit("socket.connect", (csock, lsock.getsockname()))\n', ns)
        ns['socket'] = SimpleNamespace(socketpair=ns['synthetic_socketpair'], socket=FakeSocket)
        ns['synthetic_socketpair']()
        with self.assertRaises(PermissionError):
            ns['audit']('socket.connect', (FakeSocket(), ('127.0.0.1', 51234)))
        self.assertEqual(len(ns['blocked_events']), 1)

    def test_auth_and_outside_runtime_writes_fail_closed(self):
        ns = guard_namespace()
        ns['audit']('open', (str(ns['work'] / 'session.json'), 'w', os.O_WRONLY | os.O_CREAT))
        with self.assertRaises(PermissionError):
            ns['audit']('open', (str(ROOT / 'outside-synthetic-runtime.json'), 'w', os.O_WRONLY | os.O_CREAT))
        with self.assertRaises(PermissionError):
            ns['audit']('open', (str(ROOT / '.codex/auth.json'), 'r', os.O_RDONLY))
        with self.assertRaises(PermissionError):
            ns['audit']('os.rename', (str(ns['work'] / 'state'), str(ROOT / 'outside-state')))

    def test_native_environment_probe_is_explicitly_disabled(self):
        assignment = next(node for node in ast.walk(TREE) if isinstance(node, ast.Assign)
                          and any(isinstance(target, ast.Name) and target.id == 'safe_config' for target in node.targets))
        agent = next(value for key, value in zip(assignment.value.keys, assignment.value.values)
                     if isinstance(key, ast.Constant) and key.value == 'agent')
        self.assertIs(ast.literal_eval(agent)['environment_probe'], False)


class PublicSearchGuards(unittest.TestCase):
    def test_search_sanitizer_limits_utf8_total_and_removes_metadata(self):
        raw = json.dumps({'extra': 'PRIVATE_METADATA', 'data': {'web': [
            {'url': f'https://example.com/page-{i}', 'title': '\u4e2d' * 1000, 'description': '\u4e2d' * 1500,
             'metadata': 'PRIVATE_METADATA'} for i in range(12)]}})
        encoded = public.sanitize_search_result(raw)
        result = json.loads(encoded)
        self.assertLessEqual(len(encoded.encode('utf-8')), 8000)
        self.assertLessEqual(len(result['data']['web']), 5)
        self.assertTrue(all(set(row) == {'url', 'title', 'description'} for row in result['data']['web']))
        self.assertNotIn('PRIVATE_METADATA', encoded)

    def test_search_sanitizer_does_not_echo_oversized_or_raw_errors(self):
        for raw in ('X' * (public.MAX_RESPONSE_BYTES + 1), '{malformed PRIVATE_PROVIDER_DETAIL',
                    json.dumps({'error': 'PRIVATE_PROVIDER_DETAIL'})):
            encoded = public.sanitize_search_result(raw)
            self.assertIn('error', json.loads(encoded))
            self.assertLess(len(encoded), 300)
            self.assertNotIn('PRIVATE_PROVIDER_DETAIL', encoded)

    def test_search_preserves_query_and_does_not_follow_or_cite_results(self):
        fetched = []
        def fetch(url):
            fetched.append(url)
            return 200, {}, b'<a class="result-link" href="https://example.com/">Synthetic company</a>'
        with patch.object(public, '_assert_public_host'), patch.object(public, '_decoded_fetch', fetch):
            result = json.loads(public.search_public('synthetic company Arizona'))
        self.assertEqual(len(fetched), 1)
        self.assertIn('?q=synthetic+company+Arizona', fetched[0])
        self.assertIn('Search result only', result['data']['web'][0]['description'])

    def test_search_challenge_is_not_returned_as_evidence(self):
        with patch.object(public, '_assert_public_host'), patch.object(public, '_decoded_fetch', return_value=(200, {}, b'Verify you are human')):
            result = json.loads(public.search_public('synthetic company'))
        self.assertIn('error', result)
        self.assertNotIn('data', result)


if __name__ == '__main__':
    unittest.main(verbosity=2)
