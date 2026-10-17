"""Read-only invoice connectors. Provider credentials never enter model context."""
import hashlib,json,os,secrets,time
from datetime import datetime,timezone
from decimal import Decimal,InvalidOperation
from pathlib import Path
from urllib.parse import urlencode,urlparse
import httpx
from cryptography.fernet import Fernet,InvalidToken
from fastapi import Depends,HTTPException,Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel,Field,ConfigDict
import workspace as store

PROVIDERS=('zoho','razorpay','stripe')
DOCS={'zoho':'https://www.zoho.com/invoice/api/v3/oauth/','razorpay':'https://razorpay.com/docs/api/authentication/','stripe':'https://docs.stripe.com/keys'}
REGIONS={'in':('https://accounts.zoho.in','https://www.zohoapis.in'),'com':('https://accounts.zoho.com','https://www.zohoapis.com'),'eu':('https://accounts.zoho.eu','https://www.zohoapis.eu')}

def table(conn):
    conn.execute('CREATE TABLE IF NOT EXISTS invoice_connections(owner TEXT,provider TEXT,secret TEXT,updated INTEGER,PRIMARY KEY(owner,provider))')
    conn.execute('CREATE TABLE IF NOT EXISTS invoice_oauth(state TEXT PRIMARY KEY,owner TEXT,payload TEXT,browser TEXT,expires INTEGER)')
    conn.execute('CREATE TABLE IF NOT EXISTS invoice_previews(id TEXT PRIMARY KEY,owner TEXT,provider TEXT,version TEXT,rows TEXT,expires INTEGER)')

def ready():
    if store.TEMPORARY_STORAGE or os.environ.get('VERCEL')=='1':
        raise HTTPException(503,'Provider connections require a persistent backend. This deployment uses temporary storage; CSV and sample invoices remain available.')

def cipher():
    configured=os.environ.get('FINANCEGUARD_CONNECTOR_KEY')
    if configured:
        try:return Fernet(configured.encode())
        except (ValueError,TypeError):raise HTTPException(503,'Backend connector encryption key is invalid.') from None
    # Local development only. Host this same persistent runtime for all requests.
    path=store.RUNTIME/'connector-encryption.key'
    try:
        with path.open('xb') as output:output.write(Fernet.generate_key())
    except FileExistsError:pass
    return Fernet(path.read_bytes())

def save(owner,provider,credentials):
    encrypted=cipher().encrypt(json.dumps(credentials).encode()).decode()
    with store.db() as conn:
        table(conn);conn.execute('INSERT OR REPLACE INTO invoice_connections VALUES (?,?,?,?)',(owner,provider,encrypted,int(time.time())))
        conn.execute('DELETE FROM invoice_previews WHERE owner=? AND provider=?',(owner,provider))

def load(owner,provider):
    with store.db() as conn:
        table(conn);row=conn.execute('SELECT secret FROM invoice_connections WHERE owner=? AND provider=?',(owner,provider)).fetchone()
    if not row:raise HTTPException(409,'Connect this provider first.')
    try:return json.loads(cipher().decrypt(row[0].encode()))
    except (InvalidToken,ValueError):raise HTTPException(503,'Stored connection cannot be decrypted. Restore the backend encryption key or reconnect.') from None

def response_json(response):
    if response.status_code in (401,403):raise HTTPException(401,'Provider rejected access. Reconnect or check invoice read permissions.')
    if response.status_code==429:raise HTTPException(429,'Provider rate limit reached. Wait before retrying.')
    if response.status_code>=400:raise HTTPException(502,'Provider request failed. No invoices were changed.')
    try:
        result=response.json()
        if not isinstance(result,dict):raise ValueError()
        return result
    except ValueError:raise HTTPException(502,'Provider returned an invalid response.') from None

def invoice(provider,raw):
    currency=raw.get('currency_code') if provider=='zoho' else raw.get('currency')
    if str(currency or '').upper()!='INR':raise ValueError('Only INR invoices can be imported. Other currencies are never relabeled.')
    if provider=='zoho':
        identifier=raw['invoice_id'];customer=raw.get('customer_name');due=raw.get('due_date');status=raw.get('status');total=Decimal(str(raw['total']));balance=Decimal(str(raw['balance']))
        status={'sent':'unpaid','partially_paid':'unpaid','overdue':'unpaid','void':'void','paid':'paid','draft':'draft'}.get(status,status)
    elif provider=='stripe':
        if raw.get('livemode') is not False:raise ValueError('Only explicitly test-mode Stripe invoices are accepted.')
        identifier=raw['id'];customer=raw.get('customer_name') or raw.get('customer_email');due=raw.get('due_date');status={'open':'unpaid'}.get(raw.get('status'),raw.get('status'));total=Decimal(str(raw['total']))/100;balance=Decimal(str(raw['amount_remaining']))/100
    else:
        identifier=raw['id'];customer=(raw.get('customer_details') or {}).get('name');due=raw.get('expire_by');status={'issued':'unpaid','partially_paid':'unpaid','cancelled':'void','expired':'unpaid'}.get(raw.get('status'),raw.get('status'));total=Decimal(str(raw['amount']))/100;balance=Decimal(str(raw['amount_due']))/100
    if isinstance(due,(int,float)):due=datetime.fromtimestamp(due,timezone.utc).date().isoformat()
    if not due:raise ValueError('An invoice has no due date. Add a due date at the source before importing; none is invented.')
    if not total.is_finite() or not balance.is_finite() or total<=0 or balance<0 or balance>total:raise ValueError('Invoice total or remaining balance is invalid.')
    amount=balance if status in {'unpaid','pending','overdue'} else total
    if amount==0:status='paid';amount=total
    row=store.normalize({'invoice_id':str(identifier),'customer_name':customer or 'Customer','amount_inr':str(amount),'due_date':due,'status':status},1)
    row.update(provider=provider,provider_invoice_id=str(identifier),total_inr=float(total),balance_inr=float(balance),currency='INR')
    return row

def fetch(owner,provider):
    credentials=load(owner,provider);rows=[];seen=set();cursor=None
    try:
        with httpx.Client(timeout=20,follow_redirects=False) as client:
            if provider=='zoho':
                accounts,api=REGIONS[credentials['region']]
                data=response_json(client.post(accounts+'/oauth/v2/token',data={'grant_type':'refresh_token','refresh_token':credentials['refresh_token'],'client_id':os.environ.get('ZOHO_CLIENT_ID',''),'client_secret':os.environ.get('ZOHO_CLIENT_SECRET','')}))
                token=data.get('access_token')
                if not token:raise HTTPException(401,'Zoho authorization expired or was revoked. Reconnect Zoho.')
            for page in range(1,11):
                if provider=='zoho':
                    data=response_json(client.get(api+'/invoice/v3/invoices',headers={'Authorization':'Zoho-oauthtoken '+token,'X-com-zoho-invoice-organizationid':credentials['organization_id']},params={'page':page,'per_page':100}))
                    if data.get('code',0)!=0:raise HTTPException(502,'Zoho could not read invoices. Check organization and granted scopes.')
                    items=data.get('invoices');more=(data.get('page_context') or {}).get('has_more_page',False)
                elif provider=='stripe':
                    params={'limit':100}
                    if cursor:params['starting_after']=cursor
                    data=response_json(client.get('https://api.stripe.com/v1/invoices',headers={'Authorization':'Bearer '+credentials['key']},params=params));items=data.get('data');more=data.get('has_more',False)
                else:
                    data=response_json(client.get('https://api.razorpay.com/v1/invoices',auth=(credentials['key_id'],credentials['key_secret']),params={'count':100,'skip':(page-1)*100}));items=data.get('items');more=isinstance(items,list) and len(items)==100
                if not isinstance(items,list):raise HTTPException(502,'Provider returned no valid invoice collection.')
                for raw in items:
                    row=invoice(provider,raw)
                    if row['invoice_id'] in seen:raise ValueError('Provider returned duplicate invoice identifiers.')
                    seen.add(row['invoice_id']);rows.append(row)
                    if len(rows)>500:raise ValueError('Limit this source to 500 invoices before importing.')
                if not more:return rows
                if not items:raise ValueError('Provider pagination is inconsistent.')
                cursor=items[-1].get('id')
            raise ValueError('Invoice pagination exceeded the supported limit.')
    except httpx.TimeoutException:raise HTTPException(504,'Provider timed out. Existing invoices are unchanged.') from None
    except httpx.HTTPError:raise HTTPException(502,'Could not securely reach the provider. Existing invoices are unchanged.') from None
    except (ValueError,KeyError,InvalidOperation,TypeError) as exc:
        message=str(exc) if isinstance(exc,ValueError) and not isinstance(exc,InvalidOperation) else 'Provider invoice fields are incomplete or invalid.'
        # Only our bounded adapter validation messages, not upstream bodies.
        raise HTTPException(422,message if len(message)<200 else 'Provider invoice validation failed.') from None

class Credentials(BaseModel):
    model_config=ConfigDict(extra='forbid')
    key:str=Field(default='',max_length=512)
    key_id:str=Field(default='',max_length=128)
    key_secret:str=Field(default='',max_length=512)

class ZohoStart(BaseModel):
    region:str='in'
    organization_id:str=Field(min_length=1,max_length=40,pattern=r'^\d+$')

class Confirm(BaseModel):
    preview_id:str=Field(max_length=100)

def install(app,identity,owner_lock,discard_plans):
    from fastapi.exceptions import RequestValidationError
    from fastapi.exception_handlers import request_validation_exception_handler
    from fastapi.responses import JSONResponse
    @app.exception_handler(RequestValidationError)
    async def validation_error(request,exc):
        if request.url.path.startswith('/api/connections'):
            # FastAPI's default validation response includes the rejected input,
            # which can be a private provider credential.
            return JSONResponse({'detail':'Invalid connection fields. Check provider, key format and field lengths.'},status_code=422)
        return await request_validation_exception_handler(request,exc)

    def signed(user):
        if not user['signed_in']:raise HTTPException(401,'Sign in to connect an invoice provider.')
        ready()
    def provider_check(provider):
        if provider not in PROVIDERS:raise HTTPException(404,'Unsupported invoice provider.')

    @app.get('/api/connections')
    def catalog(user=Depends(identity)):
        with store.db() as conn:
            table(conn);connected={r[0] for r in conn.execute('SELECT provider FROM invoice_connections WHERE owner=?',(user['uid'],))}
        persistent=not(store.TEMPORARY_STORAGE or os.environ.get('VERCEL')=='1')
        return {'persistent_backend':persistent,'providers':[{'id':p,'connected':p in connected,'available':persistent and (p!='zoho' or bool(os.environ.get('ZOHO_CLIENT_ID') and os.environ.get('ZOHO_CLIENT_SECRET') and os.environ.get('ZOHO_REDIRECT_URI'))),'docs':DOCS[p]} for p in PROVIDERS]}

    @app.post('/api/connections/{provider}/credentials')
    def connect(provider:str,body:Credentials,user=Depends(identity)):
        signed(user);provider_check(provider)
        if provider=='zoho':raise HTTPException(400,'Use Zoho OAuth consent instead of API keys.')
        if provider=='stripe':
            if not body.key.startswith('rk_test_') or len(body.key)<20:raise HTTPException(400,'Use a Stripe restricted TEST key with invoice read permission (rk_test_).')
            value={'key':body.key}
        else:
            if not body.key_id.startswith('rzp_test_') or not body.key_secret or any(c.isspace() for c in body.key_secret):raise HTTPException(400,'Use a Razorpay Test Mode key ID and secret.')
            value={'key_id':body.key_id,'key_secret':body.key_secret}
        with owner_lock(user['uid']):save(user['uid'],provider,value)
        return {'status':'SAVED','reason':'Credentials encrypted. Fetch a preview to verify provider access; no successful connection test is claimed.'}

    @app.post('/api/connections/zoho/start')
    def zoho_start(body:ZohoStart,user=Depends(identity)):
        signed(user)
        redirect=os.environ.get('ZOHO_REDIRECT_URI','');parsed=urlparse(redirect)
        if body.region not in REGIONS:raise HTTPException(400,'Select a supported Zoho data center.')
        if not all(os.environ.get(n) for n in ('ZOHO_CLIENT_ID','ZOHO_CLIENT_SECRET','ZOHO_REDIRECT_URI')):raise HTTPException(503,'The operator must configure the Zoho OAuth application on the backend first.')
        if not (parsed.scheme=='https' or parsed.scheme=='http' and parsed.hostname in ('localhost','127.0.0.1')) or parsed.path!='/api/connections/zoho/callback':raise HTTPException(503,'Configure the exact public Zoho callback URL on this backend.')
        state=secrets.token_urlsafe(32);browser=secrets.token_urlsafe(32)
        payload={'uid':user['uid'],'region':body.region,'organization_id':body.organization_id}
        with store.db() as conn:
            table(conn);conn.execute('DELETE FROM invoice_oauth WHERE expires<?',(int(time.time()),));conn.execute('INSERT INTO invoice_oauth VALUES (?,?,?,?,?)',(hashlib.sha256(state.encode()).hexdigest(),user['uid'],json.dumps(payload),hashlib.sha256(browser.encode()).hexdigest(),int(time.time())+600))
        from fastapi.responses import JSONResponse
        response=JSONResponse({'url':REGIONS[body.region][0]+'/oauth/v2/auth?'+urlencode({'scope':'ZohoInvoice.invoices.READ','client_id':os.environ['ZOHO_CLIENT_ID'],'state':state,'response_type':'code','redirect_uri':redirect,'access_type':'offline','prompt':'consent'})})
        response.set_cookie('fg_zoho',browser,httponly=True,samesite='lax',secure=parsed.scheme=='https',max_age=600,path='/api/connections/zoho/callback')
        return response

    @app.get('/api/connections/zoho/callback')
    def zoho_callback(request:Request):
        ready();state=request.query_params.get('state','');browser=request.cookies.get('fg_zoho','')
        digest=hashlib.sha256(state.encode()).hexdigest()
        with store.db() as conn:
            table(conn);owner=conn.execute('SELECT owner FROM invoice_oauth WHERE state=?',(digest,)).fetchone()
        if not owner:raise HTTPException(400,'Zoho authorization expired. Start again.')
        with owner_lock(owner[0]):
            with store.db() as conn:
                table(conn);row=conn.execute('DELETE FROM invoice_oauth WHERE state=? AND browser=? AND expires>? RETURNING payload',(digest,hashlib.sha256(browser.encode()).hexdigest(),int(time.time()))).fetchone()
            if not row:raise HTTPException(400,'Zoho authorization expired or browser state does not match. Start again.')
            payload=json.loads(row[0]);result='denied'
            if not request.query_params.get('error') and request.query_params.get('code'):
                try:
                    with httpx.Client(timeout=20,follow_redirects=False) as client:
                        tokens=response_json(client.post(REGIONS[payload['region']][0]+'/oauth/v2/token',data={'grant_type':'authorization_code','code':request.query_params['code'],'client_id':os.environ['ZOHO_CLIENT_ID'],'client_secret':os.environ['ZOHO_CLIENT_SECRET'],'redirect_uri':os.environ['ZOHO_REDIRECT_URI']}))
                    if not tokens.get('refresh_token'):raise HTTPException(401,'Zoho did not grant offline access. Reconnect with consent.')
                    save(payload['uid'],'zoho',dict(region=payload['region'],organization_id=payload['organization_id'],refresh_token=tokens['refresh_token']))
                    result='connected'
                except (httpx.HTTPError,HTTPException,KeyError):result='failed'
        response=RedirectResponse('/?zoho='+result+'#invoices',status_code=303)
        response.delete_cookie('fg_zoho',path='/api/connections/zoho/callback');return response

    @app.post('/api/connections/{provider}/preview')
    def preview(provider:str,user=Depends(identity)):
        signed(user);provider_check(provider)
        with owner_lock(user['uid']):
            credentials=load(user['uid'],provider);version=hashlib.sha256(json.dumps({'credentials':credentials,'snapshot':store.source(user['uid'])[1]},sort_keys=True).encode()).hexdigest();rows=fetch(user['uid'],provider)
            identifier=secrets.token_urlsafe(32)
            with store.db() as conn:
                table(conn);conn.execute('DELETE FROM invoice_previews WHERE expires<?',(int(time.time()),));conn.execute('INSERT INTO invoice_previews VALUES (?,?,?,?,?,?)',(identifier,user['uid'],provider,version,json.dumps(rows),int(time.time())+300))
        return {'preview_id':identifier,'invoices':rows[:5],'count':len(rows),'summary':store.summary(rows),'reason':'User-requested read-only source fetch. Not an ArmorIQ agent execution. Confirm to replace the current snapshot and invalidate approvals.'}

    @app.post('/api/connections/{provider}/import')
    def confirm(provider:str,body:Confirm,user=Depends(identity)):
        signed(user);provider_check(provider)
        with owner_lock(user['uid']):
            credentials=load(user['uid'],provider);version=hashlib.sha256(json.dumps({'credentials':credentials,'snapshot':store.source(user['uid'])[1]},sort_keys=True).encode()).hexdigest()
            with store.db() as conn:
                table(conn);row=conn.execute('SELECT rows FROM invoice_previews WHERE id=? AND owner=? AND provider=? AND version=? AND expires>?',(body.preview_id,user['uid'],provider,version,int(time.time()))).fetchone()
                if not row:raise HTTPException(409,'Preview expired, belongs to another account, or connection changed. Fetch again.')
                rows=json.loads(row[0]);conn.execute('DELETE FROM invoice_previews WHERE owner=?',(user['uid'],))
            store.save(user['uid'],provider,rows);discard_plans(user['uid']);store.event(user['uid'],'import_'+provider,'IMPORTED',f'Imported {len(rows)} invoices from {provider}; prior approvals invalidated.')
        return {'status':'IMPORTED','count':len(rows)}

    @app.post('/api/connections/{provider}/disconnect')
    def disconnect(provider:str,user=Depends(identity)):
        signed(user);provider_check(provider)
        with owner_lock(user['uid']):
            with store.db() as conn:
                table(conn);conn.execute('DELETE FROM invoice_connections WHERE owner=? AND provider=?',(user['uid'],provider));conn.execute('DELETE FROM invoice_previews WHERE owner=? AND provider=?',(user['uid'],provider))
                if provider=='zoho':conn.execute('DELETE FROM invoice_oauth WHERE owner=?',(user['uid'],))
            if store.source(user['uid'])[0]==provider:store.save(user['uid'],'upload',[])
            discard_plans(user['uid']);store.event(user['uid'],'disconnect_'+provider,'DISCONNECTED','Stored connection removed and approvals revoked. Revoke provider access in its dashboard to invalidate credentials globally.')
        return {'status':'DISCONNECTED'}
