"""Saved consent tests use mocked providers; they are not live ArmorIQ evidence."""
import time,os,unittest
from unittest.mock import patch,MagicMock
from types import SimpleNamespace
from fastapi.testclient import TestClient
import app
import assistant_permissions as permissions
from test_chat import model_reply

class SavedPermissionTests(unittest.TestCase):
    def setUp(self):
        self.user={'uid':'consent-'+str(time.time_ns()),'email':'synthetic@example.com','signed_in':True,'email_verified':True}
        app.app.dependency_overrides[app.identity]=lambda:self.user
        self.web=TestClient(app.app)
    def tearDown(self):
        app.discard_plans(self.user['uid']);app.app.dependency_overrides.clear();self.web.close()
    def save(self, mode='ask'):
        choices=permissions.defaults();choices['summarize_overdue_invoices']=mode
        return self.web.post('/api/assistant/permissions',json={'tools':choices,'consent':True})
    def ask(self):
        return self.web.post('/api/agent',json={'message':'Summarize my invoices','engine':'armoriq'})
    def provider(self):
        fake=MagicMock()
        fake.snapshot.return_value={};fake.flush.return_value={}
        fake.invoke.return_value=SimpleNamespace(status='success',verified=True,result={'overdue_invoice_count':3,'total_overdue_amount_inr':88000})
        return fake
    def env(self):
        return patch.dict(os.environ,{'ARMORIQ_API_KEY':'ak_test_unit_placeholder','ARMORIQ_EXPECTED_ORG_ID':'68c3541d-e2d8-462a-8393-243925a5ed23','ARMORIQ_AGENT_ID':'unit-agent','ARMORIQ_MCP_SERVER_ID':'2da563ef-544e-4db7-a418-0c404cf75180','MCP_SERVER_URL':'https://example.com/mcp','FINANCEGUARD_SCOPED_MCP':'1','FINANCEGUARD_MCP_SIGNING_KEY':'a'*48})
    def test_permission_profiles_are_owner_scoped_and_cannot_enable_financial_writes(self):
        self.assertEqual(self.save('automatic').status_code,200)
        self.assertEqual(self.web.get('/api/assistant/permissions').json()['tools']['summarize_overdue_invoices'],'automatic')
        self.user=dict(self.user,uid='other-'+self.user['uid'])
        self.assertFalse(self.web.get('/api/assistant/permissions').json()['configured'])
        tools=permissions.defaults()|{'simulate_refunds':'automatic'}
        self.assertEqual(self.web.post('/api/assistant/permissions',json={'tools':tools,'consent':True}).status_code,400)
        self.assertEqual(self.web.post('/api/assistant/permissions',json={'tools':permissions.defaults(),'consent':False}).status_code,422)
        self.user=dict(self.user,signed_in=False)
        self.assertEqual(self.web.get('/api/assistant/permissions').status_code,401)
    def test_standing_consent_still_calls_armoriq_and_reuses_current_plan(self):
        self.save('automatic');fake=self.provider()
        with self.env(),patch('app.ArmorIQWorkflow',return_value=fake) as factory,patch('mcp_access.invoke') as direct,patch('assistant_brain.complete',side_effect=[model_reply('summarize_overdue_invoices'),model_reply(text='Actual summary.'),model_reply('summarize_overdue_invoices'),model_reply(text='Actual summary.')]):
            for _ in range(2):
                result=self.ask().json();self.assertEqual(result['status'],'ALLOWED');self.assertTrue(result['actions'][0]['verified'])
            self.assertEqual(factory.call_count,1);self.assertEqual(fake.invoke.call_count,2);direct.assert_not_called()
    def test_provider_failure_does_not_fall_back_or_claim_success(self):
        self.save('automatic')
        with self.env(),patch('app.ArmorIQWorkflow',side_effect=RuntimeError('provider unavailable')),patch('mcp_access.invoke') as direct,patch('assistant_brain.complete',return_value=model_reply('summarize_overdue_invoices')):
            result=self.ask().json();self.assertEqual(result['status'],'ERROR');self.assertFalse(result['actions'][0]['verified']);direct.assert_not_called()
    def test_never_overrides_manual_plan_and_chat(self):
        self.web.post('/api/approve',json={});self.save('never')
        with patch('mcp_access.invoke') as direct,patch('app.ArmorIQWorkflow') as provider,patch('assistant_brain.complete',return_value=model_reply('summarize_overdue_invoices')):
            self.assertEqual(self.ask().json()['status'],'BLOCKED')
            self.assertEqual(self.web.post('/api/approve',json={}).json()['status'],'BLOCKED')
            direct.assert_not_called();provider.assert_not_called()
    def test_decline_is_single_use_and_never_calls_provider(self):
        with patch('assistant_brain.complete',return_value=model_reply('summarize_overdue_invoices')):
            result=self.ask().json()
        identifier=result['conversation']['pending']['id']
        with patch('app.ArmorIQWorkflow') as provider,patch('mcp_access.invoke') as direct:
            response=self.web.post('/api/chat/decline',json={'request_id':identifier}).json()
            self.assertEqual(response['status'],'DECLINED');self.assertIsNone(response['conversation']['pending'])
            self.assertEqual(self.web.post('/api/chat/approve',json={'request_id':identifier}).status_code,409)
            provider.assert_not_called();direct.assert_not_called()
    def test_revocation_removes_automatic_consent_and_pending_cards(self):
        self.save('automatic');self.web.post('/api/revoke',json={})
        with patch('app.ArmorIQWorkflow') as provider,patch('assistant_brain.complete',return_value=model_reply('summarize_overdue_invoices')):
            self.assertEqual(self.ask().json()['status'],'NEEDS_APPROVAL');provider.assert_not_called()
    def test_automatic_requires_verified_identity_and_cannot_use_local_engine(self):
        self.save('automatic')
        with patch('app.ArmorIQWorkflow') as provider,patch('mcp_access.invoke') as direct,patch('assistant_brain.complete',return_value=model_reply('summarize_overdue_invoices')):
            self.user=dict(self.user,email_verified=False)
            self.assertEqual(self.ask().status_code,403)
            self.user=dict(self.user,email_verified=True)
            result=self.web.post('/api/agent',json={'message':'Summary','engine':'local'}).json()
            self.assertEqual(result['status'],'ERROR');provider.assert_not_called();direct.assert_not_called()
    def test_native_hold_remains_held_and_never_runs_local_tool(self):
        from integration_errors import IntegrationError
        self.save('automatic');fake=self.provider()
        fake.invoke.side_effect=IntegrationError('Review in ArmorIQ Held Actions. Nothing executed.','policy_hold','policy',http_status=200)
        with self.env(),patch('app.ArmorIQWorkflow',return_value=fake),patch('mcp_access.invoke') as direct,patch('assistant_brain.complete',return_value=model_reply('summarize_overdue_invoices')):
            result=self.ask().json();self.assertEqual(result['status'],'HELD');self.assertFalse(result['actions'][0]['verified']);direct.assert_not_called()

    def test_changed_consent_version_refuses_auto_plan_inside_owner_lock(self):
        profile=self.save('automatic').json()
        self.save('never')
        with patch('app.ArmorIQWorkflow') as provider:
            with self.assertRaises(app.HTTPException):
                app.perform('summarize_overdue_invoices',self.user,'armoriq',approve=True,expected_consent_version=profile['updated_at'])
            provider.assert_not_called()
    def test_ask_always_prompts_even_with_an_existing_plan(self):
        self.save('ask');self.web.post('/api/approve',json={})
        with patch('mcp_access.invoke') as direct,patch('assistant_brain.complete',return_value=model_reply('summarize_overdue_invoices')):
            result=self.web.post('/api/agent',json={'message':'Summary','engine':'local'}).json()
            self.assertEqual(result['status'],'NEEDS_APPROVAL');direct.assert_not_called()
