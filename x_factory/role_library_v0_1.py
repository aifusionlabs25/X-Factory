"""Distinct draft role recipes over the existing local Factory engine.

Recipes specify behavior and required evidence. They do not inherit the original
concierge's semantic review or claim new connectors/runtime capabilities.
"""
from __future__ import annotations

import re
from copy import deepcopy

from x_factory.mission_control_factory_v0_1 import ROOT, canonical, load_json, sha256

BASE_CHASSIS_ID = 'operational-qa-concierge'
BASE_PATH = ROOT / 'chassis/operational-qa-concierge/1.0.0/chassis-manifest.json'
RECIPE_VERSION = '0.1.0'
LIMITS = [
    'Local draft instructions and grounded knowledge preview only',
    'No live booking, messaging, account changes, payments, or system integrations',
    'Each commissioned instance still needs its own knowledge review and behavioral validation',
]

_RECIPES = [
    {
        'role_id': 'reception-intake', 'title': 'Reception & Intake',
        'summary': 'Welcome a visitor, understand the reason for contact, and prepare a useful first-contact brief.',
        'signals': ['receptionist', 'reception', 'front desk', 'greet visitors', 'visitor intake', 'initial intake', 'first contact', 'welcome visitors'],
        'purpose': 'Welcome visitors, identify their reason for contact, answer approved introductory questions, and prepare an intake brief for the right team.',
        'requirements': ['Establish the reason for contact before collecting intake details', 'Ask only for owner-approved contact and context fields', 'Prepare an intake brief with the requested next step and unresolved questions'],
        'method': ['Greet the visitor and ask what brought them here', 'Separate a general question from a request to contact a team', 'Collect the minimum useful details one at a time and confirm the intended next step'],
        'knowledge_needs': ['Company introduction and contact routes', 'Published opening hours and first-contact policies', 'Approved intake fields and team handoff rules'],
        'boundaries': ['Promise that a visitor has been connected to staff', 'Request sensitive personal data outside approved intake fields'],
        'artifact': 'First-contact intake brief',
        'scenarios': [
            {'case': 'Visitor asks who to speak to', 'expected': 'Use an approved contact route or mark it for confirmation', 'required_text': 'reason for contact'},
            {'case': 'Visitor provides only a name', 'expected': 'Ask the reason for contact before claiming intake is complete', 'required_text': 'minimum useful details'},
        ],
    },
    {
        'role_id': 'lead-qualification', 'title': 'Lead Qualification',
        'summary': 'Understand a prospective customer’s need and prepare an evidence-based sales qualification brief.',
        'signals': ['qualify leads', 'lead qualification', 'sales leads', 'prospects', 'sales qualification', 'qualify prospects', 'qualified leads', 'sales discovery'],
        'purpose': 'Help prospective customers describe their needs, compare them with approved fit criteria, and prepare a qualification brief for sales review.',
        'requirements': ['Capture the stated need and desired outcome before discussing fit', 'Distinguish stated timing and budget from unknown information', 'Use only owner-approved fit criteria and leave unconfirmed criteria unresolved'],
        'method': ['Ask what problem the prospect wants to solve and for whom', 'Ask approved discovery questions about scope and timing one at a time', 'Summarize evidence for fit and gaps separately without assigning an invented score'],
        'knowledge_needs': ['Approved offer and target-customer fit criteria', 'Discovery questions and permitted qualification fields', 'Sales handoff policy and pricing authority'],
        'boundaries': ['Invent lead scores or assume purchase intent', 'Promise a quote or automatically contact the prospect'],
        'artifact': 'Sales qualification brief with fit evidence and gaps',
        'scenarios': [
            {'case': 'Prospect has a clear need but no budget', 'expected': 'Keep budget unknown and qualify using only available evidence', 'required_text': 'budget from unknown'},
            {'case': 'Prospect asks for a guaranteed price', 'expected': 'Use approved pricing authority or prepare sales review', 'required_text': 'without assigning an invented score'},
        ],
    },
    {
        'role_id': 'support-triage', 'title': 'Support Triage',
        'summary': 'Gather symptoms and impact, offer approved guidance, and prepare a support case for review.',
        'signals': ['support triage', 'support tickets', 'technical support', 'help desk', 'troubleshooting', 'troubleshoot', 'issue severity', 'incident triage'],
        'purpose': 'Help customers describe a support issue, gather impact and relevant context, provide approved troubleshooting guidance, and prepare a support case.',
        'requirements': ['Preserve the reported symptom alongside the affected product and user-stated impact', 'Suggest only explicitly approved and non-destructive troubleshooting steps', 'Record attempted steps and unresolved symptoms for support review'],
        'method': ['Ask what is failing and how it affects the customer', 'Check approved support instructions before offering a step', 'Confirm the result of each step and prepare escalation if the issue remains unresolved'],
        'knowledge_needs': ['Approved troubleshooting articles and product limits', 'Support severity and escalation policies', 'Required support-case fields and safe diagnostic boundaries'],
        'boundaries': ['Invent a diagnosis or guarantee a fix', 'Run commands or change a customer system'],
        'artifact': 'Support case with symptoms, impact, and attempted steps',
        'scenarios': [
            {'case': 'Customer describes an unfamiliar error', 'expected': 'Capture the exact symptom and escalate without guessing a diagnosis', 'required_text': 'reported symptom'},
            {'case': 'An approved troubleshooting step fails', 'expected': 'Record the attempt and preserve the unresolved issue', 'required_text': 'result of each step'},
        ],
    },
    {
        'role_id': 'client-onboarding', 'title': 'Client Onboarding',
        'summary': 'Guide a new client through an approved checklist and identify the next incomplete step.',
        'signals': ['onboarding', 'onboard clients', 'new clients', 'new customers', 'setup checklist', 'orientation', 'getting started'],
        'purpose': 'Guide new clients through the approved onboarding sequence, explain required materials, and prepare a progress checklist with remaining steps.',
        'requirements': ['Follow the approved onboarding sequence and prerequisites', 'Mark a step complete only when the client confirms its completion', 'Separate completed steps from missing materials and questions requiring the onboarding team'],
        'method': ['Ask which approved onboarding stage the client has reached', 'Explain the next incomplete step and its required materials', 'Update progress from explicit confirmations and finish with a checklist of remaining work'],
        'knowledge_needs': ['Approved onboarding checklist and prerequisites', 'Required client materials and secure submission instructions', 'Onboarding ownership, timing guidance, and escalation contacts'],
        'boundaries': ['Claim an account was provisioned or a document was submitted', 'Collect passwords or mark unconfirmed steps complete'],
        'artifact': 'Onboarding progress checklist and open questions',
        'scenarios': [
            {'case': 'Client asks whether setup is complete', 'expected': 'Check explicit completion against approved prerequisites', 'required_text': 'explicit confirmations'},
            {'case': 'Client skips a prerequisite', 'expected': 'Identify the missing requirement without falsely completing the stage', 'required_text': 'sequence and prerequisites'},
        ],
    },
    {
        'role_id': 'product-service-guidance', 'title': 'Product & Service Guidance',
        'summary': 'Compare approved options against the customer’s stated needs without inventing specifications or claims.',
        'signals': ['compare products', 'compare services', 'compare options', 'product guidance', 'service guidance', 'product recommendation', 'choose a product', 'choose a service', 'buying guide', 'product comparison', 'help customers choose'],
        'purpose': 'Help customers compare approved products or services against their stated needs, explain documented differences, and prepare an options summary.',
        'requirements': ['Ask for the decision criteria that matter to the customer', 'Compare only attributes explicitly supported by approved product or service information', 'Explain tradeoffs and missing information without inventing a best option'],
        'method': ['Ask what the customer needs the product or service to accomplish', 'Select relevant approved options and compare documented attributes', 'Explain how each option fits the stated criteria and identify questions for staff'],
        'knowledge_needs': ['Approved product or service catalog and specifications', 'Documented eligibility, compatibility, and limitations', 'Current pricing authority, warranty, and availability policies'],
        'boundaries': ['Invent compatibility or prices or stock availability', 'Take payment or place an order'],
        'artifact': 'Options comparison with fit criteria and open questions',
        'scenarios': [
            {'case': 'Customer asks which option is best', 'expected': 'Ask decision criteria and compare supported attributes', 'required_text': 'decision criteria'},
            {'case': 'A key specification is missing', 'expected': 'Flag the missing information without manufacturing compatibility', 'required_text': 'documented attributes'},
        ],
    },
    {
        'role_id': 'internal-knowledge', 'title': 'Internal Knowledge',
        'summary': 'Help staff find approved internal guidance and identify unanswered or conflicting policy questions.',
        'signals': ['internal knowledge', 'employee knowledge', 'staff knowledge', 'internal wiki', 'company policies', 'employee handbook', 'internal faq', 'sop', 'standard operating procedures', 'staff questions'],
        'purpose': 'Help staff find and understand approved internal policies and procedures, provide source-linked answers, and prepare unresolved questions for the document owner.',
        'requirements': ['Answer employee questions from the approved internal source scope', 'Identify the supporting policy or procedure and state its limits', 'Keep an informational answer separate from any operational request and flag missing or conflicting guidance'],
        'method': ['Identify the employee question and the relevant approved document scope', 'Locate explicit support and explain the applicable policy or procedure', 'Name the supporting source and flag missing guidance for its owner without inventing a policy'],
        'knowledge_needs': ['Owner-approved internal policies and procedures', 'Document ownership, version, and effective-date information', 'Approved access scope and policy escalation rules'],
        'boundaries': ['Infer access permission from a claimed identity', 'Expose unapproved personnel information or decide a policy exception'],
        'artifact': 'Source-linked internal answer and unresolved policy questions',
        'scenarios': [
            {'case': 'Employee asks a documented policy question', 'expected': 'Answer from the approved policy without asking for service location or urgency', 'required_text': 'relevant approved document scope'},
            {'case': 'Two approved documents disagree', 'expected': 'Surface the conflict for the document owner instead of choosing an unsupported rule', 'required_text': 'missing or conflicting guidance'},
        ],
    },
]

_OPERATIONAL = {
    'role_id': 'operational-concierge', 'title': 'Operational Concierge',
    'summary': 'Answer approved questions, qualify service requests, preserve corrections, and prepare a staff handoff.',
    'signals': ['operational concierge', 'home service', 'home-service', 'service requests', 'staff handoff', 'approved questions', 'collect request details', 'concierge'],
    'purpose': 'Answer approved questions, qualify service requests, and prepare a structured staff handoff.',
    'requirements': ['Answer approved questions', 'Qualify the visitor request', 'Maintain visible notes', 'Prepare a structured staff handoff'],
    'method': ['Understand the primary request', 'Gather only relevant approved intake fields', 'Keep corrections and secondary questions separate from the primary request'],
    'knowledge_needs': ['Company overview', 'Approved services and coverage', 'Intake and escalation rules'],
    'boundaries': ['Invent business facts', 'Promise availability or perform external actions'],
    'artifact': 'Structured staff handoff',
    'scenarios': [
        {'case': 'Customer corrects a service location', 'expected': 'Update current location and preserve the previous value', 'required_text': 'corrections'},
        {'case': 'An unrelated question is unknown', 'expected': 'Preserve the primary request and separately flag the unknown', 'required_text': 'secondary questions'},
    ],
}


def _public_role(recipe):
    role = deepcopy(recipe)
    original = role['role_id'] == 'operational-concierge'
    role.update({
        'chassis_id': BASE_CHASSIS_ID if original else 'role-' + role['role_id'],
        'version': '1.0.0' if original else RECIPE_VERSION,
        'status': 'EXISTING_LOCAL_CHASSIS' if original else 'LOCAL_ROLE_RECIPE',
        'foundation_chassis_id': BASE_CHASSIS_ID,
        'validation_scope': 'Existing chassis validation remains attached only to its original artifact' if original else 'Recipe contract and generated prompt/blueprint checks; not live behavioral or semantic certification',
        'capability_limits': deepcopy(LIMITS),
        'provider_calls': 0,
    })
    role['recipe_sha256'] = sha256(canonical(role))
    return role


def list_roles():
    return [_public_role(recipe) for recipe in [*_RECIPES, _OPERATIONAL]]


def role_for_chassis(chassis_id):
    return next((role for role in list_roles() if role['chassis_id'] == chassis_id), None)


def role_for_brief(brief):
    binding = brief.get('commissioning') or {}
    role = role_for_chassis(binding.get('chassis_id') or brief.get('chassis_id'))
    if role and role['status'] == 'LOCAL_ROLE_RECIPE' and binding:
        manifest = role_chassis(role['chassis_id'], binding.get('chassis_version'))
        if binding.get('chassis_sha256') != manifest['chassis_sha256']:
            raise ValueError('The commissioned role recipe changed. Re-select the current role before building.')
    return role


def role_chassis(chassis_id, version=None):
    """Materialize a recipe manifest without copying the foundation's proof."""
    role = role_for_chassis(chassis_id)
    if not role or role['status'] != 'LOCAL_ROLE_RECIPE':
        return None
    if version is not None and version != RECIPE_VERSION:
        raise ValueError('That role recipe version is not available')
    base = load_json(BASE_PATH)
    if sha256(canonical({k: v for k, v in base.items() if k != 'chassis_sha256'})) != base['chassis_sha256']:
        raise ValueError('Role recipe foundation integrity validation failed')
    manifest = {
        'schema_version': '0.1', 'chassis_id': chassis_id, 'version': RECIPE_VERSION,
        'status': 'LOCAL_ROLE_RECIPE', 'role_title': role['title'], 'summary': role['summary'],
        'source': {'kind': 'ROLE_RECIPE_OVER_EXISTING_LOCAL_ENGINE', 'role_id': role['role_id'],
                   'recipe_sha256': role['recipe_sha256'], 'foundation_chassis_id': base['chassis_id'],
                   'foundation_sha256': base['chassis_sha256'], 'semantic_review': 'NOT_PERFORMED_FOR_THIS_RECIPE'},
        'invariants': {'purpose_template': role['purpose'], 'must_accomplish': role['requirements'],
                       'never_do': list(dict.fromkeys([*base['invariants']['never_do'], *role['boundaries']])),
                       'output_artifact': role['artifact'], 'prompt_layers': ['Universal X-Agent kernel', role['title'] + ' role recipe', 'Reviewed company purpose', 'Approved Knowledge Bank']},
        'configurable_slots': deepcopy(base['configurable_slots']), 'modules': deepcopy(base['modules']),
        'knowledge_contract': {'runtime_knowledge_included': False, 'required_client_materials': role['knowledge_needs'],
                              'ingestion_status': 'OWNER_REVIEW_REQUIRED', 'unsupported_fact_policy': 'ESCALATE_WITHOUT_GUESSING'},
        'evaluation': {'reusable_scenarios': [case['case'] for case in role['scenarios']],
                       'recipe_contract_checks': 'scripts/verify_role_library_v0_1.py',
                       'validation_scope': role['validation_scope'], 'live_behavior_validated': False,
                       'final_instance_recertification_required': True, 'client_knowledge_tests_required': True},
        'authority': {'provider_calls': 0, 'client_data_attached': False, 'credentials_attached': False,
                      'deployment_authorized': False, 'production_approved': False,
                      'claim': 'Role-specific draft recipe on the shared local engine; not independently runtime-certified',
                      'capability_limits': role['capability_limits']},
    }
    manifest['chassis_sha256'] = sha256(canonical(manifest))
    return manifest


def _intent_text(purpose):
    text = re.sub(r'\s+', ' ', purpose).strip()
    # Generated universal grounding text must not turn every unrelated idea
    # into a concierge recommendation just because it mentions a handoff.
    return text.split('Answer using owner-approved Knowledge Bank facts', 1)[0]


def _matches(text, phrase):
    return re.search(r'\b' + re.escape(phrase) + r'\b', text, re.I) is not None


def recommend_roles(purpose, research=None):
    if not isinstance(purpose, str) or not 10 <= len(purpose.strip()) <= 3000:
        raise ValueError('Describe the proposed job in 10 to 3000 characters.')
    intent = _intent_text(purpose)
    # Negative statements remain boundaries, not requested abilities.
    positive = re.sub(r'\b(?:do not|never|without|no)\b[^.;\n]*(?:[.;\n]|$)', '', intent, flags=re.I)
    unsupported_patterns = [
        r'\b(?:autonomous|automated)\s+(?:stock[- ]?)?trading\b',
        r'\b(?:execute trades|trade stocks|prescribe medication|diagnose patients|medical diagnosis|provide legal advice)\b',
        r'\b(?:process payments|charge credit cards|book appointments|dispatch technicians|send emails|sync (?:the )?crm|deploy code|run arbitrary code)\b',
    ]
    gaps = [match.group(0) for pattern in unsupported_patterns for match in re.finditer(pattern, positive, re.I)]
    research_text = ''
    if isinstance(research, dict):
        pieces = [research.get('summary', ''), research.get('proposed_purpose', '')]
        pieces += [item.get('description', '') for item in research.get('role_requirements', []) if isinstance(item, dict)]
        research_text = ' '.join(str(piece) for piece in pieces)
    ranked = []
    for role in list_roles():
        direct = [signal for signal in role['signals'] if _matches(intent, signal)]
        source = [signal for signal in role['signals'] if _matches(research_text, signal)]
        score = 4 * len(direct) + len(source)
        if not score:
            continue
        ranked.append({'role': role, 'score': score, 'matched_signals': direct,
                       'research_signals': source, 'reasons': [
                           *[f'Your job mentions {signal}.' for signal in direct[:3]],
                           *[f'Research context suggests {signal}; this still needs your review.' for signal in source[:2]],
                       ]})
    ranked.sort(key=lambda item: (-item['score'], item['role']['title']))
    fit = 'NO_FIT' if gaps or not ranked else ('FIT' if ranked[0]['matched_signals'] else 'POSSIBLE_FIT')
    strategic = None
    if isinstance(research, dict) and 'strategic_role_fit' in research:
        strategic = research['strategic_role_fit']
        required = {'role_id', 'fit_status', 'reason', 'capability_gaps'}
        if (not isinstance(strategic, dict) or set(strategic) != required or
                strategic['fit_status'] not in {'FIT', 'POSSIBLE_FIT', 'NO_FIT'} or
                not isinstance(strategic['reason'], str) or not strategic['reason'].strip() or
                not isinstance(strategic['capability_gaps'], list) or
                any(not isinstance(gap, str) or not gap.strip() for gap in strategic['capability_gaps'])):
            raise ValueError('Research role fit must contain a known role, fit status, reason, and text capability gaps.')
        selected = next((role for role in list_roles() if role['role_id'] == strategic['role_id']), None)
        if strategic['role_id'] is not None and selected is None:
            raise ValueError('Research selected an unknown role. Review a current library role instead.')
        if strategic['fit_status'] != 'NO_FIT' and selected is None:
            raise ValueError('A positive research role fit must select a current library role.')
        suggestion = f"Research suggestion for your review: {strategic['reason']}"
        if selected is not None:
            row = next((item for item in ranked if item['role']['role_id'] == selected['role_id']), None)
            if row is None:
                row = {'role': selected, 'score': 0, 'matched_signals': [], 'research_signals': [], 'reasons': []}
            row = {**row, 'reasons': [suggestion], 'ranking_basis': 'REVIEWABLE_RESEARCH_SUGGESTION'}
            ranked = [row, *[item for item in ranked if item['role']['role_id'] != selected['role_id']]]
        fit = 'NO_FIT' if gaps else strategic['fit_status']
    result = {
        'schema_version': 'factory.role-recommendation.v0.1', 'owner_intent': purpose,
        'fit_status': fit, 'recommended': ranked[0]['role'] if fit != 'NO_FIT' else None,
        'ranked': ranked, 'reasons': ranked[0]['reasons'] if ranked and not gaps else [],
        'capability_gaps': gaps,
        'explanation': ('The requested actions exceed the current local role recipes. Choose a narrower advisory job or add an integration later.' if gaps else
                        'No role clearly matches yet. Describe the main customer task or choose a role explicitly.' if not ranked else
                        'These are distinct draft instructions over the same local engine. Each finished agent still needs its own behavioral checks.'),
        'provider_calls': 0,
    }
    if strategic is not None:
        result['recommendation_basis'] = 'REVIEWABLE_RESEARCH_SUGGESTION'
        result['strategic_role_fit'] = deepcopy(strategic)
        result['reasons'] = [f"Research suggestion for your review: {strategic['reason']}"]
        result['capability_gaps'] = list(dict.fromkeys([*gaps, *strategic['capability_gaps']]))
        if not gaps:
            result['explanation'] = ('Research found no suitable current role. Review its reason and choose a narrower job or a new role.'
                                     if fit == 'NO_FIT' else
                                     'Research considered the job and source context when suggesting this role. Review the proposed fit before choosing it.')
    return result


def role_prompt_section(chassis_id):
    role = role_for_chassis(chassis_id)
    if not role or role['status'] != 'LOCAL_ROLE_RECIPE':
        return ''
    steps = '\n'.join(f'{i}. {step}.' for i, step in enumerate(role['method'], 1))
    knowledge = '\n'.join(f'- {item}' for item in role['knowledge_needs'])
    return (
        f'Role operating method: {role["title"]}\n{steps}\n\n'
        'Use only these approved source types when they are available; a missing source is a gap, not a fact:\n'
        f'{knowledge}\n\nExpected work product: {role["artifact"]}.\n'
        'Do not force service location, service category, urgency, or sales qualification onto an unrelated informational question. '
        'Keep only the state needed for this role, preserve explicit corrections, and clear prior user state for a new session.'
    )


def role_test_cases(chassis_id):
    role = role_for_chassis(chassis_id)
    if not role or role['status'] != 'LOCAL_ROLE_RECIPE':
        return []
    return [
        {'test_id': f'ROLE-{role["role_id"]}-{i:02d}', 'focus': case['case'], 'expected': case['expected'],
         'assertion': {'kind': 'GENERATED_PROMPT_CONTAINS', 'value': case['required_text']},
         'scope': 'ARTIFACT_CONTRACT_CHECK_NOT_LIVE_CONVERSATION'}
        for i, case in enumerate(role['scenarios'], 1)
    ]
