"""Exercise real role commissioning/blueprint/prompt paths without mission writes."""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from x_factory import chassis_depot_v0_1 as depot
from x_factory import mission_control_factory_v0_1 as factory
from x_factory.prompt_forge_v0_1 import compile_prompt_package, PromptForgeError
from x_factory import role_library_v0_1 as library


class RoleTests(unittest.TestCase):
    def test_seven_roles_and_honest_recipe_provenance(self):
        roles = library.list_roles()
        self.assertEqual(len(roles), 7)
        self.assertEqual(len({role['chassis_id'] for role in roles}), 7)
        self.assertEqual(len(depot.list_chassis()), 7)
        original = factory.load_json(library.BASE_PATH)
        self.assertEqual(depot.get_chassis(library.BASE_CHASSIS_ID), original)
        for role in roles:
            chassis = depot.get_chassis(role['chassis_id'])
            depot.validate_chassis(chassis)
            if role['status'] != 'LOCAL_ROLE_RECIPE':
                continue
            self.assertEqual(chassis['status'], 'LOCAL_ROLE_RECIPE')
            self.assertNotIn('review_id', chassis['source'])
            self.assertNotIn('mission_id', chassis['source'])
            self.assertEqual(chassis['source']['semantic_review'], 'NOT_PERFORMED_FOR_THIS_RECIPE')
            self.assertFalse(chassis['evaluation']['live_behavior_validated'])
            self.assertFalse(chassis['authority']['production_approved'])
            self.assertEqual(chassis['invariants']['must_accomplish'], role['requirements'])
            self.assertEqual(chassis['knowledge_contract']['required_client_materials'], role['knowledge_needs'])

    def test_distinct_recommendations_and_explained_no_fit(self):
        examples = {
            'reception-intake': 'Create a receptionist to greet visitors at our front desk.',
            'lead-qualification': 'Qualify sales leads and capture their stated needs for sales review.',
            'support-triage': 'Provide support triage and approved troubleshooting for customer problems.',
            'client-onboarding': 'Guide new clients through an approved onboarding checklist.',
            'product-service-guidance': 'Help customers compare products against their stated needs.',
            'internal-knowledge': 'Answer employee questions from our internal knowledge and company policies.',
            'operational-concierge': 'Answer approved questions, collect request details, and prepare a staff handoff.',
        }
        for role_id, purpose in examples.items():
            with self.subTest(role=role_id):
                result = library.recommend_roles(purpose)
                self.assertEqual(result['fit_status'], 'FIT')
                self.assertEqual(result['recommended']['role_id'], role_id)
                self.assertTrue(result['reasons'])
                selected = depot.recommend_chassis(purpose)
                self.assertEqual(selected['recommended']['chassis_id'], result['recommended']['chassis_id'])
        for purpose in ['Build a fantasy landscape generator for a video game.',
                        'Build an autonomous stock trading agent that will execute trades.',
                        'Create a receptionist that will book appointments and process payments.']:
            result = library.recommend_roles(purpose)
            self.assertEqual(result['fit_status'], 'NO_FIT')
            self.assertIsNone(result['recommended'])
            self.assertIsNone(depot.recommend_chassis(purpose)['recommended'])
        bounded = library.recommend_roles('Create a receptionist. Do not book appointments or process payments.')
        self.assertEqual(bounded['fit_status'], 'FIT')
        self.assertEqual(bounded['recommended']['role_id'], 'reception-intake')

    def test_research_suggestions_are_labeled_tentative(self):
        result = library.recommend_roles('Help this company with its customer experience.', {
            'summary': 'Customers need help with onboarding.',
            'role_requirements': [{'description': 'Explain the setup checklist', 'basis': 'RESEARCH_INFERENCE', 'source_ids': ['SRC-1']}],
        })
        self.assertEqual(result['fit_status'], 'POSSIBLE_FIT')
        self.assertEqual(result['recommended']['role_id'], 'client-onboarding')
        self.assertEqual(result['ranked'][0]['matched_signals'], [])
        self.assertTrue(all('needs your review' in reason for reason in result['reasons']))

    def test_strategic_research_fit_overrides_misleading_orientation_keyword(self):
        purpose = 'Provide orientation to Python Software Foundation resources and help visitors find the right published program.'
        baseline = library.recommend_roles(purpose)
        self.assertEqual(baseline['recommended']['role_id'], 'client-onboarding')
        reason = 'This is an informational resource navigator, not a client onboarding workflow. Product and service guidance best supports comparing published programs.'
        context = {'strategic_role_fit': {
            'role_id': 'product-service-guidance', 'fit_status': 'POSSIBLE_FIT',
            'reason': reason, 'capability_gaps': ['The role needs approved information about the published programs.'],
        }}
        result = library.recommend_roles(purpose, context)
        self.assertEqual(result['recommended']['role_id'], 'product-service-guidance')
        self.assertEqual(result['ranked'][0]['role']['role_id'], 'product-service-guidance')
        self.assertEqual(result['fit_status'], 'POSSIBLE_FIT')
        self.assertEqual(result['reasons'], ['Research suggestion for your review: ' + reason])
        self.assertEqual(result['ranked'][0]['ranking_basis'], 'REVIEWABLE_RESEARCH_SUGGESTION')
        self.assertEqual(result['capability_gaps'], context['strategic_role_fit']['capability_gaps'])
        self.assertEqual(library.recommend_roles(purpose), baseline)

    def test_strategic_role_fit_cannot_override_local_unsupported_actions(self):
        reason = 'A receptionist appears related to the initial customer interaction.'
        result = library.recommend_roles('Create a receptionist that will process payments.', {
            'strategic_role_fit': {'role_id': 'reception-intake', 'fit_status': 'FIT', 'reason': reason, 'capability_gaps': []},
        })
        self.assertEqual(result['fit_status'], 'NO_FIT')
        self.assertIsNone(result['recommended'])
        self.assertIn('process payments', result['capability_gaps'])
        self.assertIn('exceed the current local role recipes', result['explanation'])

    def test_unknown_or_missing_strategic_role_never_silently_forces_a_role(self):
        suggestion = {'role_id': 'nonexistent-role', 'fit_status': 'FIT', 'reason': 'Suggested for the reported task.', 'capability_gaps': []}
        with self.assertRaisesRegex(ValueError, 'unknown role'):
            library.recommend_roles('Create a receptionist for visitors.', {'strategic_role_fit': suggestion})
        with self.assertRaisesRegex(ValueError, 'positive research role fit'):
            library.recommend_roles('Create a receptionist for visitors.', {'strategic_role_fit': suggestion | {'role_id': None}})
        result = library.recommend_roles('Create a receptionist for visitors.', {
            'strategic_role_fit': suggestion | {'role_id': None, 'fit_status': 'NO_FIT'},
        })
        self.assertEqual(result['fit_status'], 'NO_FIT')
        self.assertIsNone(result['recommended'])
        self.assertEqual(result['reasons'], ['Research suggestion for your review: Suggested for the reported task.'])

    def test_every_recipe_changes_real_commissioned_artifacts(self):
        prompt_hashes = set()
        with tempfile.TemporaryDirectory() as sandbox:
            temp = Path(sandbox)
            for role in library.list_roles():
                if role['status'] != 'LOCAL_ROLE_RECIPE':
                    continue
                with self.subTest(role=role['role_id']):
                    request = {
                        'purpose': role['purpose'], 'x_agent_name': 'Fixture Ava',
                        'client_name': 'Fictional Company', 'personality': 'Clear and helpful',
                        'target_users': 'Approved test users', 'client_context': '',
                        'presence_mode': 'TEXT_ONLY',
                    }
                    with patch.object(depot, 'create_mission', return_value={'mission_id': 'fixture-only'}) as create:
                        result = depot.commission_chassis(role['chassis_id'], request)
                        create.assert_called_once()
                        payload = create.call_args.args[0]
                    self.assertEqual(payload['output_artifact'], role['artifact'])
                    self.assertEqual(payload['public_role_title'], role['title'])
                    self.assertEqual(result['commissioning_summary']['chassis_id'], role['chassis_id'])
                    brief = factory.normalize_brief(payload)
                    blueprint = factory.build_blueprint(brief, 'fixture-role-' + role['role_id'])
                    package = compile_prompt_package(brief, [], 'fixture-role-' + role['role_id'])
                    prompt = package['prompt']
                    prompt_hashes.add(package['system_prompt_sha256'])
                    for requirement in role['requirements']:
                        self.assertIn(requirement, brief['must_accomplish'])
                        self.assertIn(requirement, blueprint['explicit_requirements'])
                        self.assertIn(requirement, prompt)
                    for step in role['method']:
                        self.assertIn(step, prompt)
                        self.assertIn(step, blueprint['conversation']['discovery_behavior'])
                    for need in role['knowledge_needs']:
                        self.assertIn(need, prompt)
                        self.assertIn(need, blueprint['knowledge']['required_domains'])
                    for case in role['scenarios']:
                        self.assertTrue(any(case['case'] in scenario for scenario in blueprint['evaluation_plan']['scenarios']))
                        self.assertIn(case['required_text'].casefold(), prompt.casefold())
                    tests = json.loads(package['values']['instance/system-prompt/PROMPT_TESTS.v0.1.json'])
                    role_tests = [test for test in tests['tests'] if test['test_id'].startswith('ROLE-')]
                    self.assertEqual(len(role_tests), 2)
                    self.assertTrue(all(test['artifact_assertion_result'] == 'PASS' for test in role_tests))
                    self.assertTrue(all(test['scope'] == 'ARTIFACT_CONTRACT_CHECK_NOT_LIVE_CONVERSATION' for test in role_tests))
                    self.assertNotIn('Determine whether it is an informational question, service request', prompt)
                    self.assertNotIn('Route the primary need according to its service category and urgency.', prompt)
                    self.assertIn('No owner-approved Knowledge Bank is currently bound', prompt)
                    self.assertFalse(blueprint['authority']['production_approved'])
                    # Actual generated artifacts can be written/re-read in isolation.
                    factory.write_new(temp / role['role_id'] / 'blueprint.json', blueprint)
                    factory.write_new(temp / role['role_id'] / 'SYSTEM_PROMPT.md', prompt.encode('utf-8'))
            self.assertEqual(len(prompt_hashes), 6)
            self.assertEqual(len(list(temp.glob('*/blueprint.json'))), 6)

    def test_prompt_assertion_fails_when_role_behavior_is_missing(self):
        role = library.role_for_chassis('role-internal-knowledge')
        with patch.object(depot, 'create_mission', return_value={}) as create:
            depot.commission_chassis(role['chassis_id'], {
                'purpose': role['purpose'], 'x_agent_name': 'Test Ava', 'client_name': 'Test Company',
                'personality': 'Helpful', 'target_users': 'Test users', 'client_context': '', 'presence_mode': 'TEXT_ONLY',
            })
        brief = factory.normalize_brief(create.call_args.args[0])
        with patch.object(library, 'role_prompt_section', return_value='Missing the real role method'):
            with self.assertRaisesRegex(PromptForgeError, 'Role prompt contract failed'):
                compile_prompt_package(brief, [], 'fixture-missing-method')

    def test_original_prompt_and_chassis_keep_existing_behavior(self):
        with patch.object(depot, 'create_mission', return_value={}) as create:
            depot.commission_chassis(library.BASE_CHASSIS_ID, {
                'purpose': 'Answer approved questions and prepare a staff handoff.',
                'x_agent_name': 'Test Ava', 'client_name': 'Test Company', 'personality': 'Helpful',
                'target_users': 'Test users', 'client_context': '', 'presence_mode': 'TEXT_ONLY',
            })
        brief = factory.normalize_brief(create.call_args.args[0])
        package = compile_prompt_package(brief, [], 'fixture-original')
        self.assertIn('Route the primary need according to its service category and urgency.', package['prompt'])
        tests = json.loads(package['values']['instance/system-prompt/PROMPT_TESTS.v0.1.json'])
        self.assertEqual(len(tests['tests']), 8)

    def test_changed_role_recipe_binding_cannot_silently_compile(self):
        role = library.role_for_chassis('role-client-onboarding')
        with patch.object(depot, 'create_mission', return_value={}) as create:
            depot.commission_chassis(role['chassis_id'], {
                'purpose': role['purpose'], 'x_agent_name': 'Test Ava', 'client_name': 'Test Company',
                'personality': 'Helpful', 'target_users': 'Test users', 'client_context': '', 'presence_mode': 'TEXT_ONLY',
            })
        brief = factory.normalize_brief(create.call_args.args[0])
        brief['commissioning']['chassis_sha256'] = '0' * 64
        with self.assertRaisesRegex(ValueError, 'role recipe changed'):
            factory.build_blueprint(brief, 'fixture-stale-role')
        with self.assertRaisesRegex(ValueError, 'role recipe changed'):
            compile_prompt_package(brief, [], 'fixture-stale-role')


if __name__ == '__main__':
    unittest.main(verbosity=2)
