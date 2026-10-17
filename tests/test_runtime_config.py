import json,os,unittest
from unittest.mock import patch
import httpx
from runtime_config import armoriq_configuration,require_armoriq_configuration
from integration_errors import classify,ConfigurationError

class ConfigurationTests(unittest.TestCase):
    def test_literal_secret_is_invalid_not_configured(self):
        with patch.dict(os.environ,{'ARMORIQ_API_KEY':'Secret'},clear=True):
            result=armoriq_configuration()
            self.assertEqual(result['checks'][0]['status'],'invalid')
            with self.assertRaises(ConfigurationError):require_armoriq_configuration()
    def test_diagnostics_do_not_contain_credentials(self):
        key='ak_test_private_test_marker'
        with patch.dict(os.environ,{'ARMORIQ_AGENT_ID':'test-agent','ARMORIQ_MCP_SERVER_ID':'2da563ef-544e-4db7-a418-0c404cf75180','ARMORIQ_API_KEY':key,'ARMORIQ_EXPECTED_ORG_ID':'68c3541d-e2d8-462a-8393-243925a5ed23','MCP_SERVER_URL':'https://example.com/mcp','VERCEL':'1','FINANCEGUARD_SCOPED_MCP':'1','FINANCEGUARD_MCP_SIGNING_KEY':'s'*48},clear=True):
            result=armoriq_configuration()
            self.assertEqual(result['configuration_status'],'configured')
            self.assertEqual(result['execution'],'not_verified')
            self.assertNotIn(key,json.dumps(result));self.assertNotIn('s'*48,json.dumps(result))
    def test_wrong_names_do_not_satisfy_configuration(self):
        with patch.dict(os.environ,{'ARMORIQ_CLIENT_KEY':'placeholder','ARMORIQ_ORG_ID':'placeholder'},clear=True):
            self.assertEqual(armoriq_configuration()['checks'][0]['status'],'missing')
    def test_provider_body_is_never_returned(self):
        request=httpx.Request('GET','https://api.armoriq.ai')
        response=httpx.Response(401,text='secret-body',request=request)
        result=classify(httpx.HTTPStatusError('secret-body',request=request,response=response))
        self.assertEqual(result['category'],'authentication');self.assertNotIn('secret-body',json.dumps(result))
        self.assertEqual(classify(httpx.ReadTimeout('secret-body'))['category'],'network')
        self.assertNotIn('secret-body',json.dumps(classify(RuntimeError('secret-body'))))

    def test_sdk_validation_error_does_not_invent_http_status(self):
        from armoriq_sdk.exceptions import ConfigurationException
        error=classify(ConfigurationException('Invalid or revoked API key.'))
        self.assertIsNone(error['provider_status'])
        self.assertEqual(error['code'],'sdk_authentication_check_failed')
    def test_html_403_is_not_proof_of_a_revoked_credential(self):
        request=httpx.Request('POST','https://api.armoriq.ai/iap/sdk/bootstrap')
        response=httpx.Response(403,headers={'content-type':'text/html'},text='private response',request=request)
        error=classify(httpx.HTTPStatusError('private response',request=request,response=response))
        self.assertEqual(error['code'],'service_access_denied');self.assertEqual(error['provider_status'],403)
        self.assertNotIn('private response',json.dumps(error))
