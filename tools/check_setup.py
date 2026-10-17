"""Read-only SDK configuration audit. Outputs identities and health, never secrets."""
import json,os,sys,logging
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from dotenv import load_dotenv
from mcp_registry import resolve_existing_mcp
load_dotenv(ROOT/'.env')

def main():
    from armoriq_sdk import ArmorIQClient
    from armoriq_sdk.config import MCPServerConfig
    from armoriq_sdk.cli import discover_mcp_tools
    from runtime_config import require_armoriq_configuration,SDK_ENDPOINTS
    from integration_errors import classify
    # The SDK can log arbitrary upstream exception bodies. This diagnostic only
    # emits its explicit whitelist below; never raw exceptions or headers.
    logging.disable(logging.CRITICAL)
    result={'expected_organization':os.environ.get('ARMORIQ_EXPECTED_ORG_ID'),
            'configured_agent_id':os.environ.get('ARMORIQ_AGENT_ID'),
            'policy_attachment_verified':False,'runtime_policy_decision_verified':False,
            'tool_execution_verified':False,'end_to_end_verified':False,
            'scope':'Read-only identity, registry and discovery checks; not an execution or policy-attachment test.'}
    try:
        require_armoriq_configuration()
        with ArmorIQClient(api_key=os.environ['ARMORIQ_API_KEY'],agent_id=os.environ.get('ARMORIQ_AGENT_ID'),timeout=15,max_retries=0,verify_ssl=True,**SDK_ENDPOINTS) as client:
            data=client.bootstrap();result['organization_id']=(data.get('org') or {}).get('orgId')
            result['organization_matches']=result['organization_id']==result['expected_organization']
            agent=data.get('agent') or {}
            identity=(agent.get('agentId') or agent.get('agent_id')) if isinstance(agent,dict) else None
            result['bootstrap_agent_identity_exposed']=bool(identity)
            result['bootstrap_agent_matches']=identity==client.agent_id if identity else None
            server=resolve_existing_mcp(client.list_mcps(),os.environ.get('ARMORIQ_MCP_SERVER_ID'))
            result['mcp_registered']=bool(server)
            result['mcp_record_id']=server.get('id') if server else None
            result['mcp_routing_name_matches']=bool(server and server.get('name')=='finance-mcp')
            if server:
                result['configured_url_matches']=bool(os.environ.get('MCP_SERVER_URL')) and os.environ['MCP_SERVER_URL'].rstrip('/')==server.get('url','').rstrip('/')
                discovery=discover_mcp_tools(MCPServerConfig(id='finance-mcp',url=server['url']),timeout=10)
                result['mcp_reachable']=discovery.reachable;result['tool_count']=len(discovery.tools)
            result['connection_ready']=all(result.get(k) for k in ['organization_matches','mcp_registered','mcp_routing_name_matches','configured_url_matches','mcp_reachable']) and result.get('tool_count')==8 and result.get('bootstrap_agent_matches') is not False
    except Exception as exc:result.update(connection_ready=False,error=classify(exc))
    print(json.dumps(result,indent=2));return 0 if result.get('connection_ready') else 1

if __name__=='__main__':raise SystemExit(main())
