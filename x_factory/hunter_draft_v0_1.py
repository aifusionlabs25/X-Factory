"""Single-prospect, owner-reviewed draft bridge. Never commissions or approves KB.

Only one hash-pinned local run is allowlisted in v0.1. No browser-supplied file
paths, URLs, code, catalogs, approval claims, or runtime commands are accepted.
The only write is an exclusive review receipt AFTER the owner's explicit action.
"""
from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from datetime import date, datetime, timezone
from pathlib import Path

from jsonschema import Draft202012Validator
from x_factory.chassis_depot_v0_1 import get_chassis
from x_factory.hunter_contracts.validate_v04 import validate_run
from x_factory.hunter_contracts.factory_brief import validate_run_factory_briefs, is_public_url
from x_factory.mission_control_factory_v0_1 import ROOT, SECRET_LIKE, PATH_LIKE, split_list

SOURCE_ID = 'hunter-checkpoint-20260828'
SOURCE_PATH = Path('C:/Users/AI Fusion Labs/Documents/Codex/2026-08-25/re/outputs/hunter-audit-v0.7.1-2026-08-28/prospects.json')
SOURCE_SHA256 = '00263873dffc429fed208d922475b82e78363f8e75acced7438c555daa07621e'
REVIEW_ROOT = ROOT / 'drafts/hunter'
MAX_OBSERVATION_AGE_DAYS = 7
CHASSIS_ID = 'operational-qa-concierge'
BLOCKED = {'millers-restoration-oh': 'HOLD: the August 28 recheck timed out; a later extraction returned a Robot Challenge Screen, not company evidence. The August 25 record has NOT been refreshed.'}
NOTICE = ('Historical research observed August 25, revised August 28—not a fresh hunt. '
          'Live sourcing and rendered qualification remain separate gates. '
          'Hunter recommendations do not prove current Factory capabilities or approved company facts.')


class HunterDraftError(ValueError):
    pass


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()


def exact_keys(value, expected):
    if not isinstance(value, dict) or set(value) != set(expected):
        raise HunterDraftError('Unexpected or missing request fields; review stopped safely.')


def source_run():
    try:
        raw = SOURCE_PATH.read_bytes()
        if len(raw) > 1024 * 1024 or hashlib.sha256(raw).hexdigest() != SOURCE_SHA256:
            raise HunterDraftError('Hunter source has changed. A new reviewed source binding is required.')
        run = json.loads(raw)
        errors = validate_run(run) + validate_run_factory_briefs(run)
        if run.get('authority') != 'advisory_only_no_outreach' or run.get('outreach_performed') is not False:
            errors.append('Source authority is not advisory-only.')
        if errors:
            raise HunterDraftError('Hunter saved-run validation failed: ' + '; '.join(errors[:3]))
        return run
    except (OSError, json.JSONDecodeError) as error:
        raise HunterDraftError('The allowlisted Hunter checkpoint is unavailable; no draft was imported.') from error


def blockers(prospect, today=None):
    today = today or date.today()
    reasons = []
    if prospect['prospect_id'] in BLOCKED:
        reasons.append(BLOCKED[prospect['prospect_id']])
    if prospect.get('stage') != 'qualified' or prospect.get('verification_status') != 'verified_public':
        reasons.append('Candidate is not qualified in the bound historical run.')
    if prospect.get('overall_score', 0) < 75 or prospect.get('rob_demo_recommendation') == 'NO':
        reasons.append('Candidate is below this draft-import threshold or marked NO.')
    audit = prospect.get('browser_audit', {})
    if audit.get('rendered_page_checked') is not True or audit.get('submission_performed') is not False:
        reasons.append('Read-only rendered-source evidence is missing.')
    dates = [s.get('observed_on', '') for s in prospect['public_sources']] + [audit.get('checked_on', '')]
    for stamp in dates:
        try:
            age = (today - date.fromisoformat(stamp)).days
            if age < 0 or age > MAX_OBSERVATION_AGE_DAYS:
                reasons.append('Research is outside the seven-day review window. Reverification is required; importing cannot renew its date.')
                break
        except (ValueError, TypeError):
            reasons.append('A source observation date is missing or invalid.')
            break
    for source in prospect['public_sources']:
        if not is_public_url(source.get('url')):
            reasons.append('A source URL is not public HTTP(S).')
    return reasons


def receipt_path(prospect_id):
    # Identity derives only from a matched pinned record, never an input path.
    key = hashlib.sha256((SOURCE_SHA256 + ':' + prospect_id).encode()).hexdigest()
    return REVIEW_ROOT / (key + '.json')


def list_prospects():
    run = source_run()
    return {'source_id': SOURCE_ID, 'source_run_sha256': SOURCE_SHA256, 'notice': NOTICE,
            'live_sourcing_certified': False, 'max_observation_age_days': MAX_OBSERVATION_AGE_DAYS,
            'prospects': [{'prospect_id': p['prospect_id'], 'company_name': p['company_name'],
                          'score': p['overall_score'], 'blockers': blockers(p),
                          'already_reviewed': receipt_path(p['prospect_id']).exists()}
                         for p in run['qualified_prospects']]}


def review_prospect(request):
    exact_keys(request, ['source_id', 'prospect_id'])
    if request['source_id'] != SOURCE_ID:
        raise HunterDraftError('Only the reviewed Hunter checkpoint is supported.')
    run = source_run()
    matches = [p for p in run['qualified_prospects'] if p['prospect_id'] == request['prospect_id']]
    if len(matches) != 1:
        raise HunterDraftError('Select exactly one prospect from this checkpoint.')
    prospect = matches[0]
    brief = prospect['factory_intake_brief']
    chassis = get_chassis(CHASSIS_ID)
    snapshot = {'source_id': SOURCE_ID, 'source_run_sha256': SOURCE_SHA256,
                'prospect_id': prospect['prospect_id'], 'research_status': 'UNAPPROVED_RESEARCH',
                'original_prospect': deepcopy(prospect)}
    fields = {'purpose': brief['system_prompt_brief'], 'x_agent_name': '',
              'client_name': prospect['company_name'], 'target_users': brief['who_will_use_this'],
              'personality': brief['personality_and_communication_style'],
              'additional_requirements': '; '.join(brief['additional_requirements']),
              'additional_boundaries': '; '.join(brief['additional_boundaries']), 'presence_mode': ''}
    return {'snapshot': snapshot, 'snapshot_sha256': digest(snapshot), 'fields': fields,
            'chassis': chassis, 'suggested_appearance': brief['appearance_recommendation'],
            'blockers': blockers(prospect), 'already_reviewed': receipt_path(prospect['prospect_id']).exists(),
            'notice': NOTICE}


def accept_draft(request):
    schema = json.loads((ROOT / 'contracts/hunter_draft_review.v0.1.schema.json').read_text())
    errors = list(Draft202012Validator(schema).iter_errors(request))
    if errors:
        raise HunterDraftError('Review is incomplete or has unsupported fields: ' + errors[0].message)
    review = review_prospect({key: request[key] for key in ('source_id', 'prospect_id')})
    if review['blockers']:
        raise HunterDraftError(' '.join(review['blockers']))
    if request['snapshot_sha256'] != review['snapshot_sha256'] or request['chassis_sha256'] != review['chassis']['chassis_sha256']:
        raise HunterDraftError('Research or role changed during review. Reopen it before continuing.')
    fields = {key: value.strip() for key, value in request['fields'].items()}
    normalized_request = {**request, 'fields': fields}
    if list(Draft202012Validator(schema).iter_errors(normalized_request)):
        raise HunterDraftError('Fields cannot be blank or shorter than their minimum length.')
    if SECRET_LIKE.search(str(fields)) or PATH_LIKE.search(str(fields)):
        raise HunterDraftError('Remove credentials or local paths from the draft.')
    # Validate effective downstream limits, including the unchangeable chassis rules.
    for field, target in [('additional_requirements', 'must_accomplish'), ('additional_boundaries', 'never_do')]:
        combined = '; '.join([*review['chassis']['invariants'][target], *split_list(fields[field])])
        if len(combined) > 3000:
            raise HunterDraftError(f'{field} is too long after including the Factory baseline rules. Shorten your additions.')
    original_limits = review['snapshot']['original_prospect']['factory_intake_brief']['additional_boundaries']
    if not set(x.casefold() for x in split_list('; '.join(original_limits))).issubset(set(x.casefold() for x in split_list(fields['additional_boundaries']))):
        raise HunterDraftError('Keep all proposed exclusions in this first draft import; you may add boundaries.')
    record = {'schema_version': 'hunter.owner-reviewed-draft.v0.1', 'status': 'OWNER_REVIEWED_DRAFT_ONLY',
              'reviewed_at': datetime.now(timezone.utc).isoformat(), 'snapshot': review['snapshot'],
              'snapshot_sha256': review['snapshot_sha256'], 'fields': fields,
              'owner_edits': {k: {'proposed': review['fields'][k], 'reviewed': v} for k, v in fields.items() if v != review['fields'][k]},
              'chassis_id': CHASSIS_ID, 'chassis_sha256': request['chassis_sha256'],
              'knowledge_approved': False, 'mission_created': False, 'provider_calls': 0, 'outreach_performed': False}
    record['record_sha256'] = digest(record)
    REVIEW_ROOT.mkdir(parents=True, exist_ok=True)
    target = receipt_path(request['prospect_id'])
    try:
        with target.open('x', encoding='utf-8') as handle:
            json.dump(record, handle, ensure_ascii=False, indent=2)
    except FileExistsError as error:
        raise HunterDraftError('This prospect already has a reviewed draft. Nothing was overwritten or applied again.') from error
    return {'status': record['status'], 'review_id': target.stem,
            'source_id': SOURCE_ID, 'prospect_id': request['prospect_id'],
            'fields': fields, 'chassis': review['chassis'], 'mission_created': False,
            'knowledge_approved': False, 'provider_calls': 0, 'outreach_performed': False}


def reopen_draft(request):
    """Explicit recovery after a refresh; never overwrite or implicitly reapprove."""
    review = review_prospect(request)
    if review['blockers']:
        raise HunterDraftError(' '.join(review['blockers']))
    target = receipt_path(request['prospect_id'])
    try:
        record = json.loads(target.read_text(encoding='utf-8'))
    except (OSError, ValueError) as error:
        raise HunterDraftError('No readable saved draft exists for this prospect.') from error
    if (record.get('record_sha256') != digest({k: v for k, v in record.items() if k != 'record_sha256'}) or
        record.get('snapshot_sha256') != review['snapshot_sha256'] or
        digest(record.get('snapshot')) != review['snapshot_sha256'] or
        record.get('chassis_sha256') != review['chassis']['chassis_sha256'] or
        record.get('status') != 'OWNER_REVIEWED_DRAFT_ONLY'):
        raise HunterDraftError('Saved research or role binding changed; reopening is blocked.')
    schema = json.loads((ROOT / 'contracts/hunter_draft_review.v0.1.schema.json').read_text())
    check = {**request, 'fields': record.get('fields'), 'snapshot_sha256': record['snapshot_sha256'],
             'chassis_sha256': record['chassis_sha256'], 'owner_confirmed': True}
    if list(Draft202012Validator(schema).iter_errors(check)):
        raise HunterDraftError('Saved draft fields no longer validate.')
    return {'status': 'OWNER_REVIEWED_DRAFT_ONLY', 'review_id': target.stem, 'fields': record['fields'],
            'source_id': SOURCE_ID, 'prospect_id': request['prospect_id'],
            'chassis': review['chassis'], 'mission_created': False, 'knowledge_approved': False,
            'provider_calls': 0, 'outreach_performed': False}
