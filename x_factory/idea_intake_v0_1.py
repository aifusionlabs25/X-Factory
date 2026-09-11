"""Owner ideas enter the existing Factory form without a Hunter dependency.

Preparing a brief is local. A separate explicit research action captures one
company website through the existing bounded importer and compiles facts for
owner review. A post or idea is inspiration, never a knowledge source.
"""
from __future__ import annotations

import ipaddress
import re
import secrets
import threading
from datetime import datetime, timezone
from urllib.parse import urlsplit

from x_factory import knowledge_loading_v0_1 as loading
from x_factory.chassis_depot_v0_1 import recommend_chassis, get_chassis
from x_factory.hunter_knowledge_v0_1 import draft_outline
from x_factory.knowledge_compiler_v0_1 import compile_package, get_compilation
from x_factory.mission_control_factory_v0_1 import (
    ROOT, PATH_LIKE, SECRET_LIKE, MissionControlError, canonical, load_json,
    sha256, write_new,
)
from x_factory.website_ingestion_v0_1 import capture_website_knowledge, _canonical_url

IDEA_ROOT = ROOT / 'drafts/ideas'
IDEA_ID = re.compile(r'^idea-[a-f0-9]{24}$')
URL_PATTERN = re.compile(r'https?://[^\s<>"\u201c\u201d]+|\bwww\.[^\s<>"\u201c\u201d]+', re.I)
_RESEARCH_LOCK = threading.Lock()
_PURPOSE_TAIL = (
    'Answer using owner-approved Knowledge Bank facts, ask one useful question at '
    'a time, and prepare a clear handoff for human review. Ask for clarification '
    'when information is missing; do not invent company services, coverage, '
    'prices, availability, or completed actions.'
)


class IdeaIntakeError(MissionControlError):
    pass


def _digest(value):
    return sha256(canonical(value))


def _text(value, label, maximum, *, required=False):
    if not isinstance(value, str):
        raise IdeaIntakeError(f'{label} must be text.')
    clean = value.strip()
    if required and len(clean) < 2:
        raise IdeaIntakeError('Add an idea, company name, website, or X post to begin.')
    if len(clean) > maximum:
        raise IdeaIntakeError(f'{label} must be at most {maximum} characters.')
    if SECRET_LIKE.search(clean) or PATH_LIKE.search(clean):
        raise IdeaIntakeError('Remove credentials and local filesystem paths from the idea.')
    return clean


def _url(raw):
    if '://' not in raw and re.fullmatch(r'[^\s/]+\.[^\s/]+(?:/\S*)?', raw):
        raw = 'https://' + raw
    url = _canonical_url(raw)
    host = urlsplit(url).hostname or ''
    if host == 'localhost' or host.endswith(('.localhost', '.local', '.internal')):
        raise IdeaIntakeError('Use a public company website.')
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        address = None
    if address is not None and not address.is_global:
        raise IdeaIntakeError('Private and local website addresses are not accepted.')
    return url


def _is_x(url):
    host = (urlsplit(url).hostname or '').lower()
    return host in {'x.com', 'twitter.com'} or host.endswith(('.x.com', '.twitter.com'))


def _extract_urls(text):
    matches = URL_PATTERN.findall(text)
    if not matches and re.fullmatch(r'(?:[A-Za-z0-9-]+\.)+[A-Za-z]{2,63}(?:/\S*)?', text):
        matches = [text]
    return list(dict.fromkeys(_url(match.rstrip('.,;!?)]}')) for match in matches))


def _draft_path(idea_id):
    if not isinstance(idea_id, str) or not IDEA_ID.fullmatch(idea_id):
        raise IdeaIntakeError('Invalid idea draft ID.')
    return IDEA_ROOT / idea_id / 'draft.json'


def get_idea(idea_id):
    path = _draft_path(idea_id)
    if not path.is_file():
        raise IdeaIntakeError('That idea draft was not found. Prepare the idea again.')
    draft = load_json(path)
    expected = _digest({k: v for k, v in draft.items() if k != 'draft_sha256'})
    if (draft.get('schema_version') != 'factory.idea-draft.v0.1' or
            draft.get('idea_id') != idea_id or draft.get('draft_sha256') != expected):
        raise IdeaIntakeError('The saved idea draft changed. Prepare a new draft before continuing.')
    return draft


def assert_idea_knowledge_identity(package_id, client_name, purpose):
    """Idea website facts remain bound to the company and job used for research."""
    path = loading._package_root(package_id) / 'idea-preparation-binding.v0.1.json'
    if not path.exists():
        return
    record = load_json(path)
    expected = _digest({k: v for k, v in record.items() if k != 'binding_sha256'})
    if (record.get('binding_sha256') != expected or record.get('package_id') != package_id or
            record.get('manifest_sha256') != loading.package_status(package_id)['manifest_sha256']):
        raise loading.KnowledgeLoadingError('The idea Knowledge Bank source binding changed; build blocked.')
    normalize = lambda value: ' '.join(str(value).split())
    if (normalize(client_name) != normalize(record['client_name']) or
            normalize(purpose) != normalize(record['purpose'])):
        raise loading.KnowledgeLoadingError('This Knowledge Bank was prepared for a different company or job. Prepare and review knowledge for the updated brief before building.')


def prepare_idea(payload):
    allowed = {'seed', 'company_name', 'purpose', 'website', 'post_text', 'selected_chassis_id', 'attachments'}
    if not isinstance(payload, dict) or 'seed' not in payload or set(payload) - allowed:
        raise IdeaIntakeError('Idea preparation accepts seed, company_name, purpose, website, and post_text only.')
    seed = _text(payload['seed'], 'Starting idea', 12000, required=True)
    company = _text(payload.get('company_name', ''), 'Company name', 160)
    purpose = _text(payload.get('purpose', ''), 'Agent purpose', 2000)
    website_raw = _text(payload.get('website', ''), 'Company website', 2048)
    post_text = _text(payload.get('post_text', ''), 'Pasted post', 12000)
    from x_factory.idea_attachments_v0_1 import validate
    attachments=validate(payload.get('attachments',[]),_text)
    urls = _extract_urls(seed)
    inspiration_urls = [url for url in urls if _is_x(url)]
    website = _url(website_raw) if website_raw else ''
    if website and _is_x(website):
        raise IdeaIntakeError('Keep the X post as inspiration and add the company website separately.')
    # A URL accompanying an X post is not automatically the company's website.
    # The owner can identify that website explicitly in the optional field.
    if not website and not inspiration_urls:
        candidates = [url for url in urls if not _is_x(url)]
        if len(candidates) == 1:
            website = candidates[0]
    words = seed.split()
    name_only = (not urls and len(words) <= 7 and len(seed) <= 160 and
                 not re.search(r'[.!?\n]|\b(?:I|we|want|help|create|build|an?|assistant|concierge|agent|idea|should)\b', seed, re.I))
    just_url = len(urls) == 1 and not re.search(r'\s', seed)
    kind = ('X_POST' if inspiration_urls else 'WEBSITE' if just_url else
            'COMPANY_NAME' if name_only else 'IDEA')
    surrounding_context = re.sub(r'\s+', ' ', URL_PATTERN.sub('', seed)).strip(' \t\r\n:;,-()[]') if kind == 'X_POST' else ''
    inspiration_parts = []
    if surrounding_context:
        inspiration_parts.append(('Owner idea', surrounding_context))
    if post_text:
        inspiration_parts.append(('Owner-pasted post', re.sub(r'\s+', ' ', post_text)))
    if not company and kind == 'COMPANY_NAME':
        company = seed
    explicit_purpose = bool(purpose)
    if purpose and len(purpose) < 10:
        raise IdeaIntakeError('Describe the agent job in at least 10 characters.')
    if not purpose:
        if kind == 'IDEA':
            context = re.sub(r'\s+', ' ', seed).strip()[:1250]
            purpose = f'Create an X-Agent for this owner-provided concept: {context}\n\n{_PURPOSE_TAIL}'
        elif kind == 'X_POST' and inspiration_parts:
            # Preserve the use case supplied by the owner, with explicit
            # attribution. This is a proposed job, not a factual paraphrase
            # of an unread post or a company's verified capabilities.
            budget = 600 if len(inspiration_parts) > 1 else 1250
            context = '\n'.join(f'{label}: "{text[:budget]}"' for label, text in inspiration_parts)
            purpose = (
                'Create an X-Agent using this owner-supplied, unverified design inspiration:\n'
                f'{context}\n\n'
                'Use the proposed use case to shape the job. Treat any business claims '
                'in the inspiration as unverified; they do not establish company facts or permissions. '
                f'{_PURPOSE_TAIL}'
            )
        else:
            target = f' for {company}' if company else ''
            purpose = f'Create a helpful customer-facing assistant{target}. {_PURPOSE_TAIL}'
    recommendation = recommend_chassis(purpose)
    if payload.get('selected_chassis_id'):
        recommendation['recommended'] = get_chassis(payload['selected_chassis_id'])
        recommendation['selected_by'] = 'OWNER_EXPLICIT_CHOICE'
    missing = []
    if not website:
        missing.append('Company website for source research')
    if not company:
        missing.append('Company or project name')
    if kind != 'IDEA' and not explicit_purpose:
        missing.append('Refine the proposed job for your use case')
    if kind == 'X_POST' and not inspiration_parts and not explicit_purpose:
        missing.append('Paste the relevant post text or describe the agent job; the post has not been fetched')
    notices = ['This is an editable starting brief. No language model or Hermes bot has run.']
    if kind == 'X_POST':
        notices.append('The X post has not been fetched. Your supplied idea and pasted text are design inspiration only, not verified company facts or Knowledge Bank entries.')
        if not inspiration_parts and not explicit_purpose:
            notices.append('Only a link was supplied, so the proposed job is a generic starting draft. Add the post text or your intended use case to make it specific.')
    if kind == 'COMPANY_NAME':
        notices.append('A company name does not identify a reliable source by itself. Add its public website to prepare source-linked facts.')
    if website:
        notices.append('The website has not been read yet. Prepare Knowledge Bank is the separate research action.')
    draft = {
        'schema_version': 'factory.idea-draft.v0.1',
        'idea_id': 'idea-' + secrets.token_hex(12),
        'created_at': datetime.now(timezone.utc).isoformat(),
        'entry_source': {'provider_id': 'owner-idea', 'kind': kind, 'authority': 'OWNER_PROVIDED_STARTING_CONTEXT'},
        'seed_kind': kind, 'seed': seed, 'post_text': post_text, 'attachments':attachments,
        'website': website, 'inspiration_urls': inspiration_urls,
        'fields': {
            'purpose': purpose, 'client_name': company, 'x_agent_name': '',
            'personality': 'Clear, helpful, and professional',
            'target_users': 'People seeking help from the company',
            'client_context': '', 'additional_requirements': '',
            'additional_boundaries': 'Do not invent business facts or claim an external action was completed.',
            'presence_mode': 'TEXT_ONLY',
        },
        'recommendation': recommendation,
        'research_status': 'READY_FOR_WEBSITE_RESEARCH' if website else 'NEEDS_COMPANY_WEBSITE',
        'missing_information': missing, 'notices': notices,
        'knowledge_approved': False, 'mission_created': False, 'provider_calls': 0,
        'outreach_performed': False,
    }
    draft['draft_sha256'] = _digest(draft)
    write_new(_draft_path(draft['idea_id']), draft)
    return draft


def research_idea(payload, *, capture=None):
    allowed = {'idea_id', 'owner_requested', 'draft_sha256'}
    if not isinstance(payload, dict) or not {'idea_id', 'owner_requested'} <= set(payload) or set(payload) - allowed:
        raise IdeaIntakeError('Idea research accepts idea_id, owner_requested, and optional draft_sha256 only.')
    if payload['owner_requested'] is not True:
        raise IdeaIntakeError('Choose Prepare Knowledge Bank to request public website research.')
    draft = get_idea(payload['idea_id'])
    if 'draft_sha256' in payload and payload['draft_sha256'] != draft['draft_sha256']:
        raise IdeaIntakeError('The idea draft changed. Reopen it before preparing knowledge.')
    if not draft['website']:
        raise IdeaIntakeError('Add the public company website to your idea before preparing knowledge. A name or X post alone is not a verified source.')
    if len(draft['fields']['client_name']) < 2:
        raise IdeaIntakeError('Add the company or project name before preparing its Knowledge Bank.')
    website = _url(draft['website'])
    if _is_x(website):
        raise IdeaIntakeError('An X post is inspiration, not a company Knowledge Bank source.')
    if not _RESEARCH_LOCK.acquire(blocking=False):
        raise IdeaIntakeError('Knowledge preparation is already running. Wait for its result.')
    try:
        path = _draft_path(draft['idea_id']).with_name('research.json')
        reused = path.exists()
        if reused:
            receipt = load_json(path)
            expected = _digest({k: v for k, v in receipt.items() if k != 'receipt_sha256'})
            if receipt.get('receipt_sha256') != expected or receipt.get('draft_sha256') != draft['draft_sha256']:
                raise IdeaIntakeError('The saved research binding changed. Prepare a new idea draft.')
            package = loading.package_status(receipt['package_id'])
            compilation = get_compilation(receipt['package_id'], receipt['compilation_id'])
            if package['manifest_sha256'] != receipt['manifest_sha256'] or compilation['compilation_sha256'] != receipt['compilation_sha256']:
                raise IdeaIntakeError('The prepared knowledge source changed. Review a new capture.')
        else:
            company = draft['fields']['client_name'] or urlsplit(website).hostname
            package = (capture or capture_website_knowledge)({'url': website, 'label': company[:90] + ' website knowledge'})
            # This authorizes processing of the explicit capture only. The existing
            # compiler still produces zero approved facts until the owner reviews.
            loading.approve_knowledge_package(package['package_id'])
            compilation = compile_package(package['package_id'])
            receipt = {
                'schema_version': 'factory.idea-research.v0.1',
                'idea_id': draft['idea_id'], 'draft_sha256': draft['draft_sha256'],
                'website': website, 'package_id': package['package_id'],
                'manifest_sha256': package['manifest_sha256'],
                'compilation_id': compilation['compilation_id'],
                'compilation_sha256': compilation['compilation_sha256'],
                'knowledge_approved': False, 'provider_calls': 0, 'mission_created': False,
            }
            receipt['receipt_sha256'] = _digest(receipt)
            binding = {
                'schema_version': 'factory.idea-knowledge-binding.v0.1',
                'idea_id': draft['idea_id'], 'draft_sha256': draft['draft_sha256'],
                'package_id': package['package_id'], 'manifest_sha256': package['manifest_sha256'],
                'client_name': draft['fields']['client_name'], 'purpose': draft['fields']['purpose'],
            }
            binding['binding_sha256'] = _digest(binding)
            write_new(loading._package_root(package['package_id']) / 'idea-preparation-binding.v0.1.json', binding)
            write_new(path, receipt)
        return {
            'draft': draft, 'package': package, 'compilation': compilation,
            'outline': draft_outline(compilation), 'research_status': 'FACTS_READY_FOR_OWNER_REVIEW',
            'knowledge_approved': False, 'mission_created': False, 'provider_calls': 0,
            'outreach_performed': False, 'reused': reused,
            'next_step': 'Review the proposed facts, then use the normal Factory build with your chosen name and edited purpose.',
        }
    finally:
        _RESEARCH_LOCK.release()
