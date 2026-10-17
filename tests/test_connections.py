"""Connector tests use mocked provider HTTP; no live access is claimed."""
import json,os,tempfile,time,unittest
from pathlib import Path
from unittest.mock import patch
import httpx
from fastapi.testclient import TestClient
import app,workspace,invoice_connections as connectors

class ConnectorTests(unittest.TestCase):
    def setUp(self):
        self.scratch=tempfile.TemporaryDirectory();self.runtime=patch.object(workspace,'RUNTIME',Path(self.scratch.name));self.runtime.start()
        self.env=patch.dict(os.environ,{'VERCEL':'0','ZOHO_CLIENT_ID':'unit-client','ZOHO_CLIENT_SECRET':'unit-secret','ZOHO_REDIRECT_URI':'http://testserver/api/connections/zoho/callback'});self.env.start()
        self.temporary=patch.object(workspace,'TEMPORARY_STORAGE',False);self.temporary.start()
        self.user={'uid':'connector-owner','signed_in':True,'email':'synthetic@example.com'}
        app.app.dependency_overrides[app.identity]=lambda:self.user
        self.web=TestClient(app.app)
    def tearDown(self):
        app.app.dependency_overrides.clear();self.web.close();self.temporary.stop();self.env.stop();self.runtime.stop();self.scratch.cleanup()
    def post(self,path,data=None):return self.web.post(path,json=data or {})
    def save_stripe(self):return self.post('/api/connections/stripe/credentials',{'key':'rk_test_secret_never_echo_this'})
    def test_keys_encrypted_and_owner_isolated(self):
        self.assertEqual(self.save_stripe().status_code,200)
        self.assertNotIn('rk_test_secret', (Path(self.scratch.name)/'workspace.sqlite3').read_bytes().decode(errors='ignore'))
        self.assertNotIn('rk_test_secret',self.web.get('/api/connections').text)
        self.user=dict(self.user,uid='other-owner')
        self.assertFalse(any(p['connected'] for p in self.web.get('/api/connections').json()['providers']))
        self.assertEqual(self.post('/api/connections/stripe/preview').status_code,409)
    def test_reject_live_keys_and_guest_and_temporary_host(self):
        self.assertEqual(self.post('/api/connections/stripe/credentials',{'key':'sk_live_no'}).status_code,400)
        self.user['signed_in']=False;self.assertEqual(self.save_stripe().status_code,401)
        self.user['signed_in']=True
        with patch.dict(os.environ,{'VERCEL':'1'}):self.assertEqual(self.save_stripe().status_code,503)
    def test_preview_does_not_import_and_confirm_is_owner_bound_one_time(self):
        self.save_stripe()
        rows=[workspace.normalize({'invoice_id':'T1','customer_name':'Synthetic','amount_inr':'123.45','due_date':'2020-01-01','status':'unpaid'},1)]
        with patch.object(connectors,'fetch',return_value=rows):preview=self.post('/api/connections/stripe/preview').json()
        self.assertEqual(workspace.source(self.user['uid'])[0],'sample')
        original=self.user.copy();self.user['uid']='other'
        self.save_stripe();self.assertEqual(self.post('/api/connections/stripe/import',{'preview_id':preview['preview_id']}).status_code,409)
        self.user=original
        result=self.post('/api/connections/stripe/import',{'preview_id':preview['preview_id']})
        self.assertEqual(result.status_code,200);self.assertEqual(workspace.source(self.user['uid'])[1][0]['amount_inr'],123.45)
        self.assertEqual(self.post('/api/connections/stripe/import',{'preview_id':preview['preview_id']}).status_code,409)
        self.post('/api/connections/stripe/disconnect');self.assertEqual(workspace.source(self.user['uid'])[1],[])
    def test_partial_payment_uses_remaining_balance(self):
        raw={'id':'in_test','currency':'inr','livemode':False,'total':100000,'amount_remaining':25000,'due_date':1577836800,'status':'open'}
        self.assertEqual(connectors.invoice('stripe',raw)['amount_inr'],250)
        raw['currency']='usd'
        with self.assertRaises(ValueError):connectors.invoice('stripe',raw)
        raw.update(currency='inr',due_date=None)
        with self.assertRaises(ValueError):connectors.invoice('stripe',raw)
    def test_zoho_read_scope_and_browser_state_binding(self):
        with patch.dict(os.environ,{'ZOHO_REDIRECT_URI':'http://localhost/api/connections/zoho/callback'}):
            started=self.post('/api/connections/zoho/start',{'organization_id':'12345','region':'in'})
        self.assertEqual(started.status_code,200)
        from urllib.parse import urlparse,parse_qs
        query=parse_qs(urlparse(started.json()['url']).query);state=query['state'][0]
        self.assertEqual(query['scope'],['ZohoInvoice.invoices.READ'])
        cookie=self.web.cookies.get('fg_zoho');self.web.cookies.clear()
        self.assertEqual(self.web.get('/api/connections/zoho/callback?state='+state).status_code,400)
        self.web.cookies.set('fg_zoho',cookie)
        data=httpx.Response(200,json={'refresh_token':'refresh-private','access_token':'access-private'})
        with patch('invoice_connections.httpx.Client') as client:
            client.return_value.__enter__.return_value.post.return_value=data
            result=self.web.get('/api/connections/zoho/callback?state='+state+'&code=one-time',follow_redirects=False)
        self.assertEqual(result.status_code,303)
        self.assertNotIn('private',result.text)
        self.assertEqual(self.web.get('/api/connections/zoho/callback?state='+state).status_code,400)
        self.assertEqual(connectors.load(self.user['uid'],'zoho')['organization_id'],'12345')
    def test_actual_adapter_get_only_and_auth_error_sanitized(self):
        self.save_stripe()
        with patch('invoice_connections.httpx.Client') as client:
            client.return_value.__enter__.return_value.get.return_value=httpx.Response(401,text='private provider body')
            result=self.post('/api/connections/stripe/preview')
            self.assertEqual(result.status_code,401);self.assertNotIn('private provider',result.text)
            client.return_value.__enter__.return_value.post.assert_not_called()
        self.assertEqual(workspace.source(self.user['uid'])[0],'sample')
    def test_validation_never_echoes_private_input(self):
        secret='private-marker-'+'a'*600
        response=self.post('/api/connections/stripe/credentials',{'key':secret})
        self.assertEqual(response.status_code,422)
        self.assertNotIn('private-marker',response.text)

    def test_razorpay_and_zoho_balances_are_not_total_amounts(self):
        razor={'id':'inv_test','currency':'INR','amount':50000,'amount_due':12500,'status':'partially_paid','expire_by':1577836800,'customer_details':{'name':'Example'}}
        zoho={'invoice_id':'1234','currency_code':'INR','total':500,'balance':125,'status':'partially_paid','due_date':'2020-01-01','customer_name':'Example'}
        self.assertEqual(connectors.invoice('razorpay',razor)['amount_inr'],125)
        self.assertEqual(connectors.invoice('zoho',zoho)['amount_inr'],125)
    def test_reconnect_invalidates_pending_preview(self):
        self.save_stripe()
        with patch.object(connectors,'fetch',return_value=[]):preview=self.post('/api/connections/stripe/preview').json()['preview_id']
        self.save_stripe()
        self.assertEqual(self.post('/api/connections/stripe/import',{'preview_id':preview}).status_code,409)
    def test_actual_stripe_fetch_requests_only_invoice_reads(self):
        self.save_stripe()
        raw={'id':'in_test','currency':'inr','livemode':False,'total':100000,'amount_remaining':25000,'due_date':1577836800,'status':'open'}
        with patch('invoice_connections.httpx.Client') as client:
            client.return_value.__enter__.return_value.get.return_value=httpx.Response(200,json={'data':[raw],'has_more':False})
            result=self.post('/api/connections/stripe/preview')
            self.assertEqual(result.status_code,200)
            self.assertEqual(result.json()['summary']['total_overdue_amount_inr'],250)
            client.return_value.__enter__.return_value.get.assert_called_once()
            client.return_value.__enter__.return_value.post.assert_not_called()

    def test_changed_workspace_cannot_be_overwritten_by_stale_provider_preview(self):
        self.save_stripe()
        with patch.object(connectors,'fetch',return_value=[]):preview=self.post('/api/connections/stripe/preview').json()['preview_id']
        workspace.save(self.user['uid'],'upload',[])
        self.assertEqual(self.post('/api/connections/stripe/import',{'preview_id':preview}).status_code,409)
