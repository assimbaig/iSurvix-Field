"""AR-Q2 redaction contracts; every token below is synthetic and never printed."""
import io,logging,sys
from django.test import SimpleTestCase,RequestFactory
from .governance_logging import RedactInvitations

class RecoveryLoggingRedactionTests(SimpleTestCase):
 def setUp(self):
  self.token='9'*64
  self.path='/account/password-reset/12345678-1234-1234-1234-123456789ABC/'+self.token+'/'
 def formatted(self,record):
  RedactInvitations().filter(record);return logging.Formatter('%(levelname)s %(name)s %(message)s').format(record)
 def assert_private(self,text):self.assertFalse(self.token in text,'Synthetic recovery bearer was not redacted')
 def test_formatted_args_path_uppercase_uuid_and_query_keep_status_context(self):
  record=logging.LogRecord('django.server',logging.WARNING,__file__,1,'POST %s %s',(self.path+'?next=/safe&token='+self.token,403),None)
  result=self.formatted(record);self.assert_private(result);self.assertIn('POST',result);self.assertIn('403',result);self.assertIn('password-reset/',result);self.assertIn('[redacted]',result);self.assertIn('next=/safe',result)
 def test_exception_and_stack_text_redact_known_path_token_without_suppressing_error(self):
  try:raise ValueError('Synthetic failure for '+self.path+' echoed '+self.token)
  except ValueError:info=sys.exc_info()
  record=logging.LogRecord('django.request',logging.ERROR,__file__,1,'Failed request %s',(self.path,),info)
  record.stack_info='Trace context '+self.path
  result=self.formatted(record);self.assert_private(result);self.assertIn('ValueError',result);self.assertIn('Synthetic failure',result);self.assertIn('Traceback',result)
 def test_structured_request_path_is_private_without_mutating_live_request(self):
  request=RequestFactory().get(self.path+'?next=/safe')
  record=logging.LogRecord('django.security.csrf',logging.WARNING,__file__,1,'Forbidden (CSRF cookie not set.)',(),None)
  record.request=request;record.request_path=self.path
  RedactInvitations().filter(record)
  result=logging.Formatter('%(message)s %(request_path)s %(request)s').format(record)
  self.assert_private(result);self.assertEqual(request.path,self.path);self.assertIn('CSRF',result)
 def test_existing_invitation_redaction_and_ordinary_messages_remain(self):
  record=logging.LogRecord('django.server',logging.INFO,__file__,1,'GET %s 200',('/governance/invite/synthetic-invite-bearer/',),None)
  result=self.formatted(record);self.assertNotIn('synthetic-invite-bearer',result);self.assertIn('/governance/invite/[redacted]/',result)
  ordinary=logging.LogRecord('django.request',logging.WARNING,__file__,1,'Bad Request: %s %s',('/account/password-reset/',400),None)
  self.assertIn('Bad Request: /account/password-reset/ 400',self.formatted(ordinary))
