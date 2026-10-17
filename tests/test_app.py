import os,tempfile,unittest,time
os.environ['FINANCEGUARD_RUNTIME']=tempfile.mkdtemp(prefix='financeguard-tests-')
from unittest.mock import patch
from fastapi.testclient import TestClient
import app as module
import workspace

class WorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.shared=TestClient(module.app,base_url='http://127.0.0.1:8001')
        cls.shared.__enter__()
    @classmethod
    def tearDownClass(cls):cls.shared.__exit__(None,None,None)
    def setUp(self):
        self.web=self.shared
        self.web.cookies.clear()
        def invoke(tool,token):
            response=self.web.post('/mcp',headers={'Authorization':'Bearer '+token,'Accept':'application/json, text/event-stream'},json={'jsonrpc':'2.0','id':1,'method':'tools/call','params':{'name':tool,'arguments':{}}})
            result=response.json()['result']
            if result.get('isError'):raise RuntimeError('MCP rejected test invocation.')
            return __import__('json').loads(result['content'][0]['text'])
        self.transport=patch('mcp_access.invoke',side_effect=invoke)
        self.transport.start()
        self.user={'uid':'user-'+str(time.time_ns()),'email':'test@example.com','email_verified':True,'signed_in':True}
        module.app.dependency_overrides[module.identity]=lambda:self.user
    def tearDown(self):
        self.transport.stop();module.app.dependency_overrides.clear()
    def post(self,path,data):return self.web.post(path,json=data)
    def test_guest_and_auth_boundary(self):
        module.app.dependency_overrides.clear()
        self.assertEqual(self.web.get('/api/state').status_code,401)
        self.assertEqual(self.post('/api/demo',{}).status_code,200)
        self.assertEqual(self.web.get('/api/state').json()['source'],'sample')
        self.assertEqual(self.post('/api/import',{'csv':'anything'}).status_code,401)
        self.assertEqual(self.web.get('/api/state',headers={'Authorization':'Bearer fake'}).status_code,401)
        self.assertEqual(self.web.post('/api/demo',headers={'Origin':'https://evil.example'}).status_code,403)
    def test_scoped_import_and_plan_invalidation(self):
        csv='invoice_id,customer_name,amount_inr,due_date,status\nA,Example,123.45,2020-01-01,unpaid\n'
        self.assertEqual(self.post('/api/import',{'csv':csv}).json()['count'],1)
        self.assertEqual(self.web.get('/api/state').json()['source'],'sample')
        self.post('/api/approve',{})
        self.assertTrue(self.post('/api/import',{'csv':csv,'confirm':True}).json()['saved'])
        self.assertEqual(self.post('/api/execute',{}).status_code,409)
        self.post('/api/approve',{})
        result=self.post('/api/command',{'message':'summarize overdue invoices'}).json()
        self.assertEqual(result['result']['total_overdue_amount_inr'],123.45)
        self.assertFalse(result['verified'])
        before=self.web.get('/api/state').json()['invoices']
        for tool in ['simulate_refunds','transfer_funds','delete_invoices']:
            self.assertEqual(self.post('/api/execute',{'tool':tool}).json()['status'],'BLOCKED')
        self.assertEqual(before,self.web.get('/api/state').json()['invoices'])
        self.user=dict(self.user,uid='another-user-'+str(time.time_ns()))
        state=self.web.get('/api/state').json()
        self.assertEqual(state['source'],'sample');self.assertEqual(state['events'],[]);self.assertEqual(state['plans'],{})
    def test_validation(self):
        header='invoice_id,customer_name,amount_inr,due_date,status\n'
        for invalid in ['NaN','-1','1.001','Infinity']:
            self.assertEqual(self.post('/api/import',{'csv':header+f'A,Name,{invalid},2020-01-01,unpaid\n'}).status_code,400)
        self.assertEqual(self.post('/api/import',{'csv':header+'A,Name,1,2020-01-01,paid\nA,Name,1,2020-01-01,paid\n'}).status_code,400)
    def test_drafts_and_reports_need_their_own_plan(self):
        self.post('/api/approve',{})
        self.assertEqual(self.post('/api/command',{'message':'draft reminders'}).json()['status'],'BLOCKED')
        self.post('/api/approve',{'tool':'create_draft_payment_reminders'})
        result=self.post('/api/command',{'message':'draft reminders'}).json()['result']
        self.assertEqual(result['draft_count'],3);self.assertEqual(result['emails_sent'],0)
        self.post('/api/approve',{'tool':'export_sandbox_reports'})
        self.assertIn('report',self.post('/api/command',{'message':'export report'}).json()['result'])
    def test_expiry_and_cloud_data_boundary(self):
        self.post('/api/approve',{})
        module.sessions[self.user['uid']]['local']['expires']=0
        self.assertEqual(self.post('/api/execute',{}).status_code,409)
        workspace.save(self.user['uid'],'upload',[])
        with patch.dict(os.environ,{'FINANCEGUARD_SCOPED_MCP':'0'}):
            self.assertEqual(self.post('/api/approve',{'engine':'armoriq'}).status_code,409)
    def test_stripe_key_constraints(self):
        with patch.dict(os.environ,{'STRIPE_OPERATOR_EMAIL':self.user['email'],'STRIPE_SECRET_KEY':'sk_live_do_not_use'}):
            self.assertEqual(self.post('/api/source/stripe',{}).status_code,400)
    def test_revoke(self):
        self.post('/api/approve',{})
        credential=module.sessions[self.user['uid']]['local']['mcp_token']
        self.assertEqual(self.post('/api/revoke',{}).json()['status'],'REVOKED')
        self.assertEqual(self.post('/api/execute',{}).status_code,409)
        with self.assertRaises(RuntimeError):module.mcp_access.invoke('summarize_overdue_invoices',credential)
    def test_missing_backend_configuration_is_sanitized_and_never_creates_workflow(self):
        with patch.dict(os.environ,{'ARMORIQ_API_KEY':''}),patch('app.ArmorIQWorkflow') as workflow:
            response=self.post('/api/approve',{'engine':'armoriq'})
            self.assertEqual(response.status_code,503)
            data=response.json()
            self.assertEqual(data['category'],'configuration')
            self.assertEqual(data['code'],'armoriq_api_key_missing')
            self.assertFalse(data['verified']);workflow.assert_not_called()
            self.assertEqual(self.web.get('/api/state').json()['events'][0]['status'],'ERROR')
    def test_scoped_armoriq_forwarding_and_result(self):
        from types import SimpleNamespace
        with patch.dict(os.environ,{'FINANCEGUARD_SCOPED_MCP':'1','ARMORIQ_AGENT_ID':'test-agent','ARMORIQ_MCP_SERVER_ID':'2da563ef-544e-4db7-a418-0c404cf75180','ARMORIQ_API_KEY':'ak_test_unit_test_placeholder','ARMORIQ_EXPECTED_ORG_ID':'68c3541d-e2d8-462a-8393-243925a5ed23','MCP_SERVER_URL':'https://mcp.example/mcp','FINANCEGUARD_MCP_SIGNING_KEY':'unit-test-signing-key-'+'a'*32}),patch('app.ArmorIQWorkflow') as client:
            client.return_value.snapshot.return_value={'session_id':'test-session','trace_ids':[],'delivery':'unconfirmed','accepted':0,'rejected':0}
            client.return_value.flush.return_value=client.return_value.snapshot.return_value
            client.return_value.invoke.return_value=SimpleNamespace(status='success',verified=True,result={'content':[{'type':'text','text':'{"overdue_invoice_count":3,"total_overdue_amount_inr":88000}'}],'isError':False})
            self.assertEqual(self.post('/api/approve',{'engine':'armoriq'}).status_code,200)
            self.assertEqual(client.call_args.args[0],'summarize_overdue_invoices')
            self.assertTrue(client.call_args.args[1])
            result=self.post('/api/execute',{'engine':'armoriq'}).json()
            self.assertTrue(result['verified']);self.assertEqual(result['result']['overdue_invoice_count'],3)
            client.return_value.invoke.return_value=SimpleNamespace(status='success',verified=True,result={'content':[{'type':'text','text':'tool failed'}],'isError':True})
            response=self.post('/api/execute',{'engine':'armoriq'})
            self.assertEqual(response.status_code,502)
            self.assertEqual(self.web.get('/api/state').json()['events'][0]['status'],'ERROR')
    def test_action_aliases_and_audit_scope(self):
        self.assertEqual(self.post('/api/run-approved-action',{}).status_code,409)
        self.post('/api/approve',{})
        self.assertEqual(self.post('/api/run-approved-action',{}).json()['status'],'allowed')
        self.assertEqual(self.post('/api/attempt-refund',{}).json()['status'],'blocked')
        log=self.web.get('/api/audit-log').json()
        self.assertEqual(log['source'],'application_action_trail')
        self.assertEqual(log['events'][0]['action'],'simulate_refunds')
        self.user=dict(self.user,uid='unrelated-'+str(time.time_ns()))
        self.assertEqual(self.web.get('/api/audit-log').json()['events'],[])

    def test_direct_mcp_denies_missing_scope_and_wrong_tool(self):
        headers={'Accept':'application/json, text/event-stream'}
        payload={'jsonrpc':'2.0','id':1,'method':'tools/call','params':{'name':'summarize_overdue_invoices','arguments':{}}}
        result=self.web.post('/mcp',headers=headers,json=payload).json()['result']
        self.assertTrue(result['isError'])
        token=module.mcp_access.issue(self.user['uid'],'list_invoices',module.store.source(self.user['uid'])[1])
        result=self.web.post('/mcp',headers=dict(headers,Authorization='Bearer '+token),json=payload).json()['result']
        self.assertTrue(result['isError'])
    def test_stripe_sync_normalization(self):
        data={'data':[{'id':'in_test_1','currency':'inr','livemode':False,'total':12345,'due_date':1577836800,'status':'open','customer_name':'Test Customer'}],'has_more':False}
        request=__import__('httpx').Request('GET','https://api.stripe.com/v1/invoices')
        response=__import__('httpx').Response(200,json=data,request=request)
        with patch.dict(os.environ,{'STRIPE_OPERATOR_EMAIL':self.user['email'],'STRIPE_SECRET_KEY':'sk_test_placeholder'}),patch('app.httpx.Client') as client:
            client.return_value.__enter__.return_value.get.return_value=response
            self.assertEqual(self.post('/api/source/stripe',{}).json()['status'],'SYNCED')
            state=self.web.get('/api/state').json()
            self.assertEqual(state['invoices'][0]['amount_inr'],123.45)
            self.assertEqual(state['source'],'stripe_sandbox')

if __name__=='__main__':unittest.main()
