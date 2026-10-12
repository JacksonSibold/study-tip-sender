import importlib.util,json,sys,tempfile,types,unittest
from datetime import datetime
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
 def test_top_level_must_be_an_object(self):
  with tempfile.TemporaryDirectory() as d, patch.object(sender,'CONTENT_FILE',Path(d)/'c.json'):
   sender.CONTENT_FILE.write_text('[]',encoding='utf-8')
   with self.assertRaises(ValueError):sender.load_content()
 def test_tips_and_concepts_must_be_lists_of_text(self):
  bad=[{'tips':'one'},{'tips':[123]},{'concepts':['']},{'concepts':[None]}]
  for data in bad:
   with self.subTest(data=data),tempfile.TemporaryDirectory() as d,patch.object(sender,'CONTENT_FILE',self._write_content(d,data)):
    with self.assertRaises(ValueError):sender.load_content()
 def test_definitions_and_questions_require_their_fields(self):
  bad=[{'definitions':[{'term':'T'}]},{'definitions':['T - D']},{'questions':[{'q':'Q?'}]},{'questions':[{'q':'Q?','a':''}]}]
  for data in bad:
   with self.subTest(data=data),tempfile.TemporaryDirectory() as d,patch.object(sender,'CONTENT_FILE',self._write_content(d,data)):
    with self.assertRaises(ValueError):sender.load_content()
 def test_content_with_no_entries_is_rejected(self):
  for data in ({},{'tips':[]}):
   with self.subTest(data=data),tempfile.TemporaryDirectory() as d,patch.object(sender,'CONTENT_FILE',self._write_content(d,data)):
    with self.assertRaises(ValueError):sender.load_content()
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
 def test_non_object_state_file_is_treated_as_empty(self):
  with tempfile.TemporaryDirectory() as d, patch.object(sender,'STATE_FILE',Path(d)/'state.json'):
   for raw in ('[]','"text"','null'):
    sender.STATE_FILE.write_text(raw)
    self.assertEqual(sender.load_state(),{'date':'','sent_indices':[],'sent_slots':[]},raw)
 def test_partial_state_is_filled_with_defaults(self):
  with tempfile.TemporaryDirectory() as d, patch.object(sender,'STATE_FILE',Path(d)/'state.json'):
   sender.STATE_FILE.write_text('{"date": "2027-05-01"}')
   self.assertEqual(sender.load_state(),{'date':'2027-05-01','sent_indices':[],'sent_slots':[]})
 def test_wrong_typed_lists_are_replaced_with_empty_lists(self):
  with tempfile.TemporaryDirectory() as d, patch.object(sender,'STATE_FILE',Path(d)/'state.json'):
   sender.STATE_FILE.write_text('{"date":"2027-05-01","sent_indices":"oops","sent_slots":null}')
   self.assertEqual(sender.load_state(),{'date':'2027-05-01','sent_indices':[],'sent_slots':[]})
 def test_interrupted_save_keeps_previous_state_intact(self):
  import io,contextlib
  with tempfile.TemporaryDirectory() as d, patch.object(sender,'STATE_FILE',Path(d)/'state.json'):
   old={'date':'2027-05-01','sent_indices':[0],'sent_slots':['2027-05-01 08']}
   sender.save_state(old)
   def partial_dump(obj,fp,**kwargs):
    fp.write('{"date": "2027-05');raise OSError('disk full')
   with patch.object(sender.json,'dump',partial_dump),contextlib.redirect_stdout(io.StringIO()):
    sender.save_state({'date':'2027-05-01','sent_indices':[0,1],'sent_slots':[]})
   self.assertEqual(json.loads(sender.STATE_FILE.read_text(encoding='utf-8')),old)
   self.assertEqual(sorted(p.name for p in Path(d).iterdir()),['state.json'])
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
class SlotTests(unittest.TestCase):
 def setUp(self):
  self._dir=tempfile.TemporaryDirectory()
  self.addCleanup(self._dir.cleanup)
  patcher=patch.object(sender,'STATE_FILE',Path(self._dir.name)/'state.json')
  patcher.start();self.addCleanup(patcher.stop)
 def _state(self):
  return {'date':'2026-10-12','sent_indices':[],'sent_slots':[]}
 def test_sends_once_at_top_of_a_send_hour_and_records_the_slot(self):
  state=self._state();now=datetime(2026,10,12,10,0,tzinfo=sender.MT)
  with patch.object(sender,'send_sms',return_value=True) as send:
   self.assertTrue(sender.dispatch_due_slot(state,['a','b'],now))
   self.assertFalse(sender.dispatch_due_slot(state,['a','b'],now))
  self.assertEqual(send.call_count,1)
  self.assertEqual(state['sent_slots'],['2026-10-12 10'])
  self.assertEqual(len(state['sent_indices']),1)
 def test_no_send_outside_send_hours_or_off_the_minute(self):
  for now in (datetime(2026,10,12,9,0,tzinfo=sender.MT),datetime(2026,10,12,10,1,tzinfo=sender.MT)):
   with self.subTest(now=now),patch.object(sender,'send_sms',return_value=True) as send:
    self.assertFalse(sender.dispatch_due_slot(self._state(),['a'],now))
    send.assert_not_called()
 def test_failed_send_does_not_record_the_slot(self):
  import io,contextlib
  state=self._state();now=datetime(2026,10,12,12,0,tzinfo=sender.MT)
  out=io.StringIO()
  with patch.object(sender,'send_sms',return_value=False),contextlib.redirect_stdout(out):
   self.assertFalse(sender.dispatch_due_slot(state,['a'],now))
  self.assertIn('will not be retried this hour',out.getvalue())
  self.assertEqual(state['sent_slots'],[])
  self.assertEqual(state['sent_indices'],[])
class RunTests(unittest.TestCase):
 def test_phone_number_must_be_digits_only(self):
  for phone in ('+15555550100','555-0100','1555 0100'):
   with self.subTest(phone=phone),tempfile.TemporaryDirectory() as d,patch.object(sender,'PHONE_NUMBER',phone),patch.object(sender,'RESEND_API_KEY','test-only'),patch.object(sender,'STATE_FILE',Path(d)/'s.json'),patch.object(sender,'load_content',lambda:['x']),patch.object(sender.time,'sleep',side_effect=KeyboardInterrupt):
    with self.assertRaises(SystemExit) as cm:sender.run()
    self.assertIn('PHONE_NUMBER',str(cm.exception.code))
 def test_unloadable_content_exits_with_nonzero_status(self):
  with tempfile.TemporaryDirectory() as d,patch.object(sender,'PHONE_NUMBER','15555550100'),patch.object(sender,'RESEND_API_KEY','test-only'),patch.object(sender,'CONTENT_FILE',Path(d)/'missing.json'):
   with self.assertRaises(SystemExit) as cm:sender.run()
  self.assertNotEqual(cm.exception.code,0)
class DryRunTests(unittest.TestCase):
 def setUp(self):
  import io,contextlib
  self._dir=tempfile.TemporaryDirectory()
  self.addCleanup(self._dir.cleanup)
  self.state_file=Path(self._dir.name)/'sent_state.json'
  content=Path(self._dir.name)/'content.json'
  content.write_text(json.dumps({'tips':['Only tip']}),encoding='utf-8')
  self.content_file=content
  for name,value in (('STATE_FILE',self.state_file),('CONTENT_FILE',content),('PHONE_NUMBER','15555550100'),('RESEND_API_KEY',''),('TO_ADDRESS','15555550100@tmomail.net')):
   patcher=patch.object(sender,name,value);patcher.start();self.addCleanup(patcher.stop)
  for target in (patch.object(sender,'send_sms',side_effect=AssertionError('dry run must not send')),patch.object(module.Emails,'send',side_effect=AssertionError('dry run must not send'))):
   target.start();self.addCleanup(target.stop)
  self.out=io.StringIO()
  self._redirect=contextlib.redirect_stdout(self.out);self._redirect.__enter__();self.addCleanup(self._redirect.__exit__,None,None,None)
 def test_prints_the_next_message_and_recipient_without_sending(self):
  sender.main(['--dry-run'])
  output=self.out.getvalue()
  self.assertIn('DRY RUN',output)
  self.assertIn('Tip: Only tip',output)
  self.assertIn('15555550100@tmomail.net',output)
 def test_does_not_create_or_change_the_state_file(self):
  sender.main(['--dry-run'])
  self.assertFalse(self.state_file.exists())
  stale={'date':'2000-01-01','sent_indices':[0],'sent_slots':['2000-01-01 08']}
  self.state_file.write_text(json.dumps(stale))
  before=self.state_file.read_text()
  sender.main(['--dry-run'])
  self.assertEqual(self.state_file.read_text(),before)
 def test_does_not_mark_slots_or_indices_as_sent(self):
  today=datetime.now(sender.MT).strftime('%Y-%m-%d')
  state={'date':today,'sent_indices':[],'sent_slots':[]}
  self.state_file.write_text(json.dumps(state))
  sender.main(['--dry-run'])
  self.assertEqual(json.loads(self.state_file.read_text()),state)
 def test_does_not_require_an_api_key(self):
  with patch.object(sender,'RESEND_API_KEY',''):
   sender.main(['--dry-run'])
  self.assertIn('DRY RUN',self.out.getvalue())
 def test_malformed_phone_number_is_rejected(self):
  with patch.object(sender,'PHONE_NUMBER','+15555550100'),self.assertRaises(SystemExit):
   sender.main(['--dry-run'])
 def test_missing_phone_number_is_rejected(self):
  with patch.object(sender,'PHONE_NUMBER',''),self.assertRaises(SystemExit):
   sender.main(['--dry-run'])
 def test_unloadable_content_exits_with_nonzero_status(self):
  with patch.object(sender,'CONTENT_FILE',Path(self._dir.name)/'missing.json'),self.assertRaises(SystemExit) as cm:
   sender.main(['--dry-run'])
  self.assertNotEqual(cm.exception.code,0)
class ArgumentTests(unittest.TestCase):
 def test_without_flag_main_starts_the_scheduler(self):
  with patch.object(sender,'run') as run,patch.object(sender,'dry_run') as dry:
   sender.main([])
  run.assert_called_once_with();dry.assert_not_called()
 def test_dry_run_flag_selects_dry_run_mode(self):
  with patch.object(sender,'run') as run,patch.object(sender,'dry_run') as dry:
   sender.main(['--dry-run'])
  dry.assert_called_once_with();run.assert_not_called()
if __name__=='__main__':unittest.main()
