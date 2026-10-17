"""Non-secret runtime configuration diagnostics; does not claim connectivity."""
import os
from urllib.parse import urlparse
from uuid import UUID

from integration_errors import ConfigurationError

# Verified against the installed production SDK 0.6.10. Do not inherit generic
# BACKEND_ENDPOINT/PROXY_ENDPOINT variables from another application/service.
SDK_ENDPOINTS = {'iap_endpoint': 'https://iap.armoriq.ai',
                 'proxy_endpoint': 'https://proxy.armoriq.ai',
                 'backend_endpoint': 'https://api.armoriq.ai'}


def armoriq_configuration():
    checks = []
    issues = []

    def check(name, valid, invalid_reason):
        value = os.environ.get(name, '')
        status = 'missing' if not value.strip() else 'present' if valid else 'invalid'
        checks.append({'name': name, 'status': status})
        if status != 'present':
            issues.append({'code': name.lower() + '_' + status, 'variable': name,
                           'message': f'{name} is missing on the running backend.' if status == 'missing' else invalid_reason})

    key = os.environ.get('ARMORIQ_API_KEY', '')
    check('ARMORIQ_API_KEY', key == key.strip() and key.startswith(('ak_live_', 'ak_test_')) and len(key) > 12,
          'ARMORIQ_API_KEY must contain the actual ArmorIQ API credential, without quotes or surrounding whitespace. A Secret label, client key or organization ID is not an API key.')
    expected = os.environ.get('ARMORIQ_EXPECTED_ORG_ID', '')
    try:
        UUID(expected)
        valid_org = expected == expected.strip()
    except (ValueError, AttributeError):
        valid_org = False
    check('ARMORIQ_EXPECTED_ORG_ID', valid_org,
          'ARMORIQ_EXPECTED_ORG_ID must be the organization UUID belonging to the API key, not a credential or workspace display name.')
    agent = os.environ.get('ARMORIQ_AGENT_ID','')
    check('ARMORIQ_AGENT_ID', bool(agent.strip()) and agent == agent.strip() and len(agent)<200 and not agent.startswith(('ak_','sk_')),
          'ARMORIQ_AGENT_ID must be the exact existing SDK agent identifier resolved from the registry, not an API key or an assumed display name.')
    try:
        UUID(os.environ.get('ARMORIQ_MCP_SERVER_ID','')); valid_server = True
    except ValueError:valid_server = False
    check('ARMORIQ_MCP_SERVER_ID', valid_server,
          'ARMORIQ_MCP_SERVER_ID must be the UUID of the existing MCP dashboard record. Do not create a replacement registration.')
    try:
        endpoint = urlparse(os.environ.get('MCP_SERVER_URL', ''))
        valid_url = endpoint.scheme == 'https' and bool(endpoint.hostname) and endpoint.path.rstrip('/').endswith('/mcp') and not any([endpoint.username, endpoint.password, endpoint.query, endpoint.fragment])
    except ValueError:
        valid_url = False
    check('MCP_SERVER_URL', valid_url, 'MCP_SERVER_URL must be a public HTTPS /mcp endpoint without embedded credentials, query strings or fragments.')
    check('FINANCEGUARD_SCOPED_MCP', os.environ.get('FINANCEGUARD_SCOPED_MCP') == '1',
          'FINANCEGUARD_SCOPED_MCP must be 1 so the SDK forwards workspace-scoped credentials to the MCP origin.')
    signing = os.environ.get('FINANCEGUARD_MCP_SIGNING_KEY', '')
    check('FINANCEGUARD_MCP_SIGNING_KEY', len(signing) >= 32 and signing == signing.strip(),
          'FINANCEGUARD_MCP_SIGNING_KEY must be a private shared random key of at least 32 characters on the backend and MCP origin.')
    return {'configuration_status': 'missing' if any(c['status'] == 'missing' for c in checks) else 'invalid' if issues else 'configured',
            'checks': checks, 'issues': issues, 'connectivity': 'not_checked', 'execution': 'not_verified'}


def require_armoriq_configuration():
    result = armoriq_configuration()
    if result['issues']:
        issue = result['issues'][0]
        scope = os.environ.get('VERCEL_ENV', 'production').title()
        host = f'Vercel {scope} environment settings, then create a new {scope} deployment' if os.environ.get('VERCEL') == '1' else 'the backend environment or ignored local .env, then restart the backend'
        raise ConfigurationError(issue['message'] + ' Update ' + host + '.', issue['code'])
    return result


def deployment_metadata():
    return {'host': 'vercel' if os.environ.get('VERCEL') == '1' else 'local',
            'environment': os.environ.get('VERCEL_ENV', 'local'),
            'revision': os.environ.get('VERCEL_GIT_COMMIT_SHA', '')[:12] or None,
            'backend_origin': 'same-origin', 'sdk_version': '0.6.10',
            'shared_state_required': os.environ.get('VERCEL') == '1'}
