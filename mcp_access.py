"""Short-lived, owner/action/data-scoped credentials for our MCP origin."""
import asyncio,hashlib,json,os,secrets,time
from pathlib import Path
import jwt
from contextlib import contextmanager
import workspace as store

def secret():
    configured=os.environ.get('FINANCEGUARD_MCP_SIGNING_KEY')
    if configured:
        if len(configured)<32:raise RuntimeError('FINANCEGUARD_MCP_SIGNING_KEY must contain at least 32 characters.')
        return configured
    path=store.RUNTIME/'mcp-signing.key'
    try:
        with path.open('x',encoding='utf-8') as output:output.write(secrets.token_urlsafe(48))
    except FileExistsError:pass
    value=path.read_text(encoding='utf-8').strip()
    if len(value)<32:raise RuntimeError('MCP signing key is unavailable.')
    return value

def fingerprint(rows):return hashlib.sha256(json.dumps(rows,sort_keys=True).encode()).hexdigest()

@contextmanager
def grants():
    with store.db() as connection:
        connection.execute('CREATE TABLE IF NOT EXISTS mcp_grants(id TEXT PRIMARY KEY,owner TEXT NOT NULL,expires INTEGER NOT NULL,revoked INTEGER NOT NULL DEFAULT 0)')
        yield connection

def revoke_owner(owner):
    with grants() as conn:conn.execute('UPDATE mcp_grants SET revoked=1 WHERE owner=?',(owner,))

def revoke_token(token):
    claims=jwt.decode(token,secret(),algorithms=['HS256'],audience='finance-mcp',issuer='financeguard-backend',options={'verify_exp':False})
    with grants() as conn:conn.execute('UPDATE mcp_grants SET revoked=1 WHERE id=?',(claims.get('jti',''),))

def issue(owner,tool,rows):
    now=int(time.time());identifier=secrets.token_urlsafe(32)
    token=jwt.encode({'sub':owner,'aud':'finance-mcp','iss':'financeguard-backend','jti':identifier,'tool':tool,'data':fingerprint(rows),'iat':now,'exp':now+300},secret(),algorithm='HS256')
    with grants() as conn:
        conn.execute('DELETE FROM mcp_grants WHERE expires<?',(now,))
        conn.execute('INSERT INTO mcp_grants(id,owner,expires) VALUES (?,?,?)',(identifier,owner,now+300))
    return token

def authorized_rows(ctx,tool):
    request=ctx.request_context.request
    header=request.headers.get('authorization','') if request else ''
    if not header.startswith('Bearer '):raise PermissionError('MCP workspace authorization required.')
    try:
        claims=jwt.decode(header[7:],secret(),algorithms=['HS256'],audience='finance-mcp',issuer='financeguard-backend',options={'require':['sub','jti','tool','data','exp','iat']})
        with grants() as conn:
            active=conn.execute('SELECT 1 FROM mcp_grants WHERE id=? AND owner=? AND revoked=0 AND expires>?',(claims['jti'],claims['sub'],int(time.time()))).fetchone()
        if not active:raise ValueError('Approval is revoked or unavailable on this MCP origin.')
        if claims['tool']!=tool:raise ValueError('Tool outside approved scope.')
        _,rows=store.source(claims['sub'])
        if claims['data']!=fingerprint(rows):raise ValueError('Invoice data changed. Reapprove the plan.')
        return rows
    except (jwt.PyJWTError,ValueError,KeyError):raise PermissionError('MCP authorization invalid, expired, or outside the approved scope.') from None

async def _invoke(tool,token):
    import httpx
    from mcp import ClientSession
    from mcp.client.streamable_http import streamable_http_client
    async def call(http,url):
        async with streamable_http_client(url,http_client=http) as (read,write,_):
            async with ClientSession(read,write) as session:
                await session.initialize()
                result=await session.call_tool(tool,{})
                if result.isError:raise RuntimeError('MCP rejected the execution. Reapprove or inspect connection health.')
                return json.loads(result.content[0].text)
    headers={'Authorization':'Bearer '+token}
    if os.environ.get('VERCEL')=='1':
        # No listener exists on localhost in a function. Still use real MCP
        # initialize/tools/call over HTTP via ASGI, with the same scoped auth.
        from finance_mcp.server import create_server
        origin=create_server()
        asgi=origin.streamable_http_app()
        async with origin.session_manager.run():
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=asgi),headers=headers,timeout=20) as http:
                return await call(http,'http://127.0.0.1:8002/mcp')
    url='http://127.0.0.1:'+os.environ.get('FINANCEGUARD_PORT','8001')+'/mcp'
    async with httpx.AsyncClient(headers=headers,timeout=20) as http:
        return await call(http,url)

def invoke(tool,token):return asyncio.run(_invoke(tool,token))
