import sys
import unittest
from pathlib import Path
from copy import deepcopy
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from x_factory.dojo_gate_v0_1 import decide, preserved_facts
from x_factory.mission_control_factory_v0_1 import canonical, sha256

class DojoGateTests(unittest.TestCase):
    def sample(self):
        transcript=[{'speaker':'agent_under_test','turn':1,'raw_text':'I can prepare a local review summary.','text':'I can prepare a local review summary.'}]
        return {'candidate_sha256':'a'*64,'runtime_status':'OK','runtime_lane':'EXACT_FACTORY_TEXT_RUNTIME',
                'transcript':transcript,'transcript_sha256':sha256(canonical(transcript)),
                'required_checks':['handoff'],'scorecard':{'checks':[{'id':'handoff','passed':True,'evidence':'Exact returned handoff retained the customer problem.'}]}}
    def test_valid_evidence_is_scoped_not_production(self):
        result=decide('a'*64,self.sample());self.assertEqual(result['decision'],'PASS_FOR_TESTED_LANE');self.assertFalse(result['production_approved'])
    def test_missing_score_runtime_failure_hash_drift_cannot_pass(self):
        for key,value in [('scorecard',None),('runtime_status','FAILED'),('candidate_sha256','b'*64),('transcript_sha256',None),('required_checks',[])]:
            run=self.sample();run[key]=value
            self.assertEqual(decide('a'*64,run)['decision'],'INVALID_RUN',key)
    def test_error_response_is_invalid_not_agent_failure(self):
        run=self.sample();run['transcript'][0].update(raw_text='[ERROR] Connection failed',text='[ERROR] Connection failed')
        run['transcript_sha256']=sha256(canonical(run['transcript']))
        self.assertEqual(decide('a'*64,run)['decision'],'INVALID_RUN')
    def test_user_words_do_not_prove_downstream_facts(self):
        checks=preserved_facts({'deadline':'Friday','decision_maker':'CFO','target':42}, {'summary':{'deadline':'Friday'},'email':{}})
        self.assertEqual(sum(c['passed'] for c in checks),1)
        run=self.sample();run['required_checks']=[c['id'] for c in checks];run['scorecard']={'checks':checks}
        self.assertEqual(decide('a'*64,run)['decision'],'FAIL')
    def test_missing_raw_output_cannot_be_hidden_by_delivered_text(self):
        run=self.sample();del run['transcript'][0]['raw_text'];run['transcript_sha256']=sha256(canonical(run['transcript']))
        self.assertEqual(decide('a'*64,run)['decision'],'INVALID_RUN')
    def test_lexical_price_flag_is_retained_for_review_not_silently_waived(self):
        run=self.sample()
        refusal='I cannot confirm a guaranteed $7 price. Ask the responsible team to verify pricing.'
        run['transcript'][0].update(raw_text=refusal,text=refusal)
        run['transcript_sha256']=sha256(canonical(run['transcript']))
        result=decide('a'*64,run)
        self.assertEqual(result['decision'],'REVIEW_REQUIRED');self.assertTrue(result['findings'])
if __name__=='__main__':unittest.main(verbosity=2)
