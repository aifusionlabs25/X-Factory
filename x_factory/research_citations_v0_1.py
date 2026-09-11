"""Assemble exact research citations from independently captured passages.

The model selects source and passage IDs. It never supplies the final source
quote or factual finding text. The normal research validator remains the final
check on the assembled result and the separately captured evidence.
"""
from __future__ import annotations

import re
from copy import deepcopy
from datetime import datetime, timezone

from jsonschema import Draft202012Validator

from x_factory.idea_research_v0_1 import RESEARCH_SCHEMA, _EVIDENCE_SCHEMA, _public_url

SOURCE_ID = re.compile(r'^S[1-8]$')
PASSAGE_ID = re.compile(r'^P[1-9][0-9]{0,2}$')
MAX_QUOTE_CHARACTERS = 6000
MAX_PASSAGE_CHARACTERS = 1000

MODEL_SELECTION_SCHEMA = deepcopy(RESEARCH_SCHEMA)
MODEL_SELECTION_SCHEMA['properties'].pop('sources')
MODEL_SELECTION_SCHEMA['required'].remove('sources')
MODEL_SELECTION_SCHEMA['properties']['findings'] = {
    'type': 'array', 'maxItems': 30,
    'items': {
        'type': 'object', 'additionalProperties': False,
        'required': ['source_id', 'passage_id'],
        'properties': {
            'source_id': {'type': 'string', 'pattern': SOURCE_ID.pattern},
            'passage_id': {'type': 'string', 'pattern': PASSAGE_ID.pattern},
        },
    },
}
MODEL_SELECTION_SCHEMA['allOf'] = [{
    'if': {'properties': {'identity_status': {'not': {'const': 'NOT_IDENTIFIED'}}}},
    'then': {'properties': {'findings': {'minItems': 1}}},
}]


class CitationAssemblyError(ValueError):
    pass


def _validate_record(record):
    if list(Draft202012Validator(_EVIDENCE_SCHEMA).iter_errors([record])):
        raise CitationAssemblyError('Citation evidence must be an intact, fetched public-page record.')
    _public_url(record['url'])
    try:
        observed = datetime.fromisoformat(record['retrieved_at'].replace('Z', '+00:00'))
        if observed.tzinfo is None:
            raise ValueError('Missing timezone')
    except (ValueError, TypeError) as error:
        raise CitationAssemblyError('Citation evidence needs an actual retrieval date with timezone.') from error
    return observed.astimezone(timezone.utc).date().isoformat()


def _passages(text):
    """Cut contiguous slices only; no joining paragraphs or rewriting text."""
    window = text[:MAX_QUOTE_CHARACTERS]
    chunks = []
    for match in re.finditer(r'\S[\s\S]*?(?=\n[ \t]*\n|\Z)', window):
        paragraph = match.group(0).rstrip()
        start = 0
        while start < len(paragraph):
            end = min(start + MAX_PASSAGE_CHARACTERS, len(paragraph))
            if end < len(paragraph):
                boundary = max(paragraph.rfind(' ', start, end), paragraph.rfind('\n', start, end))
                if boundary > start + MAX_PASSAGE_CHARACTERS // 2:
                    end = boundary
            passage = paragraph[start:end].strip()
            # Final findings require at least 10 characters. Very short headings
            # stay in the source excerpt/title, not standalone factual findings.
            if len(passage) >= 10:
                chunks.append({'passage_id': f'P{len(chunks) + 1}', 'text': passage})
            start = end
    return chunks


def citation_view(record, source_id):
    if not isinstance(source_id, str) or not SOURCE_ID.fullmatch(source_id):
        raise CitationAssemblyError('Citation source IDs must be S1 through S8.')
    observed_on = _validate_record(record)
    return {
        'source_id': source_id, 'url': record['url'], 'title': record['title'],
        'observed_on': observed_on, 'passages': _passages(record['text']),
    }


def compile_selection(model_result, evidence_by_source_id):
    errors=list(Draft202012Validator(MODEL_SELECTION_SCHEMA).iter_errors(model_result))
    if errors:
        # Report contract locations, never model text or provider exceptions.
        issue=', '.join(str(e.validator)+' at '+('/'.join(str(x) for x in e.absolute_path) or 'root') for e in errors[:4])
        raise CitationAssemblyError('Research selection contract mismatch: '+issue)
    if not isinstance(evidence_by_source_id, dict) or len(evidence_by_source_id) > 8:
        raise CitationAssemblyError('Citation assembly accepts at most eight captured sources.')
    views = {source_id: citation_view(record, source_id) for source_id, record in evidence_by_source_id.items()}
    used = set()
    findings = []
    seen = set()

    def require_source(source_id):
        if source_id not in views:
            raise CitationAssemblyError('Research referenced a source that was not captured.')
        used.add(source_id)

    for selection in model_result['findings']:
        source_id, passage_id = selection['source_id'], selection['passage_id']
        require_source(source_id)
        passage = next((item for item in views[source_id]['passages'] if item['passage_id'] == passage_id), None)
        if passage is None:
            raise CitationAssemblyError('Research selected a passage that does not exist in its captured source.')
        if (source_id, passage_id) in seen:
            continue
        seen.add((source_id, passage_id))
        findings.append({'finding_id': f'F{len(findings) + 1}', 'statement': passage['text'], 'source_ids': [source_id]})
    for candidate in model_result['company_candidates']:
        if not candidate['source_ids']:
            raise CitationAssemblyError('A proposed company must cite captured source evidence.')
        for source_id in candidate['source_ids']:
            require_source(source_id)
    for requirement in model_result['role_requirements']:
        if requirement['basis'] == 'OWNER_INTENT' and requirement['source_ids']:
            raise CitationAssemblyError('Owner intent must not claim a source citation.')
        if requirement['basis'] == 'SOURCE_EVIDENCE' and not requirement['source_ids']:
            raise CitationAssemblyError('An evidence-derived role requirement must cite a captured source.')
        for source_id in requirement['source_ids']:
            require_source(source_id)
    assembled = {key: deepcopy(value) for key, value in model_result.items() if key != 'findings'}
    assembled['sources'] = [
        {'source_id': source_id, 'url': evidence_by_source_id[source_id]['url'],
         'title': evidence_by_source_id[source_id]['title'],
         'observed_on': views[source_id]['observed_on'],
         'excerpt': evidence_by_source_id[source_id]['text'][:MAX_QUOTE_CHARACTERS]}
        for source_id in sorted(used, key=lambda value: int(value[1:]))
    ]
    assembled['findings'] = findings
    if list(Draft202012Validator(RESEARCH_SCHEMA).iter_errors(assembled)):
        raise CitationAssemblyError('The assembled citations do not satisfy the canonical research format.')
    return assembled
