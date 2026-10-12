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
class ContentTests(unittest.TestCase):
 def _write_content(self,d,data):
  path=Path(d)/'content.json'
  path.write_text(json.dumps(data),encoding='utf-8')
  return path
 def test_all_content_categories_are_formatted(self):
  data={'tips':['Rest'],'concepts':['Cache'],'definitions':[{'term':'T','definition':'D'}],'questions':[{'q':'Why?','a':'Because'}]}
  with tempfile.TemporaryDirectory() as d, patch.object(sender,'CONTENT_FILE',self._write_content(d,data)):
   self.assertEqual(sender.load_content(),['Tip: Rest','Concept: Cache','Def: T - D','Q: Why? A: Because'])
 def test_missing_categories_default_to_empty_list(self):
  with tempfile.TemporaryDirectory() as d, patch.object(sender,'CONTENT_FILE',self._write_content(d,{'tips':['Only']})):
   self.assertEqual(sender.load_content(),['Tip: Only'])
 def test_missing_content_file_raises(self):
  with tempfile.TemporaryDirectory() as d, patch.object(sender,'CONTENT_FILE',Path(d)/'absent.json'):
   with self.assertRaises(FileNotFoundError):sender.load_content()
class SelectionTests(unittest.TestCase):
 def test_pool_recycles_when_every_item_was_already_used(self):
  state={'sent_indices':[0,1]}
  with patch.object(sender.random,'choice',lambda seq:seq[0]):
   idx,msg=sender.pick_message(['a','b'],state)
  self.assertEqual((idx,msg),(0,'a'))
  self.assertEqual(state['sent_indices'],[])
 def test_message_at_exact_limit_is_not_truncated(self):
  text='x'*320
  _,msg=sender.pick_message([text],{})
  self.assertEqual(msg,text)
 def test_message_one_over_limit_is_truncated_with_ellipsis(self):
  _,msg=sender.pick_message(['x'*321],{})
  self.assertEqual(len(msg),320)
  self.assertTrue(msg.endswith('...'))
class DeliveryTests(unittest.TestCase):
 def test_transient_failure_then_success_returns_true_after_one_backoff(self):
  calls=[];waits=[]
  def flaky(_):
   calls.append(1)
   if len(calls)==1:raise RuntimeError('temporary')
   return {'id':'msg-1'}
  with patch.object(sender,'RESEND_API_KEY','test-only'),patch.object(module.Emails,'send',flaky),patch.object(sender.time,'sleep',waits.append):
   self.assertTrue(sender.send_sms('hello'))
  self.assertEqual(len(calls),2);self.assertEqual(waits,[5])
 def test_missing_api_key_fails_without_calling_sdk(self):
  calls=[]
  with patch.object(sender,'RESEND_API_KEY',''),patch.object(module.Emails,'send',lambda p:calls.append(p)):
   self.assertFalse(sender.send_sms('hello'))
  self.assertEqual(calls,[])
class StateTests(unittest.TestCase):
 def test_missing_state_file_returns_empty_defaults(self):
  with tempfile.TemporaryDirectory() as d, patch.object(sender,'STATE_FILE',Path(d)/'none.json'):
   self.assertEqual(sender.load_state(),{'date':'','sent_indices':[],'sent_slots':[]})
 def test_save_failure_logs_warning_instead_of_raising(self):
  import io,contextlib
  with tempfile.TemporaryDirectory() as d, patch.object(sender,'STATE_FILE',Path(d)),io.StringIO() as buf,contextlib.redirect_stdout(buf):
   sender.save_state({'date':'x','sent_indices':[],'sent_slots':[]})
   self.assertIn('WARN: failed to save state',buf.getvalue())
 def test_same_day_state_is_returned_unchanged_without_writing(self):
  with tempfile.TemporaryDirectory() as d, patch.object(sender,'STATE_FILE',Path(d)/'state.json'):
   state={'date':'2027-05-01','sent_indices':[2],'sent_slots':['2027-05-01 08']}
   self.assertIs(sender.reset_state_if_new_day(state,'2027-05-01'),state)
   self.assertFalse(sender.STATE_FILE.exists())
if __name__=='__main__':unittest.main()
