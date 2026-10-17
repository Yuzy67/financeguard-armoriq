"""Read-only proposal for the EXISTING MCP record. Never creates/updates policy or registry rows."""
import argparse,json,logging,os,sys
from pathlib import Path
from urllib.parse import urlsplit,urlunsplit
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from dotenv import load_dotenv
load_dotenv(ROOT/'.env')

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('url',help='Proposed verified public HTTPS /mcp URL, not a dashboard URL')
    args=parser.parse_args();url=urlsplit(args.url)
    if url.scheme!='https' or not url.hostname or url.username or url.password or url.query or url.fragment or not url.path.rstrip('/').endswith('/mcp'):
        parser.error('Use a confirmed HTTPS /mcp service URL without embedded credentials, query or fragment.')
    logging.disable(logging.CRITICAL)
    from armoriq_sdk import ArmorIQClient
    from runtime_config import SDK_ENDPOINTS,require_armoriq_configuration
    from integration_errors import classify
    try:
        require_armoriq_configuration()
        with ArmorIQClient(api_key=os.environ['ARMORIQ_API_KEY'],agent_id=os.environ['ARMORIQ_AGENT_ID'],timeout=15,max_retries=0,verify_ssl=True,**SDK_ENDPOINTS) as client:
            organization=(client.bootstrap().get('org') or {}).get('orgId')
            if organization!=os.environ['ARMORIQ_EXPECTED_ORG_ID']:raise ValueError('organization_mismatch')
            record=next((m for m in client.list_mcps() if m.get('id')==os.environ['ARMORIQ_MCP_SERVER_ID']),None)
            if not record:raise ValueError('existing_record_not_resolved')
            current=urlsplit(record.get('url',''))
            print(json.dumps({'mode':'proposal_only','organization_id':organization,'agent_id':os.environ['ARMORIQ_AGENT_ID'],'existing_mcp_record_id':record['id'],'existing_name':record.get('name'),'current_endpoint':urlunsplit((current.scheme,current.hostname or '',current.path,'','')),'proposed_endpoint':args.url,'policy_change':None,'remote_changes_applied':False,'next_step':'Review the existing policy target/rules and obtain approval before updating this exact record.'},indent=2))
    except Exception as exc:
        print(json.dumps({'remote_changes_applied':False,'error':classify(exc)}));return 1
    return 0

if __name__=='__main__':raise SystemExit(main())
