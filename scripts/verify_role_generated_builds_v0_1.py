"""Build two real recipe candidates exclusively in a disposable temporary root.

This verifies deterministic generated files and their tests. It performs no live
model, avatar, knowledge approval, deployment, or user-workspace mission action.
"""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from x_factory import mission_control_factory_v0_1 as factory
from x_factory.chassis_depot_v0_1 import commission_chassis, get_chassis
from x_factory.role_library_v0_1 import role_for_chassis


class GeneratedRoleTests(unittest.TestCase):
    def test_two_actual_builds_preserve_distinct_role_behavior_and_bounded_claims(self):
        prompts = {}
        requests = [
            ('role-lead-qualification', 'Mira', 'Fictional Lead Company',
             'Qualify sales leads for the owner-approved consulting offer. Capture their goals and timing, then prepare a sales brief. Do not invent a budget.'),
            ('role-internal-knowledge', 'Eli', 'Fictional Staff Company',
             'Answer staff questions using the approved internal knowledge and employee handbook. Identify the relevant policy and prepare unanswered questions for its owner.'),
        ]
        user_root = factory.INTERACTIVE_ROOT
        before = {path.name for path in user_root.iterdir()} if user_root.is_dir() else set()
        base_chassis_before = get_chassis('operational-qa-concierge')
        with tempfile.TemporaryDirectory(prefix='factory-role-generated-builds-') as temporary:
            isolated_root = Path(temporary) / 'runs'
            with patch.object(factory, 'INTERACTIVE_ROOT', isolated_root):
                for chassis_id, agent, company, purpose in requests:
                    with self.subTest(role=chassis_id):
                        role = role_for_chassis(chassis_id)
                        recipe = get_chassis(chassis_id)
                        record = commission_chassis(chassis_id, {
                            'purpose': purpose, 'x_agent_name': agent, 'client_name': company,
                            'personality': 'Clear, helpful, and concise', 'target_users': 'Synthetic test participants',
                            'client_context': 'A fictional company used only for isolated generated-build verification.',
                            'presence_mode': 'TEXT_ONLY',
                        })
                        root = isolated_root / record['mission_id']
                        self.assertTrue(root.is_dir())
                        self.assertEqual(record['build']['unit_tests'], 'PASS')
                        self.assertTrue(record['build']['repeatable'])
                        self.assertEqual(record['agent']['purpose'], purpose)
                        self.assertEqual(record['agent']['agent_name'], agent)
                        self.assertEqual(record['agent']['client_name'], company)
                        self.assertEqual(record['provider']['calls'], 0)
                        self.assertEqual(record['provider']['status'], 'SEMANTIC_REVIEW_PENDING')
                        self.assertEqual(record['anam']['provider_actions'], 0)
                        self.assertFalse(record['authority']['production_approved'])
                        self.assertFalse(record['authority']['deployment_authorized'])
                        self.assertEqual(record['knowledge']['entry_count'], 0)
                        self.assertFalse(record['knowledge']['runtime_installed'])
                        self.assertFalse(record['runtime_foundry']['live_runtime'])
                        self.assertEqual(recipe['source']['semantic_review'], 'NOT_PERFORMED_FOR_THIS_RECIPE')
                        self.assertNotIn('review_id', recipe['source'])

                        brief = factory.load_json(root / record['artifacts']['owner_brief'])
                        blueprint = factory.load_json(root / record['artifacts']['blueprint'])
                        spec = factory.load_json(root / record['artifacts']['agent_spec'])
                        certification = factory.load_json(root / record['artifacts']['certification'])
                        prompt = (root / 'instance/system-prompt/SYSTEM_PROMPT.md').read_text(encoding='utf-8')
                        prompt_tests = factory.load_json(root / 'instance/system-prompt/PROMPT_TESTS.v0.1.json')
                        assumptions = factory.load_json(root / 'instance/system-prompt/PROMPT_ASSUMPTIONS.v0.1.json')
                        prompts[chassis_id] = prompt
                        self.assertEqual(brief['commissioning']['chassis_sha256'], recipe['chassis_sha256'])
                        self.assertEqual(blueprint['owner_intent'], purpose)
                        self.assertEqual(spec['identity']['agent_name'], agent)
                        self.assertIn(purpose, prompt)
                        self.assertIn(role['artifact'], prompt)
                        for requirement in role['requirements']:
                            self.assertIn(requirement, brief['must_accomplish'])
                            self.assertIn(requirement, blueprint['explicit_requirements'])
                            self.assertIn(requirement, prompt)
                        for step in role['method']:
                            self.assertIn(step, prompt)
                        for need in role['knowledge_needs']:
                            self.assertIn(need, blueprint['knowledge']['required_domains'])
                            self.assertIn(need, prompt)
                        for case in role['scenarios']:
                            self.assertTrue(any(case['case'] in scenario for scenario in blueprint['evaluation_plan']['scenarios']))
                        tests = [test for test in prompt_tests['tests'] if test['test_id'].startswith('ROLE-')]
                        self.assertEqual(len(tests), 2)
                        self.assertTrue(all(test['artifact_assertion_result'] == 'PASS' for test in tests))
                        self.assertTrue(any('do not prove live conversational behavior' in item['statement'] for item in assumptions['assumptions']))
                        self.assertEqual(certification['unit_test_status'], 'PASS')
                        self.assertEqual(certification['provider_calls'], 0)
                        self.assertEqual(certification['network_attempts'], 0)
                        self.assertNotIn('HERMES_LUNA_UNANIMOUS_PASS', json.dumps(record))
                        self.assertNotIn('Route the primary need according to its service category and urgency.', prompt)
                self.assertEqual(len(list(isolated_root.glob('*/mission-record.json'))), 2)
        self.assertNotEqual(prompts['role-lead-qualification'], prompts['role-internal-knowledge'])
        self.assertIn('without assigning an invented score', prompts['role-lead-qualification'])
        self.assertNotIn('without assigning an invented score', prompts['role-internal-knowledge'])
        self.assertIn('relevant approved document scope', prompts['role-internal-knowledge'])
        self.assertEqual(get_chassis('operational-qa-concierge'), base_chassis_before)
        after = {path.name for path in user_root.iterdir()} if user_root.is_dir() else set()
        self.assertEqual(before, after, 'The user mission directory must be untouched.')


if __name__ == '__main__':
    unittest.main(verbosity=2)
