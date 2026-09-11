"""Owner research-direction review. Company fact approval remains separate."""
from __future__ import annotations

from x_factory import idea_intake_v0_1 as idea
from x_factory import idea_research_v0_1 as research
from x_factory.chassis_depot_v0_1 import get_chassis
from x_factory.role_library_v0_1 import recommend_roles
from x_factory.mission_control_factory_v0_1 import canonical, sha256, write_new


def recommendation(purpose, result=None):
    roles = recommend_roles(purpose, result)
    selected = roles['recommended']
    return {'recommended': get_chassis(selected['chassis_id']) if selected else None,
            'alternatives': [get_chassis(row['role']['chassis_id']) for row in roles['ranked'] if not selected or row['role']['chassis_id'] != selected['chassis_id']],
            'fit_status': roles['fit_status'], 'role_recommendation': roles}


def job_view(job_id):
    job = research.get_job(job_id)
    if job.get('result'):
        job['recommendation'] = recommendation(job['result']['proposed_purpose'], job['result'])
    return job


def review_direction(idea_id, payload):
    required = {'owner_requested', 'job_id', 'result_sha256', 'draft_sha256', 'purpose', 'selected_chassis_id'}
    if not isinstance(payload, dict) or not required <= set(payload) or set(payload) - required - {'company_name', 'website'}:
        raise idea.IdeaIntakeError('Review the research direction, selected role, and company identity before continuing.')
    if payload['owner_requested'] is not True:
        raise idea.IdeaIntakeError('The research direction needs your review.')
    if any(not isinstance(payload.get(key, ''), str) for key in required - {'owner_requested'} | {'company_name', 'website'}):
        raise idea.IdeaIntakeError('Research review fields must be plain text.')
    original = idea.get_idea(idea_id)
    job = research.get_job(payload['job_id'])
    if (job['status'] != 'NEEDS_REVIEW' or job['idea_id'] != idea_id or job['draft_sha256'] != original['draft_sha256']
            or payload['draft_sha256'] != original['draft_sha256'] or payload['result_sha256'] != job.get('result_sha256')):
        raise idea.IdeaIntakeError('The research draft changed or is not ready for review. Reopen its current result.')
    result = job['result']
    company, website = payload.get('company_name', '').strip(), payload.get('website', '').strip()
    candidates = result['company_candidates']
    if result['identity_status'] == 'AMBIGUOUS' and (not company or not website):
        raise idea.IdeaIntakeError('More than one company matched. Confirm the company name and website yourself.')
    if result['identity_status'] == 'RESOLVED' and len(candidates) == 1:
        company = company or candidates[0]['name']
        website = website or candidates[0]['website'] or ''
    company = company or original['fields']['client_name']
    website = website or original['website']
    selected = get_chassis(payload['selected_chassis_id'])
    draft = idea.prepare_idea({'seed': original['seed'], 'post_text': original['post_text'], 'purpose': payload['purpose'],
                              'company_name': company, 'website': website, 'selected_chassis_id': selected['chassis_id']})
    receipt = {'schema_version': 'factory.research-direction-review.v0.1', 'original_idea_id': idea_id,
               'idea_id': draft['idea_id'], 'job_id': job['job_id'], 'result_sha256': job['result_sha256'],
               'draft_sha256': draft['draft_sha256'], 'selected_chassis_id': selected['chassis_id'],
               'authority': 'OWNER_REVIEWED_DIRECTION_ONLY', 'knowledge_approved': False, 'mission_created': False}
    receipt['receipt_sha256'] = sha256(canonical(receipt))
    write_new(idea._draft_path(draft['idea_id']).with_name('research-review.json'), receipt)
    return {'draft': draft, 'review': receipt}
