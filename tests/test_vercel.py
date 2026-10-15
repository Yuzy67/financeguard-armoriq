"""Exercise Vercel cold-start behavior in a separate interpreter."""
import json,os,subprocess,sys,tempfile,unittest

class VercelDeploymentTests(unittest.TestCase):
    def test_cold_start_host_cookie_and_real_mcp(self):
        script=r'''
import json,os,site,tempfile
from unittest.mock import patch
for path in json.loads(os.environ['TEST_PACKAGE_PATHS']):site.addsitedir(path)
os.environ.pop('FINANCEGUARD_RUNTIME',None)
os.environ.update(VERCEL='1',VERCEL_URL='preview.example.vercel.app',VERCEL_PROJECT_PRODUCTION_URL='financeguard-armoriq.vercel.app')
with tempfile.TemporaryDirectory() as scratch,patch('tempfile.gettempdir',return_value=scratch):
    import app,workspace,mcp_access
    from fastapi.testclient import TestClient
    assert workspace.RUNTIME.parent.name==__import__('pathlib').Path(scratch).name
    with TestClient(app.app,base_url='https://financeguard-armoriq.vercel.app') as web:
        assert web.get('/').status_code==200
        assert web.get('/favicon.ico').status_code==204
        assert web.get('/api/health').json()['storage']=='temporary'
        assert web.get('/api/state').status_code==401
        response=web.post('/api/demo')
        assert response.status_code==200
        assert 'Secure' in response.headers['set-cookie']
        assert web.get('/api/state').json()['temporary_storage'] is True
        assert web.post('/api/approve',json={}).status_code==200
        result=web.post('/api/execute',json={}).json()
        assert result['status']=='ALLOWED',result
        assert result['result']['total_overdue_amount_inr']==88000
        assert result['verified'] is False
        assert web.post('/api/execute',json={'tool':'simulate_refunds'}).json()['status']=='BLOCKED'
        assert web.get('/',headers={'Host':'untrusted.example'}).status_code==400
        try:mcp_access.invoke('summarize_overdue_invoices','forged')
        except Exception as exc:assert 'MCP rejected' in str(exc) or isinstance(exc,ExceptionGroup)
        else:raise AssertionError('Forged MCP token was accepted')
'''
        env=dict(os.environ,TEST_PACKAGE_PATHS=json.dumps([p for p in sys.path if p]))
        result=subprocess.run([sys.executable,'-c',script],env=env,capture_output=True,text=True,timeout=45)
        self.assertEqual(result.returncode,0,result.stderr[-6000:])

