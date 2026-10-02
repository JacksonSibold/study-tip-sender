import importlib.util,json,sys,tempfile,types,unittest
from pathlib import Path
from unittest.mock import patch
module=types.ModuleType('resend')
module.Emails=types.SimpleNamespace(send=lambda _: (_ for _ in ()).throw(AssertionError('Unexpected delivery')))
sys.modules['resend']=module
spec=importlib.util.spec_from_file_location('sender',Path(__file__).parents[1]/'main.py')
sender=importlib.util.module_from_spec(spec);spec.loader.exec_module(sender)
class SenderTests(unittest.TestCase):
 def test_corrupt_state_recovers_and_daily_reset_persists(self):
  with tempfile.TemporaryDirectory() as d, patch.object(sender,'STATE_FILE',Path(d)/'state.json'):
   sender.STATE_FILE.write_text('{broken')
   self.assertEqual(sender.load_state()['sent_slots'],[])
   result=sender.reset_state_if_new_day({'date':'old','sent_indices':[0],'sent_slots':['old 08']},'2027-05-01')
   self.assertEqual(result['sent_indices'],[])
   self.assertEqual(json.loads(sender.STATE_FILE.read_text())['date'],'2027-05-01')
 def test_selection_avoids_delivered_items_and_limits_message_length(self):
  i,msg=sender.pick_message(['already sent','x'*500],{'sent_indices':[0]})
  self.assertEqual(i,1); self.assertLessEqual(len(msg),320)
 def test_delivery_retries_are_bounded_and_backoff_is_offline(self):
  attempts=[];waits=[]
  def fail(_):attempts.append(1);raise RuntimeError('mock delivery failure')
  with patch.object(sender,'RESEND_API_KEY','test-only'),patch.object(module.Emails,'send',fail),patch.object(sender.time,'sleep',waits.append):
   self.assertFalse(sender.send_sms('test'))
  self.assertEqual(len(attempts),3);self.assertEqual(waits,[5,10])
 def test_missing_configuration_stops_before_delivery(self):
  with patch.object(sender,'PHONE_NUMBER',''),patch.object(sender,'RESEND_API_KEY',''):
   with self.assertRaises(SystemExit):sender.run()
if __name__=='__main__':unittest.main()
