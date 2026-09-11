"""Exact passage selection and canonical evidence-validation regressions."""
import sys
import unittest
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from x_factory import research_citations_v0_1 as citations
from x_factory import idea_research_v0_1 as research


def evidence(text=None, title='Example Company', url='https://example.com/'):
    return {'url': url, 'title': title, 'retrieved_at': datetime.now(timezone.utc).isoformat(),
            'text': text or 'Example Company helps new customers.\n\nWe provide a reviewed onboarding checklist.\n\nContact staff for questions about account setup.',
            'access_status': 'FETCHED'}


def selection():
    return {
        'identity_status': 'RESOLVED',
        'company_candidates': [{'name': 'Example Company', 'website': 'https://example.com/', 'source_ids': ['S1']}],
        'findings': [{'source_id': 'S1', 'passage_id': 'P2'}],
        'uncertainties': ['Confirm the current onboarding owner and required documents.'],
        'proposed_purpose': 'Guide new clients through an approved onboarding checklist and explain the next step.',
        'role_requirements': [{'description': 'Ask the client which onboarding step is incomplete.', 'basis': 'OWNER_INTENT', 'source_ids': []}],
        'summary': 'An onboarding guide is proposed for owner review using captured company sources.',
    }


class CitationTests(unittest.TestCase):
    def test_valid_selection_roundtrips_through_unchanged_backend(self):
        record = evidence()
        original_record = deepcopy(record)
        model = selection()
        view = citations.citation_view(record, 'S1')
        self.assertEqual(view, citations.citation_view(record, 'S1'))
        self.assertEqual(view['title'], record['title'])
        self.assertEqual(view['passages'][1]['text'], 'We provide a reviewed onboarding checklist.')
        result = citations.compile_selection(model, {'S1': record})
        self.assertEqual(result['findings'], [{'finding_id': 'F1', 'statement': view['passages'][1]['text'], 'source_ids': ['S1']}])
        self.assertEqual(result['sources'][0]['excerpt'], record['text'])
        self.assertEqual(result['sources'][0]['title'], record['title'])
        envelope = {'research': result, 'source_evidence': [record], 'usage': {'model_calls': 0, 'tool_calls': 0}}
        self.assertEqual(research.validate_result(envelope, started_at=record['retrieved_at']), result)
        self.assertEqual(record, original_record)
        self.assertEqual(model, selection())

    def test_passages_are_exact_contiguous_substrings_inside_first_6000_characters(self):
        text = ' \n' + ('A specific approved sentence about the company. ' * 155) + '\n\nAFTER_WINDOW_SENTINEL cannot be selected.'
        record = evidence(text=text)
        view = citations.citation_view(record, 'S1')
        self.assertGreater(len(view['passages']), 1)
        for passage in view['passages']:
            self.assertGreaterEqual(len(passage['text']), 10)
            self.assertLessEqual(len(passage['text']), 1000)
            self.assertIn(passage['text'], text[:6000])
            self.assertNotIn('AFTER_WINDOW_SENTINEL', passage['text'])
        model = selection()
        model['findings'] = [{'source_id': 'S1', 'passage_id': view['passages'][-1]['passage_id']}]
        result = citations.compile_selection(model, {'S1': record})
        self.assertEqual(result['sources'][0]['excerpt'], text[:6000])
        research.validate_result({'research': result, 'source_evidence': [record]})

    def test_company_and_role_references_include_sources_without_selected_findings(self):
        first = evidence()
        second = evidence('Approved setup instructions require a staff review.', title='Setup instructions', url='https://example.com/setup')
        model = selection()
        model['role_requirements'].append({'description': 'Prepare unresolved setup questions for staff review.', 'basis': 'SOURCE_EVIDENCE', 'source_ids': ['S2']})
        result = citations.compile_selection(model, {'S2': second, 'S1': first})
        self.assertEqual([source['source_id'] for source in result['sources']], ['S1', 'S2'])
        self.assertEqual(len(result['findings']), 1)
        research.validate_result({'research': result, 'source_evidence': [first, second]})

    def test_unknown_source_passage_or_synthesized_quote_is_rejected(self):
        changes = [
            lambda model: model['findings'][0].update(source_id='S8'),
            lambda model: model['findings'][0].update(passage_id='P99'),
            lambda model: model['findings'][0].update(text='An invented or paraphrased company fact.'),
            lambda model: model['findings'][0].update(statement='Joined noncontiguous claims are forbidden.'),
            lambda model: model.update(sources=[{'excerpt': 'Invented quote'}]),
            lambda model: model['company_candidates'][0].update(source_ids=['S3']),
            lambda model: model['role_requirements'][0].update(basis='SOURCE_EVIDENCE', source_ids=['S4']),
        ]
        for change in changes:
            with self.subTest(change=change):
                model = selection()
                change(model)
                with self.assertRaises(citations.CitationAssemblyError):
                    citations.compile_selection(model, {'S1': evidence()})

    def test_source_free_result_preserves_uncertainty_without_fabricating_findings(self):
        model = selection()
        model.update(identity_status='NOT_IDENTIFIED', company_candidates=[], findings=[])
        result = citations.compile_selection(model, {})
        self.assertEqual(result['sources'], [])
        self.assertEqual(result['findings'], [])
        self.assertTrue(result['uncertainties'])
        research.validate_result({'research': result, 'source_evidence': []})
        model = selection()
        model['findings'] = []
        with self.assertRaises(citations.CitationAssemblyError):
            citations.compile_selection(model, {'S1': evidence()})

    def test_source_and_finding_budgets_and_reference_basis_are_constrained(self):
        records = {f'S{i}': evidence() for i in range(1, 10)}
        with self.assertRaises(citations.CitationAssemblyError):
            citations.compile_selection(selection(), records)
        model = selection()
        model['findings'] *= 31
        with self.assertRaises(citations.CitationAssemblyError):
            citations.compile_selection(model, {'S1': evidence()})
        for requirement in [
            {'description': 'A sourced requirement without a reference.', 'basis': 'SOURCE_EVIDENCE', 'source_ids': []},
            {'description': 'An owner requirement that claims a source.', 'basis': 'OWNER_INTENT', 'source_ids': ['S1']},
        ]:
            model = selection()
            model['role_requirements'] = [requirement]
            with self.assertRaises(citations.CitationAssemblyError):
                citations.compile_selection(model, {'S1': evidence()})

    def test_duplicated_selection_reuses_one_exact_finding(self):
        model = selection()
        model['findings'] *= 2
        result = citations.compile_selection(model, {'S1': evidence()})
        self.assertEqual(len(result['findings']), 1)
        self.assertEqual(result['findings'][0]['finding_id'], 'F1')


if __name__ == '__main__':
    unittest.main(verbosity=2)
