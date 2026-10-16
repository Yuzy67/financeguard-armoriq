"""FinanceGuard application: Firebase identities and isolated invoice workspaces."""
import hashlib,json,os,secrets,threading,time
from datetime import datetime,timezone
from decimal import Decimal
from pathlib import Path
from uuid import uuid4
import httpx
from dotenv import load_dotenv
from fastapi import FastAPI,Request,HTTPException,Depends
from fastapi.responses import FileResponse,JSONResponse,Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel,Field
from starlette.middleware.trustedhost import TrustedHostMiddleware
from contextlib import asynccontextmanager
ROOT=Path(__file__).parent
load_dotenv(ROOT/'.env')
import workspace as store
from security import verify_identity
import mcp_access
import assistant_brain
from armoriq_workflow import ArmorIQWorkflow
from finance_mcp.server import mcp
mcp_app=mcp.streamable_http_app()
@asynccontextmanager
async def lifespan(app):
    async with mcp.session_manager.run():
        try:yield
        finally:
            for uid in list(sessions):discard_plans(uid)
app=FastAPI(title='FinanceGuard',docs_url=None,redoc_url=None,lifespan=lifespan)
deployment_hosts=[os.environ.get(name,'') for name in ['VERCEL_URL','VERCEL_PROJECT_PRODUCTION_URL','VERCEL_BRANCH_URL']] if os.environ.get('VERCEL')=='1' else []
app.add_middleware(TrustedHostMiddleware,allowed_hosts=['localhost','127.0.0.1','testserver']+[h.strip() for h in os.environ.get('FINANCEGUARD_ALLOWED_HOSTS','').split(',') if h.strip()]+[h for h in deployment_hosts if h])
app.mount('/assets',StaticFiles(directory=ROOT/'frontend'),name='assets')
sessions={};locks={};master=threading.Lock();guest_sessions={}
SAFE={'list_invoices','summarize_overdue_invoices','create_draft_payment_reminders','export_sandbox_reports'}
UNSAFE={'simulate_refunds','transfer_funds','delete_invoices'}

@app.middleware('http')
async def safety(request,call_next):
    origin=request.headers.get('origin')
    if request.method not in {'GET','HEAD','OPTIONS'} and ((origin and origin.rstrip('/')!=str(request.base_url).rstrip('/')) or request.headers.get('sec-fetch-site')=='cross-site'):
        return JSONResponse({'detail':'Cross-origin request rejected'},status_code=403)
    response=await call_next(request)
    response.headers.update({'X-Content-Type-Options':'nosniff','Referrer-Policy':'same-origin','Cache-Control':'no-store'})
    return response

def identity(request:Request):
    header=request.headers.get('authorization','')
    if header:
        if not header.startswith('Bearer '):raise HTTPException(401,'Sign in again.')
        return verify_identity(header[7:])
    with master:guest=guest_sessions.get(request.cookies.get('fg_demo',''))
    if not guest or guest['expires']<time.time():raise HTTPException(401,'Start a demo or sign in.')
    return {'uid':guest['uid'],'email':'','signed_in':False}

def owner_lock(uid):
    with master:return locks.setdefault(uid,threading.Lock())

def discard_plans(uid):
    previous=sessions.pop(uid,{})
    for plan in previous.values():
        if plan.get('client'):plan['client'].close()

def fingerprint(rows):return hashlib.sha256(json.dumps(rows,sort_keys=True).encode()).hexdigest()

def failure(uid,tool,exc,engine,observability=None):
    name=type(exc).__name__;blocked=name in {'IntentMismatchException','PolicyBlockedException','ActionDenied'}
    reason='IntentMismatchException: action is outside the approved plan.' if name=='IntentMismatchException' else 'ArmorIQ policy denied the action.' if blocked else f'{name}: provider operation failed.'
    if name=='ConfigurationError':reason=str(exc)
    if 'Internal Proxy Error' in str(exc):reason='ArmorIQ proxy could not execute the tool. Verify registered MCP URL and server health.'
    event=store.event(uid,tool,'BLOCKED' if blocked else 'ERROR',reason,engine='ARMORIQ_SDK' if name=='IntentMismatchException' else engine.upper(),observability=observability)
    return JSONResponse({'status':event['status'],'reason':reason,'exception':name,'event':event,'verified':False},status_code=200 if blocked else 502)

def perform(tool,user,engine='local',approve=False,expected_fingerprint=None):
    uid=user['uid']
    with owner_lock(uid):
        kind,rows=store.source(uid);session=sessions.setdefault(uid,{})
        if expected_fingerprint and fingerprint(rows)!=expected_fingerprint:raise HTTPException(409,'Invoice data changed. Request approval again for the new snapshot.')
        if engine not in {'local','armoriq'}:raise HTTPException(400,'Unknown execution engine.')
        if engine=='armoriq' and kind!='sample' and os.environ.get('FINANCEGUARD_SCOPED_MCP')!='1':raise HTTPException(409,'Scoped MCP forwarding must be configured before ArmorIQ can read your imported workspace.')
        if approve:
            previous=session.pop(engine,None)
            if previous and previous.get('client'):previous['client'].close()
            if tool not in SAFE:raise HTTPException(400,'Only safe actions can be approved.')
            plan={'goal':'Review invoices without money movement.','steps':[{'action':tool,'mcp':'finance-mcp','params':{}}]}
            new={'id':str(uuid4()),'tool':tool,'expires':time.time()+300,'fingerprint':fingerprint(rows),'plan':plan,'mcp_token':mcp_access.issue(uid,tool,rows)}
            if engine=='armoriq':
                if not os.environ.get('ARMORIQ_API_KEY'):raise HTTPException(503,'Add ARMORIQ_API_KEY to backend .env.')
                try:
                    workflow=ArmorIQWorkflow(tool,new['mcp_token'] if os.environ.get('FINANCEGUARD_SCOPED_MCP')=='1' else None)
                    new.update(client=workflow)
                    workflow.flush()
                except Exception as exc:return failure(uid,tool,exc,engine)
            session[engine]=new
            event=store.event(uid,'approve_plan','APPROVED',f'Approved {tool} for five minutes.',engine=engine.upper(),observability=new['client'].snapshot() if new.get('client') else None)
            return {'status':'APPROVED','reason':event['reason'],'event':event}
        approved=session.get(engine)
        if not approved or time.time()>=approved['expires']:
            if approved and approved.get('client'):approved['client'].close()
            session.pop(engine,None)
            raise HTTPException(409,'Approve a plan first, or renew the expired plan.')
        if approved['fingerprint']!=fingerprint(rows):
            if approved.get('client'):approved['client'].close()
            session.pop(engine,None);raise HTTPException(409,'Invoice data changed. Approve a new plan.')
        if engine=='local':
            if tool!=approved['tool']:
                event=store.event(uid,tool,'BLOCKED','Outside the approved local plan. Nothing executed.')
                return {'status':'BLOCKED','reason':event['reason'],'event':event,'verified':False}
            try:result=mcp_access.invoke(tool,approved['mcp_token'])
            except Exception as exc:return failure(uid,tool,exc,engine)
            event=store.event(uid,tool,'ALLOWED','MCP tool executed for this workspace under the local plan. No ArmorIQ verification claimed.')
            return {'status':'ALLOWED','reason':event['reason'],'result':result,'event':event,'verified':False}
        try:
            params={'invoice_id':(rows[0]['invoice_id'] if rows else 'demo-invoice')} if tool in {'simulate_refunds','delete_invoices'} else {'recipient':'Sandbox vendor','amount_inr':50000} if tool=='transfer_funds' else {}
            result=approved['client'].invoke(tool,params,user_email=user.get('email') or os.environ.get('FINANCEGUARD_USER_EMAIL','demo@example.com'))
            if result.status!='success':raise RuntimeError('Tool execution failed.')
            status='UNEXPECTED_ALLOWED' if tool in UNSAFE else 'ALLOWED'
            payload=result.result
            if isinstance(payload,dict) and payload.get('content'):
                if payload.get('isError'):raise RuntimeError('MCP returned a tool error.')
                texts=[part.get('text','') for part in payload['content'] if part.get('type')=='text']
                if texts:
                    try:payload=json.loads(texts[0])
                    except ValueError:pass
            if tool=='summarize_overdue_invoices':
                expected=store.summary(rows)
                if not isinstance(payload,dict) or payload.get('overdue_invoice_count')!=expected['overdue_invoice_count'] or payload.get('total_overdue_amount_inr')!=expected['total_overdue_amount_inr']:
                    raise RuntimeError('MCP result does not match this workspace snapshot.')
            observation=approved['client'].flush()
            event=store.event(uid,tool,status,'ArmorIQ SDK invocation returned.' if status=='ALLOWED' else 'Unsafe action unexpectedly returned. Inspect the policy.',result.verified is True,'ARMORIQ',observability=observation)
            return {'status':status,'reason':event['reason'],'verified':result.verified is True,'result':payload,'event':event}
        except Exception as exc:
            observation=approved['client'].flush()
            return failure(uid,tool,exc,engine,observation)

@app.get('/api/health')
def health():
    return {'status':'ok','storage':'temporary' if store.TEMPORARY_STORAGE else 'local-persistent','armoriq_configured':bool(os.environ.get('ARMORIQ_API_KEY')),'mcp_signing_configured':bool(os.environ.get('FINANCEGUARD_MCP_SIGNING_KEY')),'mcp_url_configured':bool(os.environ.get('MCP_SERVER_URL'))}

@app.get('/favicon.ico',include_in_schema=False)
def favicon():return Response(status_code=204)

@app.get('/')
def home():return FileResponse(ROOT/'frontend/index.html')

@app.post('/api/demo')
def demo():
    key=secrets.token_urlsafe(32)
    with master:
        for old in [k for k,v in guest_sessions.items() if v['expires']<time.time()]:guest_sessions.pop(old,None)
        guest_sessions[key]={'uid':'demo-'+uuid4().hex,'expires':time.time()+3600}
    response=JSONResponse({'status':'READY'})
    response.set_cookie('fg_demo',key,httponly=True,samesite='strict',max_age=3600,secure=os.environ.get('FINANCEGUARD_HTTPS')=='1' or os.environ.get('VERCEL')=='1')
    return response

@app.get('/api/state')
def state(user=Depends(identity)):
    kind,rows=store.source(user['uid'])
    with owner_lock(user['uid']):plans={engine:{k:p[k] for k in ['id','tool','expires','plan']} for engine,p in sessions.get(user['uid'],{}).items() if p['expires']>time.time()}
    return {'invoices':rows,'summary':store.summary(rows),'events':store.history(user['uid']),'source':kind,'plans':plans,'user':user,'armoriq_configured':bool(os.environ.get('ARMORIQ_API_KEY')),'stripe_configured':bool(os.environ.get('STRIPE_SECRET_KEY')),'temporary_storage':store.TEMPORARY_STORAGE,'assistant':assistant_brain.configuration()}

class Action(BaseModel):
    tool:str='summarize_overdue_invoices'
    engine:str='local'

@app.post('/api/approve')
def approve(body:Action,user=Depends(identity)):return perform(body.tool,user,body.engine,True)

@app.post('/api/execute')
def execute(body:Action,user=Depends(identity)):
    if body.tool not in SAFE|UNSAFE:raise HTTPException(400,'Unsupported tool.')
    return perform(body.tool,user,body.engine)

@app.post('/api/run-approved-action')
def run_approved_action(body:Action,user=Depends(identity)):
    result=perform('summarize_overdue_invoices',user,body.engine)
    if isinstance(result,dict):result.update(action='summarize_overdue_invoices',status=result['status'].lower())
    return result

@app.post('/api/attempt-refund')
def attempt_refund(body:Action,user=Depends(identity)):
    result=perform('simulate_refunds',user,body.engine)
    if isinstance(result,dict):result.update(action='simulate_refunds',status=result['status'].lower())
    elif isinstance(result,JSONResponse):
        payload=json.loads(result.body);payload.update(action='simulate_refunds',status=payload['status'].lower())
        return JSONResponse(payload,status_code=result.status_code)
    return result

@app.get('/api/audit-log')
def audit_log(user=Depends(identity)):
    return {'source':'application_action_trail','events':store.history(user['uid']),
            'note':'Local event IDs are not provider IDs. Observability fields contain SDK IDs and ingestion receipts; console visibility is separate.'}

@app.post('/api/revoke')
def revoke(user=Depends(identity)):
    with owner_lock(user['uid']):
        previous=sessions.pop(user['uid'],{})
        for plan in previous.values():
            if plan.get('client'):plan['client'].close()
        event=store.event(user['uid'],'revoke_plans','REVOKED','Local server discarded all workspace approvals and intent tokens. This is not a global provider token revocation.')
    return {'status':'REVOKED','reason':event['reason'],'event':event}

class AgentRequest(BaseModel):
    message:str=Field(min_length=1,max_length=2000)
    engine:str='local'

@app.post('/api/command')
def agent(body:AgentRequest,user=Depends(identity)):
    text=body.message.lower()
    tool=('simulate_refunds' if 'refund' in text else 'transfer_funds' if 'transfer' in text else 'delete_invoices' if 'delete' in text else 'create_draft_payment_reminders' if 'reminder' in text or 'draft' in text else 'export_sandbox_reports' if 'export' in text or 'report' in text else 'summarize_overdue_invoices' if any(s in text for s in ['overdue','owe','summary','summarize']) else 'list_invoices' if 'invoice' in text else None)
    if not tool:return {'status':'NEEDS_INPUT','reason':'Try summarize overdue invoices, list invoices, draft reminders, export report, or test a refund. Requests use command matching.'}
    return perform(tool,user,body.engine)

class Import(BaseModel):
    csv:str=Field(max_length=700000)
    confirm:bool=False
    auto_sync:bool=False

@app.post('/api/import')
def upload(body:Import,user=Depends(identity)):
    if not user['signed_in']:raise HTTPException(401,'Sign in before importing invoices.')
    try:rows=store.preview(body.csv)
    except ValueError as exc:raise HTTPException(400,str(exc)) from None
    if body.confirm:
        with owner_lock(user['uid']):
            store.save(user['uid'],'upload',rows);discard_plans(user['uid'])
            store.event(user['uid'],'auto_sync_invoices' if body.auto_sync else 'import_invoices','IMPORTED',f'Imported {len(rows)} invoices. Prior plans invalidated.')
    return {'invoices':rows,'count':len(rows),'saved':body.confirm}

@app.get('/api/template')
def template():return Response('invoice_id,customer_name,amount_inr,due_date,status\nINV-001,Example Studio,24000,2026-10-01,unpaid\nINV-002,Example Retail,15000,2026-11-01,paid\n',media_type='text/csv',headers={'Content-Disposition':'attachment; filename="invoice-template.csv"'})

@app.post('/api/source/sample')
def sample(user=Depends(identity)):
    with owner_lock(user['uid']):store.reset(user['uid']);discard_plans(user['uid'])
    return {'status':'READY'}

@app.post('/api/source/stripe')
def stripe_sync(user=Depends(identity)):
    if not user['signed_in']:raise HTTPException(401,'Sign in before syncing invoices.')
    allowed=os.environ.get('STRIPE_OPERATOR_EMAIL','').lower()
    if not allowed or user['email'].lower()!=allowed:raise HTTPException(403,'Restricted to the configured demo operator. Customer OAuth is not implemented.')
    if not user.get('email_verified'):raise HTTPException(403,'Verify your Firebase email before accessing the operator Stripe sandbox.')
    key=os.environ.get('STRIPE_SECRET_KEY','')
    if not key:raise HTTPException(503,'Add a sandbox STRIPE_SECRET_KEY on the backend.')
    if not key.startswith(('sk_test_','rk_test_')):raise HTTPException(400,'Only Stripe test-mode API keys are accepted.')
    rows=[];cursor=None
    try:
        with httpx.Client(timeout=20) as client:
            for page in range(10):
                params={'limit':100}
                if cursor:params['starting_after']=cursor
                response=client.get('https://api.stripe.com/v1/invoices',params=params,headers={'Authorization':'Bearer '+key})
                response.raise_for_status();data=response.json()
                for invoice in data['data']:
                    if invoice.get('livemode'):raise ValueError('Live invoices are not accepted.')
                    if invoice.get('currency')!='inr':raise ValueError('Only INR invoices are supported. Other currencies cannot be relabeled as INR.')
                    due=invoice.get('due_date')
                    if not due:raise ValueError('An invoice has no due date. Configure explicit due dates in the sandbox first.')
                    raw={'invoice_id':invoice['id'],'customer_name':invoice.get('customer_name') or invoice.get('customer_email') or 'Sandbox customer','amount_inr':str(Decimal(invoice['total'])/100),'due_date':datetime.fromtimestamp(due,timezone.utc).date().isoformat(),'status':'unpaid' if invoice.get('status')=='open' else invoice.get('status','draft')}
                    rows.append(store.normalize(raw,len(rows)+1))
                if not data.get('has_more'):break
                cursor=data['data'][-1]['id']
            else:raise ValueError('More than 1000 invoices. Narrow the sandbox first.')
        if not rows:raise ValueError('No sandbox invoices found. Create test invoices first.')
    except httpx.HTTPError:raise HTTPException(502,'Stripe sync failed. Check test credentials and read permissions.') from None
    except ValueError as exc:raise HTTPException(400,str(exc)) from None
    with owner_lock(user['uid']):store.save(user['uid'],'stripe_sandbox',rows);discard_plans(user['uid'])
    return {'status':'SYNCED','count':len(rows)}

from chat_api import install as install_chat
install_chat(app,identity,perform,store,sessions,owner_lock,fingerprint)

# Last mount preserves /api routes and serves the SDK's default /mcp path.
app.mount('/',mcp_app)
