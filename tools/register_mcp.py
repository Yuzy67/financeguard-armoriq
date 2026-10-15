"""Register a tunnel URL using the installed ArmorIQ SDK CLI implementation."""
import argparse,json,sys
from pathlib import Path
from urllib.parse import urlparse
from dotenv import load_dotenv
ROOT=Path(__file__).resolve().parents[1]
load_dotenv(ROOT/'.env')
from armoriq_sdk.config import ArmorIQConfig,IdentityConfig,MCPServerConfig,PolicyConfig
from armoriq_sdk.cli import discover_mcp_tools,_register_with_control_plane
parser=argparse.ArgumentParser()
parser.add_argument('url',help='Current public HTTPS endpoint including /mcp')
args=parser.parse_args()
parsed=urlparse(args.url)
if parsed.scheme!='https' or not parsed.hostname or parsed.username or parsed.password or parsed.query:
    parser.error('Use a public HTTPS /mcp URL without embedded credentials or query secrets.')
server=MCPServerConfig(id='finance-mcp',url=args.url,description='FinanceGuard workspace-scoped MCP')
discovery=discover_mcp_tools(server,timeout=15)
if not discovery.reachable or len(discovery.tools)!=8:raise SystemExit('MCP discovery did not return eight tools. Check origin and tunnel.')
safe=['list_invoices','get_invoice_details','summarize_overdue_invoices','create_draft_payment_reminders','export_sandbox_reports']
config=ArmorIQConfig(identity=IdentityConfig(api_key='$ARMORIQ_API_KEY',user_id='financeguard-operator',agent_id='financeguard-demo'),mcp_servers=[server],policy=PolicyConfig(allow=['finance-mcp.'+t for t in safe],deny=['finance-mcp.'+t for t in ['simulate_refunds','transfer_funds','delete_invoices']]))
response=_register_with_control_plane(config)
print('Registered:',response.get('success',False),'tools:',len(discovery.tools))
print('Use the installed SDK production endpoint; a legacy proxy returned by registration may not accept current keys.')
