"""Prepare an ignored private Vercel import file without printing its secrets."""
import os
import secrets
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from dotenv import dotenv_values,set_key


def main():
    from armoriq_sdk import ArmorIQClient
    values=dotenv_values(ROOT/'.env')
    key=values.get('ARMORIQ_API_KEY') or os.environ.get('ARMORIQ_API_KEY')
    if not key:raise SystemExit('ARMORIQ_API_KEY is missing from private configuration.')
    # Validate before copying. Do not print the key or arbitrary provider errors.
    try:
        with ArmorIQClient(api_key=key,timeout=12,max_retries=0) as client:
            org=(client.bootstrap().get('org') or {}).get('orgId')
    except Exception as exc:
        raise SystemExit('ArmorIQ identity validation failed: '+type(exc).__name__)
    expected=values.get('ARMORIQ_EXPECTED_ORG_ID')
    if not org or expected and expected!=org:
        raise SystemExit('Expected organization differs from the authenticated key; no files changed.')
    runtime=ROOT/'runtime'
    runtime.mkdir(exist_ok=True)
    signing=values.get('FINANCEGUARD_MCP_SIGNING_KEY')
    if not signing:
        existing=runtime/'mcp-signing.key'
        signing=existing.read_text().strip() if existing.exists() else secrets.token_urlsafe(48)
    if len(signing)<32:raise SystemExit('The existing signing key is too short; no files changed.')
    prepared={
        'ARMORIQ_API_KEY':key,
        'ARMORIQ_EXPECTED_ORG_ID':org,
        'ARMORIQ_AGENT_ID':values.get('ARMORIQ_AGENT_ID') or 'financeguard-demo',
        'ARMORIQ_OBSERVABILITY':'true',
        'MCP_SERVER_URL':'https://financeguard-armoriq.vercel.app/mcp',
        'FINANCEGUARD_SCOPED_MCP':'1',
        'FINANCEGUARD_MCP_SIGNING_KEY':signing,
        'FIREBASE_PROJECT_ID':values.get('FIREBASE_PROJECT_ID') or 'asmoneykit',
        'FINANCEGUARD_ALLOWED_HOSTS':'financeguard-armoriq.vercel.app',
        'FINANCEGUARD_HTTPS':'1',
    }
    output=runtime/'vercel-production.env'
    output.write_text('# PRIVATE: import in Vercel Production. Never commit or share.\n')
    for name,value in prepared.items():set_key(str(output),name,value)
    # Match local signing/registry settings while preserving all other entries.
    for name in ['ARMORIQ_EXPECTED_ORG_ID','MCP_SERVER_URL','FINANCEGUARD_SCOPED_MCP','FINANCEGUARD_MCP_SIGNING_KEY']:
        set_key(str(ROOT/'.env'),name,prepared[name])
    print('Authenticated organization:',org)
    print('Private Vercel import file: runtime/vercel-production.env (Git-ignored)')
    print('Public MCP endpoint:',prepared['MCP_SERVER_URL'])
    print('Credentials were not printed. Import the private file into Vercel Production and redeploy.')


if __name__=='__main__':main()
