"""Read-only SDK configuration audit. Outputs identities and health, never secrets."""
import json,os,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from dotenv import load_dotenv
load_dotenv(ROOT/'.env')

def main():
    from armoriq_sdk import ArmorIQClient
    from armoriq_sdk.config import MCPServerConfig
    from armoriq_sdk.cli import discover_mcp_tools
    from armoriq_workflow import TARGET_ORG
    if not os.environ.get('ARMORIQ_API_KEY'):
        print(json.dumps({'ready':False,'reason':'ARMORIQ_API_KEY is missing'}));return 1
    result={'expected_organization':os.environ.get('ARMORIQ_EXPECTED_ORG_ID',TARGET_ORG)}
    try:
        with ArmorIQClient(api_key=os.environ['ARMORIQ_API_KEY']) as client:
            data=client.bootstrap();result['organization_id']=(data.get('org') or {}).get('orgId')
            result['organization_matches']=result['organization_id']==result['expected_organization']
            server=next((m for m in client.list_mcps() if m.get('name')=='finance-mcp'),None)
            result['mcp_registered']=bool(server)
            if server:
                result['registered_mcp_url']=server.get('url')
                result['configured_url_matches']=bool(os.environ.get('MCP_SERVER_URL')) and os.environ['MCP_SERVER_URL'].rstrip('/')==server.get('url','').rstrip('/')
                discovery=discover_mcp_tools(MCPServerConfig(id='finance-mcp',url=server['url']),timeout=10)
                result['mcp_reachable']=discovery.reachable;result['tool_count']=len(discovery.tools)
            result['ready']=all(result.get(k) for k in ['organization_matches','mcp_registered','configured_url_matches','mcp_reachable']) and result.get('tool_count')==8
    except Exception as exc:result.update(ready=False,error_type=type(exc).__name__)
    print(json.dumps(result,indent=2));return 0 if result.get('ready') else 1

if __name__=='__main__':raise SystemExit(main())
