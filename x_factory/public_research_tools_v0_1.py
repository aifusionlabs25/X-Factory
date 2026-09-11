"""Key-free public search and guarded direct reads for the Factory researcher.

No third-party extraction proxy, login, cookies, challenge bypass, or package
installation. Search results are leads; only successful page reads are evidence.
"""
from __future__ import annotations

import asyncio
import json
import socket
from html.parser import HTMLParser
from urllib.parse import parse_qs, quote_plus, urljoin, urlsplit

from x_factory.website_ingestion_v0_1 import _canonical_url, _origin, _fetch_page, _default_fetch, _decode_http_response, _ReadablePage, _assert_public_host, MAX_RESPONSE_BYTES


def _decoded_fetch(url):
    return _decode_http_response(*_default_fetch(url))


def sanitize_search_result(raw):
    """Search is bounded discovery metadata, never accepted page evidence."""
    try:
        if isinstance(raw, str) and len(raw) > MAX_RESPONSE_BYTES:
            raise ValueError('Search payload too large')
        data = json.loads(raw) if isinstance(raw, str) else raw
        rows = data.get('data', {}).get('web', [])
        results = []
        for row in rows[:5]:
            if not isinstance(row, dict):
                continue
            url = _canonical_url(row.get('url', ''))
            if len(url) > 2048:
                continue
            result = {'url': url, 'title': str(row.get('title', ''))[:400],
                      'description': str(row.get('description', ''))[:600]}
            if len(json.dumps(results + [result], ensure_ascii=False).encode('utf-8')) > 7800:
                break
            results.append(result)
        if results:
            return json.dumps({'success': True, 'data': {'web': results}, 'notice': 'Search leads only. Open each source before citing.'}, ensure_ascii=False)
    except (ValueError, TypeError, AttributeError):
        pass
    return json.dumps({'error': 'Search is unavailable or returned no readable results. Use a company website or report this limitation. Do not bypass challenges.'})


class _SearchLinks(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.current = None
        self.links = []

    def handle_starttag(self, tag, attrs):
        data = dict(attrs)
        if tag == 'a' and ('result-link' in data.get('class', '') or 'result__a' in data.get('class', '')):
            self.current = {'url': data.get('href', ''), 'title': ''}

    def handle_data(self, data):
        if self.current is not None:
            self.current['title'] += data

    def handle_endtag(self, tag):
        if tag == 'a' and self.current is not None:
            self.links.append(self.current)
            self.current = None


def search_public(query, limit=5):
    if not isinstance(query, str) or not 3 <= len(query.strip()) <= 600:
        return json.dumps({'error': 'Use a short public research query.'})
    url = 'https://lite.duckduckgo.com/lite/?q=' + quote_plus(query)
    try:
        # The company importer intentionally removes query strings. Search must
        # preserve this locally constructed q parameter, with no redirects.
        _assert_public_host(url, socket.getaddrinfo)
        status, headers, body = _decoded_fetch(url)
        if status != 200 or len(body) > MAX_RESPONSE_BYTES:
            raise ValueError('Search is unavailable')
        parser = _SearchLinks()
        decoded = body.decode('utf-8', errors='replace')
        if any(term in decoded.lower() for term in ('verify you are human', 'access denied', 'checking your browser', 'enable javascript and cookies', 'anomaly.js', 'bots use duckduckgo')):
            raise ValueError('Access challenge')
        parser.feed(decoded)
        results = []
        for row in parser.links:
            candidate = urljoin(url, row['url'])
            parsed = urlsplit(candidate)
            if parsed.hostname and parsed.hostname.endswith('duckduckgo.com'):
                candidate = parse_qs(parsed.query).get('uddg', [''])[0]
            if not candidate.startswith(('https://', 'http://')):
                continue
            try:
                candidate = _canonical_url(candidate)
            except ValueError:
                continue
            results.append({'url': candidate[:2048], 'title': row['title'].strip()[:400], 'description': 'Search result only; open this page before citing it.'})
            if len(results) >= min(int(limit), 5):
                break
        if not results:
            return json.dumps({'error': 'Public search returned no readable results or an access challenge. Do not bypass it; use an owner-provided website or report the limitation.'})
        return json.dumps({'success': True, 'data': {'web': results}, 'provider': 'DuckDuckGo public search'}, ensure_ascii=False)
    except Exception:
        return json.dumps({'error': 'Public search could not be reached. Use an owner-provided website or report the limitation.'})


async def extract_public(urls, format=None, char_limit=16000):
    def fetch_one(raw):
        try:
            url = _canonical_url(raw)
            final, media, body, _ = _fetch_page(url, origin=_origin(url), resolver=socket.getaddrinfo, fetcher=_decoded_fetch)
            decoded = body.decode('utf-8', errors='replace')
            if media == 'text/html':
                parser = _ReadablePage()
                parser.feed(decoded)
                title, content, links = parser.result()
            else:
                title, content, links = urlsplit(final).hostname, decoded, []
            if any(term in content.lower()[:1500] for term in ('verify you are human', 'access denied', 'checking your browser', 'enable javascript and cookies')):
                raise ValueError('Access challenge')
            same_site = []
            for link in links:
                try:
                    candidate = urljoin(final, link)
                    if _origin(candidate) == _origin(final):
                        same_site.append(candidate)
                except ValueError:
                    continue
                if len(same_site) == 12:
                    break
            return {'url': final, 'title': title or urlsplit(final).hostname, 'content': content[:min(int(char_limit or 16000), 16000)], 'same_site_links': same_site}
        except Exception:
            return {'url': str(raw)[:2048], 'error': 'This public page could not be read safely. No content was accepted.'}
    results = await asyncio.gather(*(asyncio.to_thread(fetch_one, url) for url in urls[:4]))
    return json.dumps({'results': results, 'provider': 'Factory guarded direct page reading'}, ensure_ascii=False)
