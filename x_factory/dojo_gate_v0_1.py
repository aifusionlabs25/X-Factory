"""Fail-closed candidate-bound Dojo gate; no legacy scorer or reply sanitizer.

Only the pinned, pure X-LINK global hard-rule function is reused. Customer
names never select historical agent-specific rules. No old repository is copied.
"""
import importlib.util
import re
from pathlib import Path
from x_factory.mission_control_factory_v0_1 import sha256, canonical

SOURCE = Path(r'C:\AI Fusion Labs\X AGENTS\REPOS\X-LINK\tools\xagent_eval\hard_rules.py')
SOURCE_SHA256 = 'c62f82ae7a29c2554caa471d73d0ef3d57a18d6a90eae41ce11609a846ad8701'


def hard_rules(transcript):
    if not SOURCE.is_file() or sha256(SOURCE.read_bytes()) != SOURCE_SHA256:
        raise ValueError('Pinned Dojo hard-rule source is unavailable or changed; evaluation cannot pass')
    spec = importlib.util.spec_from_file_location('factory_pinned_dojo_rules', SOURCE)
    module = importlib.util.module_from_spec(spec)
    # Do not generate caches or import the historical runner or model stack.
    exec(compile(SOURCE.read_bytes(), str(SOURCE), 'exec'), module.__dict__)
    findings = []
    sessions={t.get('session_id','default') for t in transcript}
    for session in sessions:
        for lane in ('raw_text', 'text'):
            turns = [{**t, 'text': t.get(lane, '')} for t in transcript if t.get('session_id','default')==session]
            result = module.evaluate_hard_rules(agent_slug='factory-generic', transcript=turns)
            findings += [{**f, 'output_lane': lane,'session_id':session} for f in result['findings']]
    return findings


def decide(candidate_sha256, run):
    """No scorecard, incomplete capture, runtime failure or hash drift can pass."""
    invalid = []
    if not isinstance(run, dict):
        return {'decision':'INVALID_RUN','reasons':['Missing run evidence'],'production_approved':False}
    if not re.fullmatch(r'[a-f0-9]{64}',str(candidate_sha256)) or run.get('candidate_sha256') != candidate_sha256:
        invalid.append('Candidate binding is missing or changed')
    if run.get('runtime_status') != 'OK': invalid.append('Runtime did not complete cleanly')
    if run.get('runtime_lane') not in {'EXACT_FACTORY_TEXT_RUNTIME', 'LOCAL_DETERMINISTIC_PREVIEW'}:
        invalid.append('Runtime fidelity is not established')
    transcript = run.get('transcript')
    if not isinstance(transcript,list) or not transcript:
        invalid.append('Missing transcript'); transcript=[]
    agents = [t for t in transcript if isinstance(t,dict) and t.get('speaker')=='agent_under_test']
    if not agents or any(not isinstance(t.get(k),str) or not t[k].strip() for t in agents for k in ('raw_text','text')):
        invalid.append('Both raw and delivered agent output are required')
    if any(re.search(r'\[ERROR\]|connection failed|traceback', t.get('raw_text',''), re.I) for t in agents):
        invalid.append('Runtime error text is not a valid agent answer')
    if run.get('transcript_sha256') != sha256(canonical(transcript)):
        invalid.append('Transcript hash is missing or changed')
    scorecard = run.get('scorecard')
    plan = run.get('required_checks')
    if not isinstance(plan,list) or not plan or len(set(plan)) != len(plan):
        invalid.append('An explicit, unique test plan is required');plan=[]
    checks = scorecard.get('checks') if isinstance(scorecard,dict) else None
    if not isinstance(checks,list) or {c.get('id') for c in checks if isinstance(c,dict)} != set(plan) or len(checks) != len(plan):
        invalid.append('Scorecard is missing or does not cover the complete test plan');checks=[]
    if any(not isinstance(c.get('passed'),bool) or not c.get('evidence') for c in checks):
        invalid.append('Every score requires an explicit result and evidence')
    if invalid:
        return {'decision':'INVALID_RUN','reasons':invalid,'production_approved':False}
    try:
        findings=hard_rules(transcript)
    except ValueError as error:
        return {'decision':'INVALID_RUN','reasons':[str(error)],'production_approved':False}
    failed=[c['id'] for c in checks if not c['passed']]
    blocked=any(f['severity']=='BLOCK_RELEASE' for f in findings)
    # Legacy lexical flags can also fire on a refusal quoting a visitor's price.
    # Retain every raw finding and block clearance; never silently waive it.
    return {'decision':'FAIL' if failed else 'REVIEW_REQUIRED' if blocked else 'PASS_FOR_TESTED_LANE',
            'scope':run['runtime_lane'], 'failed_checks':failed, 'findings':findings,
            'candidate_sha256':candidate_sha256,'source_sha256':SOURCE_SHA256,
            'production_approved':False,'anam_validated':False}


def preserved_facts(expected, artifacts):
    """Check final artifacts, not words that appear only in the user's turns."""
    return [{'id':f'{name}:{key}', 'passed': artifact.get(key)==value,
             'evidence': {'expected':value,'actual':artifact.get(key)}}
            for name,artifact in artifacts.items() for key,value in expected.items()]
