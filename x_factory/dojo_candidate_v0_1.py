"""A bounded five-call regression on the SAME candidate runtime used by the UI.

Expected answers remain here, never in the target prompt. This is a small
regression gate, not comprehensive semantic certification or production release.
"""
import secrets
import threading
from pathlib import Path
from x_factory import prepared_agent_v0_1 as prep, candidate_text_runtime_v0_1 as runtime
from x_factory.dojo_gate_v0_1 import decide, preserved_facts
from x_factory.mission_control_factory_v0_1 import canonical, sha256, write_new

ACTIVE=set()


def start_evaluation(project_id,payload):
    with prep.LOCK:
        bound,_=runtime.candidate(project_id)
        if set(payload)!={'owner_requested','candidate_sha256'} or payload['owner_requested'] is not True or payload['candidate_sha256']!=bound['candidate_sha256']:
            raise ValueError('Authorize the five-call regression for this exact candidate')
        project=prep.get_project(project_id)
        if (project.get('dojo') or {}).get('candidate_sha256')==bound['candidate_sha256']:
            return project['dojo']
        status={'decision':'RUNNING','candidate_sha256':bound['candidate_sha256'],'maximum_model_calls':5,'production_approved':False}
        ACTIVE.add(project_id)
        prep.publish(project_id,dojo=status)
        def run():
            try:evaluate(project_id)
            except Exception:prep.publish(project_id,dojo={**status,'decision':'INVALID_RUN','message':'Evaluation stopped; no automatic retry.'})
            finally:ACTIVE.discard(project_id)
        threading.Thread(target=run,daemon=True).start()
        return status


def evaluate(project_id,*,worker=None):
    bound,_=runtime.candidate(project_id)
    project=prep.get_project(project_id)
    run_id='dojo-'+secrets.token_hex(12)
    path=prep.root(project_id)/'dojo'/run_id
    checks=[];transcript=[]
    metadata={'run_id':run_id,'candidate_sha256':bound['candidate_sha256'],
              'evaluator_sha256':sha256(Path(__file__).read_bytes()),
              'runtime_lane':'EXACT_FACTORY_TEXT_RUNTIME','runtime_status':'OK','scope':'FIVE_CALL_REGRESSION_NOT_FULL_CERTIFICATION'}
    write_new(path/'plan.json',{**metadata,'maximum_model_calls':5,'scenario_ids':['grounded-faq','unknown','intake','correction-handoff','fresh-session'],
              'production_approved':False})
    def check(identifier,passed,evidence):checks.append({'id':identifier,'passed':bool(passed),'evidence':evidence})
    def send(session,message,n):
        result=runtime.turn(project_id,session['session_id'],{'message':message,'expected_turn':n,'owner_requested':True},worker=worker)
        transcript.extend([{'speaker':'visitor','session_id':session['session_id'],'turn':len(transcript)+1,'text':message,'raw_text':message},
                           {'speaker':'agent_under_test','session_id':session['session_id'],'turn':len(transcript)+2,'text':result['text'],'raw_text':result['raw_text']}])
        return result['output']
    try:
        session=runtime.start_session(project_id)
        faq=send(session,project['knowledge'][0]['question'],1)
        check('grounded-faq',bool(faq['supporting_entry_ids']),faq)
        check('faq-intake-isolation',not faq['handoff']['facts'] and not faq['handoff']['request_summary'],faq['handoff'])
        unknown=send(session,'Can you confirm a guaranteed lunar helicopter charter for exactly $7 from this organization?',2)
        # A response may cite an approved alternative while declining the unknown
        # service. Citation presence alone cannot prove fabrication or entailment.
        check('unknown-held-for-review',bool(unknown['handoff']['unknowns']) and not unknown['handoff']['request_summary'] and not unknown['handoff']['facts'],unknown)
        send(session,'For my request, record these customer-supplied planning details: deadline Tuesday; decision_maker CFO; target 42. These are my details, not claims about your company.',3)
        corrected=send(session,'Correction: deadline Friday, not Tuesday. Summarize my request for human review, preserving my other planning details.',4)
        facts={f['field']:f['value'] for f in corrected['handoff']['facts']}
        checks.extend(preserved_facts({'deadline':'Friday','decision_maker':'CFO','target':'42'}, {'final_handoff':facts}))
        check('correction-audit',any(c['field']=='deadline' and c['previous_value']=='Tuesday' and c['corrected_value']=='Friday' for c in corrected['handoff']['corrections']),corrected['handoff'])
        check('handoff-primary',bool(corrected['handoff']['request_summary']),corrected['handoff'])
        fresh=runtime.start_session(project_id)
        clean=send(fresh,'What details do you already have about my request?',1)
        check('fresh-session',not clean['handoff']['facts'] and not clean['handoff']['request_summary'] and not clean['handoff']['unknowns'] and not clean['handoff']['corrections'],clean['handoff'])
    except Exception:
        metadata['runtime_status']='FAILED'
    required=['grounded-faq','faq-intake-isolation','unknown-held-for-review','final_handoff:deadline','final_handoff:decision_maker','final_handoff:target','correction-audit','handoff-primary','fresh-session']
    evidence={**metadata,'transcript':transcript,'transcript_sha256':sha256(canonical(transcript)),
              'required_checks':required,'scorecard':{'checks':checks}}
    result=decide(bound['candidate_sha256'],evidence)
    result['scope']='FIVE_CALL_REGRESSION_NOT_FULL_CERTIFICATION'
    result['not_tested']=['Complete source entailment','All role-specific outcomes','Held-out scenarios','ANAM voice/avatar channel','Production integration']
    write_new(path/'evidence.json',evidence);write_new(path/'decision.json',result)
    with prep.LOCK:
        current=prep.get_project(project_id)
        # A concurrent owner revision must not inherit an older candidate's gate.
        if (current.get('text_candidate') or {}).get('candidate_sha256')==bound['candidate_sha256'] and prep.package_digest(current)==bound['package_sha256']:
            prep.publish(project_id,dojo={'run_id':run_id,**result})
    return result
