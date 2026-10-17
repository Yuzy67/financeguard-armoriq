"""Real, read-only diagnostics. Never registers, scans, deploys or alters policies."""
import argparse,asyncio,json,logging,sys
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
logging.disable(logging.CRITICAL)

async def mcp_probe(url):
    import httpx
    from mcp import ClientSession
    from mcp.client.streamable_http import streamable_http_client
    report={'endpoint':url,'transport':'Streamable HTTP'}
    try:
        async with httpx.AsyncClient(timeout=20,follow_redirects=False) as http:
            async with streamable_http_client(url,http_client=http) as (read,write,_):
                async with ClientSession(read,write) as session:
                    init=await session.initialize();tools=await session.list_tools()
                    report.update(initialized=True,protocol_version=init.protocolVersion,server_name=init.serverInfo.name,tools=[t.name for t in tools.tools])
                    result=await session.call_tool('summarize_overdue_invoices',{})
                    report['unauthenticated_summary_denied']=result.isError
                    report['invoice_data_received']=not result.isError
    except Exception as exc:report.update(initialized=False,error_type=type(exc).__name__)
    return report


def live_trace(base):
    import httpx
    report={'frontend_contract':'frontend/app.js api() uses same-origin approval and execution routes','requests':[],
            'policy_decision_confirmed':False,'dashboard_decision_confirmed':False,'tool_execution_confirmed':False}
    with httpx.Client(base_url=base,timeout=45,follow_redirects=False) as client:
        for path,body in [('/api/demo',{}),('/api/state',None),('/api/approve',{'tool':'summarize_overdue_invoices','engine':'armoriq'}),('/api/run-approved-action',{'engine':'armoriq'}),('/api/attempt-refund',{'engine':'armoriq'})]:
            try:
                response=client.get(path) if body is None else client.post(path,json=body)
                data=response.json()
                event=data.get('event') or {};obs=event.get('observability') or {}
                entry={'path':path,'http_status':response.status_code}
                for name in ['status','verified','code','category','exception']:
                    if isinstance(data.get(name),(str,bool,int)):entry[name]=data[name]
                # Application reasons are already sanitized; never return arbitrary
                # HTML, upstream exception strings, tokens or invoice/customer data.
                reason=data.get('reason') or data.get('detail')
                if isinstance(reason,str) and len(reason)<400:entry['reason']=reason
                if event.get('engine'):entry['decision_source']=event['engine']
                entry['observability']={k:obs[k] for k in ['session_id','trace_ids','organization_id','agent_id','agent_registry_verified','mcp_server_id','delivery','accepted','rejected','console_verified','runtime_policy'] if k in obs}
                policy=obs.get('runtime_policy') or {}
                if policy.get('source')=='ARMORIQ_ENFORCEMENT_API' and policy.get('http_status')==200 and isinstance(policy.get('allowed'),bool):report['policy_decision_confirmed']=True
                if path=='/api/state':
                    entry['sample_workspace']=data.get('source')=='sample'
                    report['requests'].append(entry)
                    if response.status_code!=200 or data.get('source')!='sample':
                        report['blocked_at']='synthetic_workspace_validation';break
                    continue
                if path=='/api/run-approved-action':
                    result=data.get('result') or {}
                    if isinstance(result,dict):entry['summary']={k:result[k] for k in ['overdue_invoice_count','total_overdue_amount_inr'] if k in result}
                    report['tool_execution_confirmed']=data.get('status','').upper()=='ALLOWED' and bool(entry.get('summary'))
                report['requests'].append(entry)
                if path in {'/api/demo','/api/approve'} and (response.status_code!=200 or path=='/api/approve' and data.get('status')!='APPROVED'):
                    report['blocked_at']=path;break
            except Exception as exc:
                report['requests'].append({'path':path,'error_type':type(exc).__name__});report['blocked_at']=path;break
    return report


def service_probe():
    import os,httpx
    from dotenv import load_dotenv
    from runtime_config import SDK_ENDPOINTS,armoriq_configuration
    load_dotenv(ROOT/'.env')
    key=os.environ.get('ARMORIQ_API_KEY','')
    report={'configuration':armoriq_configuration(),'key_source':'backend environment / ignored local .env','requests':[]}
    if not key:return report
    with httpx.Client(timeout=15,follow_redirects=False,verify=True) as client:
        requests=[('sdk_proxy_health','GET',SDK_ENDPOINTS['proxy_endpoint']+'/health'),('sdk_bootstrap','POST',SDK_ENDPOINTS['backend_endpoint']+'/iap/sdk/bootstrap')]
        for stage,method,url in requests:
            try:
                kwargs={'headers':{'X-API-Key':key,'Authorization':'Bearer '+key}}
                if method=='POST':kwargs['json']={}
                response=client.request(method,url,**kwargs)
                json_api='application/json' in response.headers.get('content-type','').lower()
                entry={'stage':stage,'endpoint':url,'http_status':response.status_code,'json_api_response':json_api,
                       'credential_validity':'unconfirmed','policy_decision':False}
                if stage=='sdk_bootstrap' and response.is_success and json_api:
                    data=response.json();org=data.get('org') or {};agent=data.get('agent') or {}
                    entry.update(organization_id=org.get('orgId') or org.get('id'),credential_validity='bootstrap_accepted')
                    entry['agent_identity_fields_exposed']=[k for k in ['id','agentId','agent_id','name'] if isinstance(agent,dict) and k in agent]
                report['requests'].append(entry)
            except httpx.HTTPError as exc:report['requests'].append({'stage':stage,'network_error_type':type(exc).__name__,'credential_validity':'unconfirmed'})
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--live',action='store_true',help='Exercise only a fresh sample workspace on the deployed app')
    parser.add_argument('--local-services',action='store_true',help='Probe real SDK services with securely configured local credentials')
    parser.add_argument('--output',type=Path,help='Write sanitized evidence JSON')
    args=parser.parse_args()
    base='https://financeguard-armoriq.vercel.app'
    from importlib.metadata import version
    report={'sdk_version':version('armoriq-sdk'),'timestamp_utc':datetime.now(timezone.utc).isoformat(),'existing_mcp_record_id':'2da563ef-544e-4db7-a418-0c404cf75180',
            'registry_read_access':'not_established','policy_target':'unconfirmed','security_scan_started':False}
    import httpx
    try:
        response=httpx.get(base+'/api/health',timeout=20)
        health=response.json();report['production_health']={'http_status':response.status_code,**{k:health.get(k) for k in ['storage','armoriq_configured','mcp_signing_configured','mcp_url_configured','deployment']}}
    except Exception as exc:report['production_health']={'error_type':type(exc).__name__}
    report['mcp']=asyncio.run(mcp_probe(base+'/mcp'))
    if args.live:report['live_trace']=live_trace(base)
    if args.local_services:report['local_services']=service_probe()
    if args.output:
        args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report,indent=2))
    return 0

if __name__=='__main__':raise SystemExit(main())
