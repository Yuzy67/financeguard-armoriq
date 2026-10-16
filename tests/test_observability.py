"""SDK instrumentation contracts with mocked provider HTTP; not live cloud evidence."""
import json,os,time,unittest
from types import SimpleNamespace
from unittest.mock import patch
import httpx
from armoriq_sdk import ArmorIQClient
from armoriq_sdk.models import IntentToken
from armoriq_sdk.exceptions import IntentMismatchException
from armoriq_workflow import ArmorIQWorkflow,ConfigurationError,TARGET_ORG

class ObservabilityTests(unittest.TestCase):
    def setUp(self):
        self.batches=[];self.status=200;self.policy_status=200;self.policy_allowed=True
        self.env=patch.dict(os.environ,{'ARMORIQ_API_KEY':'ak_test_unit_test_placeholder','ARMORIQ_EXPECTED_ORG_ID':TARGET_ORG,'MCP_SERVER_URL':'https://mcp.example/mcp','ARMORIQ_OBSERVABILITY':'true'})
        self.env.start()
        self.client=ArmorIQClient(api_key='ak_test_unit_test_placeholder',user_id='test-operator',agent_id='test-agent',_skip_api_key_validation=True)
        self.client.http_client.close()
        def respond(request):
            if request.url.path.endswith('/iap/sdk/enforce'):return httpx.Response(self.policy_status,json={'allowed':self.policy_allowed})
            if request.url.path.endswith('/iap/audit'):return httpx.Response(200,json={})
            if request.url.path.endswith('/observability/spans'):
                payload=json.loads(request.content);self.batches.extend(payload['batches'])
                return httpx.Response(self.status,json={'accepted':len(payload['batches']),'rejected':0})
            raise AssertionError('Unexpected network request in unit test: '+request.url.path)
        self.client.http_client=httpx.Client(transport=httpx.MockTransport(respond))
        token=IntentToken(token_id='unit-token',plan_hash='test-hash',signature='test-signature',issued_at=time.time(),expires_at=time.time()+300,composite_identity='test',raw_token={'plan':{'steps':[{'mcp':'finance-mcp','action':'summarize_overdue_invoices','params':{}}]}})
        self.bootstrap=patch.object(self.client,'bootstrap',return_value={'org':{'orgId':TARGET_ORG}});self.bootstrap.start()
        self.registry=patch.object(self.client,'list_mcps',return_value=[{'name':'finance-mcp','url':'https://mcp.example/mcp'}]);self.registry.start()
        self.token=patch.object(self.client,'get_intent_token',return_value=token);self.token.start()
        original=self.client.invoke
        def invoke(mcp,action,*args,**kwargs):
            if action=='simulate_refunds':return original(mcp,action,*args,**kwargs)
            return SimpleNamespace(status='success',verified=True,result={'overdue_invoice_count':3})
        self.invoke=patch.object(self.client,'invoke',side_effect=invoke);self.invoke.start()
        self.factory=patch('armoriq_sdk.ArmorIQClient',return_value=self.client);self.factory.start()
        self.workflow=None
    def tearDown(self):
        if self.workflow:self.workflow.close()
        else:self.client.close()
        for item in [self.factory,self.invoke,self.token,self.registry,self.bootstrap,self.env]:item.stop()
    def start(self):
        self.workflow=ArmorIQWorkflow('summarize_overdue_invoices','scoped-test-credential')
        return self.workflow
    def test_plan_allow_tool_deny_and_ingestion_receipt(self):
        workflow=self.start()
        workflow.invoke('summarize_overdue_invoices',{},'demo@example.com')
        with self.assertRaises(IntentMismatchException):workflow.invoke('simulate_refunds',{'invoice_id':'demo-invoice'},'demo@example.com')
        evidence=workflow.flush()
        self.assertEqual(evidence['delivery'],'accepted');self.assertGreater(evidence['accepted'],0)
        self.assertFalse(evidence['console_verified'])
        spans=[s for b in self.batches for s in b['spans']]
        decisions=[s['attributes']['decision'] for s in spans if s['kind']=='policy_call']
        self.assertIn('allow',decisions);self.assertIn('deny',decisions)
        self.assertIn('tool.report',[s['name'] for s in spans])
        self.assertEqual(len(self.batches),1)
        self.assertNotIn('scoped-test-credential',json.dumps(self.batches))
    def test_rejected_telemetry_never_becomes_success(self):
        self.status=403;workflow=self.start()
        result=workflow.invoke('summarize_overdue_invoices',{},'demo@example.com')
        self.assertTrue(result.verified)
        evidence=workflow.flush()
        self.assertEqual(evidence['delivery'],'rejected');self.assertEqual(evidence['accepted'],0)
    def test_wrong_organization_refuses_plan(self):
        self.client.bootstrap.return_value={'org':{'orgId':'another-org'}}
        with self.assertRaises(ConfigurationError):self.start()
        self.client.get_intent_token.assert_not_called()
    def test_stale_registration_refuses_plan(self):
        self.client.list_mcps.return_value=[{'name':'finance-mcp','url':'https://old.example/mcp'}]
        with self.assertRaises(ConfigurationError):self.start()
        self.client.get_intent_token.assert_not_called()
    def test_flush_preserves_session_correlation(self):
        workflow=self.start();first=workflow.flush()
        with self.assertRaises(IntentMismatchException):workflow.invoke('simulate_refunds',{},'demo@example.com')
        second=workflow.flush()
        self.assertEqual(first['session_id'],second['session_id'])
        self.assertEqual(len(second['trace_ids']),2)



    def test_policy_outage_is_an_error_without_tool_execution(self):
        self.policy_status=503;workflow=self.start()
        with self.assertRaises(RuntimeError):workflow.invoke('summarize_overdue_invoices',{},'demo@example.com')
        self.client.invoke.assert_not_called()
    def test_cloud_policy_denial_stops_execution(self):
        from armoriq_workflow import ActionDenied
        self.policy_allowed=False;workflow=self.start()
        with self.assertRaises(ActionDenied):workflow.invoke('summarize_overdue_invoices',{},'demo@example.com')
        self.client.invoke.assert_not_called()
