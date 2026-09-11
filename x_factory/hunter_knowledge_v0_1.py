"""Explicit Hunter -> OMNARA preparation. Research never enters source fact files.

Plan is read-only. Prepare fetches bounded public company pages and authorizes
their processing into UNAPPROVED proposals, not runtime facts or a mission.
"""
from __future__ import annotations

import json
import threading
from datetime import date

from x_factory import hunter_draft_v0_1 as hunter
from x_factory import knowledge_loading_v0_1 as loading
from x_factory.knowledge_compiler_v0_1 import compile_package, get_compilation
from x_factory.mission_control_factory_v0_1 import ROOT, write_new
from x_factory.website_ingestion_v0_1 import capture_website_knowledge, _canonical_url, _origin, MAX_PAGES

PREPARATION_ROOT = ROOT / 'drafts/hunter-knowledge'
_PREPARE_LOCK = threading.Lock()
SECTIONS = {
    'Company overview': {'BRAND_REFERENCE', 'GENERAL_REFERENCE'},
    'Services': {'SERVICE_OR_CAPABILITY'},
    'Service area and contact': {'LOCATION_OR_CONTACT'},
    'FAQs': {'FAQ'},
    'Policies and hours': {'BUSINESS_POLICY', 'HOURS_OR_AVAILABILITY'},
    'Intake and escalation instructions': set(),
}


def knowledge_plan(request):
    saved = hunter.reopen_draft(request)  # receipt/source/schema/HOLD/age validation
    review = hunter.review_prospect(request)
    prospect = review['snapshot']['original_prospect']
    website = _canonical_url(prospect['website'])
    sources = []
    excluded = []
    observed = {s['url']: s['observed_on'] for s in prospect['public_sources']}
    for raw in dict.fromkeys([prospect['website'], *observed]):
        url = _canonical_url(raw)
        if _origin(url) != _origin(website):
            excluded.append({'url': url, 'reason': 'Outside the company website; not fetched.'})
        elif url not in {s['url'] for s in sources}:
            if len(sources) < MAX_PAGES:
                sources.append({'url': url, 'observed_on': observed.get(raw), 'status': 'RESEARCH_LINK_NOT_APPROVED_FACT'})
            else:
                excluded.append({'url': url, 'reason': 'Outside the six-page capture limit.'})
    plan = {
        'schema_version': 'hunter.knowledge-preparation.v0.1',
        'source_id': request['source_id'], 'prospect_id': request['prospect_id'],
        'review_id': saved['review_id'], 'snapshot_sha256': review['snapshot_sha256'],
        'fields': saved['fields'], 'day': date.today().isoformat(),
        'research_direction': prospect['factory_intake_brief']['knowledge_direction_only'],
        'sources': sources, 'excluded_sources': excluded,
        'max_pages': MAX_PAGES, 'specialist': 'OMNARA',
        'method': 'LOCAL_SOURCE_EXTRACTION_PENDING_OWNER_REVIEW',
        'knowledge_approved': False, 'mission_created': False, 'provider_calls': 0,
        'notice': 'Source links and the reviewed job guide preparation. Hunter claims are not facts. No live model is used. Only your later fact review approves knowledge.',
    }
    plan['plan_sha256'] = hunter.digest(plan)
    return plan


def draft_outline(compilation):
    """Pointers to exact proposals, not invented facts or claims of completeness."""
    result = []
    for title, categories in SECTIONS.items():
        ids = [e['entry_id'] for e in compilation['entries'] if e.get('relevance', {}).get('category') in categories]
        result.append({'title': title, 'entry_ids': ids,
                       'status': 'DRAFT_FACTS_TO_REVIEW' if ids else 'NEEDS_OWNER_INFORMATION'})
    return result


def assert_knowledge_identity(package_id, client_name, purpose):
    """A later build cannot silently relabel Hunter-sourced facts for another job."""
    path = loading._package_root(package_id) / 'hunter-preparation-binding.v0.1.json'
    if not path.exists():
        return  # Existing manual/website packages retain their existing contract.
    record = json.loads(path.read_text(encoding='utf-8'))
    if (record.get('receipt_sha256') != hunter.digest({k: v for k, v in record.items() if k != 'receipt_sha256'}) or
            record.get('package_id') != package_id or
            record.get('manifest_sha256') != loading.package_status(package_id)['manifest_sha256']):
        raise loading.KnowledgeLoadingError('Hunter knowledge source binding changed; build blocked.')
    normalize = lambda text: ' '.join(str(text).split())
    fields = record['plan']['fields']
    if normalize(client_name) != normalize(fields['client_name']) or normalize(purpose) != normalize(fields['purpose']):
        raise loading.KnowledgeLoadingError('This Hunter Knowledge Bank belongs to a different company or reviewed job. Restore that draft or prepare and review a new source package for the changed brief.')


def prepare_knowledge(request, *, capture=None):
    hunter.exact_keys(request, ['source_id', 'prospect_id', 'plan_sha256', 'owner_requested'])
    if request['owner_requested'] is not True:
        raise hunter.HunterDraftError('Preparing website knowledge requires your separate explicit request.')
    if not _PREPARE_LOCK.acquire(blocking=False):
        raise hunter.HunterDraftError('A preparation is already running. Wait for its result before starting another.')
    try:
        plan = knowledge_plan({key: request[key] for key in ('source_id', 'prospect_id')})
        if request['plan_sha256'] != plan['plan_sha256']:
            raise hunter.HunterDraftError('The reviewed job, source or date changed. Reopen the draft before preparation.')
        target = PREPARATION_ROOT / (plan['plan_sha256'] + '.json')
        if target.exists():
            receipt = json.loads(target.read_text(encoding='utf-8'))
            if receipt.get('receipt_sha256') != hunter.digest({k: v for k, v in receipt.items() if k != 'receipt_sha256'}) or receipt.get('plan') != plan:
                raise hunter.HunterDraftError('Knowledge preparation receipt changed; reuse blocked.')
            package = loading.package_status(receipt['package_id'])
            compilation = get_compilation(package['package_id'], receipt['compilation_id'])
            if package['manifest_sha256'] != receipt['manifest_sha256'] or compilation['compilation_sha256'] != receipt['compilation_sha256']:
                raise hunter.HunterDraftError('Prepared source or compilation changed; reuse blocked.')
        else:
            package = (capture or capture_website_knowledge)(
                {'url': plan['sources'][0]['url'], 'label': (plan['fields']['client_name'][:85] + ' · Hunter source draft')},
                seed_urls=[s['url'] for s in plan['sources']])
            # This records authorization to PROCESS the requested source files.
            # It cannot approve any compiled fact; no review_compilation call here.
            loading.approve_knowledge_package(package['package_id'])
            compilation = compile_package(package['package_id'])
            receipt = {'schema_version': 'hunter.knowledge-preparation-receipt.v0.1',
                       'plan': plan, 'package_id': package['package_id'],
                       'manifest_sha256': package['manifest_sha256'],
                       'compilation_id': compilation['compilation_id'],
                       'compilation_sha256': compilation['compilation_sha256'],
                       'knowledge_approved': False, 'mission_created': False, 'provider_calls': 0}
            receipt['receipt_sha256'] = hunter.digest(receipt)
            write_new(loading._package_root(package['package_id']) / 'hunter-preparation-binding.v0.1.json', receipt)
            PREPARATION_ROOT.mkdir(parents=True, exist_ok=True)
            write_new(target, receipt)  # Research stays outside knowledge-package/files.
        return {'plan': plan, 'package': package, 'compilation': compilation,
                'outline': draft_outline(compilation), 'knowledge_approved': False,
                'mission_created': False, 'provider_calls': 0,
                'next_step': 'Review proposed facts. Approved Knowledge Bank files are produced only by a separate Build.'}
    finally:
        _PREPARE_LOCK.release()
