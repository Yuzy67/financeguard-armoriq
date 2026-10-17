"""Sanitized integration failures. Never return provider bodies or credentials."""
import re
import httpx


class IntegrationError(RuntimeError):
    def __init__(self, message, code='provider_error', category='provider', http_status=502, provider_status=None):
        super().__init__(message)
        self.code = code
        self.category = category
        self.http_status = http_status
        self.provider_status = provider_status


class ConfigurationError(IntegrationError):
    def __init__(self, message, code='configuration_error'):
        super().__init__(message, code, 'configuration', 503)


def classify(exc):
    if isinstance(exc, IntegrationError):
        return {'code': exc.code, 'category': exc.category, 'reason': str(exc),
                'http_status': exc.http_status, 'provider_status': exc.provider_status,
                'status': 'HELD' if exc.code == 'policy_hold' else 'BLOCKED' if exc.category in {'policy', 'token'} else 'ERROR'}
    name = type(exc).__name__
    definitions = {
        'IntentMismatchException': ('intent_mismatch', 'policy', 'IntentMismatchException: action is outside the approved plan. Nothing executed.'),
        'PolicyBlockedException': ('policy_denied', 'policy', 'ArmorIQ policy denied this action. No tool executed.'),
        'ActionDenied': ('policy_denied', 'policy', 'Action is outside the approved scope or ArmorIQ denied it. No tool executed.'),
        'PolicyHoldException': ('policy_hold', 'policy', 'ArmorIQ requires additional approval. No tool executed.'),
        'RevokedTokenError': ('token_revoked', 'token', 'ArmorIQ rejected a revoked intent token. Approve a new plan.'),
        'TokenExpiredException': ('token_expired', 'token', 'The intent token expired. Approve a new plan.'),
        'InvalidTokenException': ('token_invalid', 'token', 'ArmorIQ rejected the intent token. It may be invalid or revoked; no verified success is claimed.'),
    }
    if name in definitions:
        code, category, reason = definitions[name]
        return {'code': code, 'category': category, 'reason': reason, 'http_status': 200,
                'provider_status': None, 'status': 'BLOCKED'}
    if isinstance(exc, BaseExceptionGroup):
        return classify(exc.exceptions[0])
    status = getattr(exc, 'status_code', None)
    if isinstance(exc, httpx.HTTPStatusError):
        status = exc.response.status_code
        if status in {401,403} and 'text/html' in exc.response.headers.get('content-type','').lower():
            return classify(IntegrationError('The service returned an HTML access-denied page before a valid ArmorIQ API response. Credential validity is unconfirmed; check service access from this backend.', 'service_access_denied', 'network', provider_status=status))
    # SDK ConfigurationException embeds bootstrap status in text. Inspect only
    # a numeric marker; never include the arbitrary text/body in our response.
    if name == 'ConfigurationException':
        match = re.search(r'(?:failed:|HTTP)\s*(\d{3})\b', str(exc))
        status = int(match[1]) if match else status
        if 'Invalid or revoked API key' in str(exc):
            # SDK 0.6.10 maps BOTH 401 and 403 to this message and drops
            # the response. Do not invent a status or claim a revoked key.
            return classify(IntegrationError('ArmorIQ SDK credential validation failed before policy execution. The SDK does not expose whether the underlying response was 401 or 403; check backend service access and credentials.', 'sdk_authentication_check_failed', 'authentication'))
    if status in {401, 403}:
        return classify(IntegrationError('ArmorIQ rejected the API credential or its account access. Verify the API key and organization on this backend.',
                        'authentication_failed', 'authentication', provider_status=status))
    if isinstance(exc, httpx.TimeoutException):
        return classify(IntegrationError('ArmorIQ or MCP timed out. Inspect activity before retrying; execution is not confirmed.', 'network_timeout', 'network'))
    if isinstance(exc, httpx.RequestError):
        return classify(IntegrationError('The backend could not securely reach ArmorIQ or MCP. Check the registered HTTPS origin and service availability.', 'network_error', 'network'))
    if name == 'MCPInvocationException':
        return classify(IntegrationError('ArmorIQ proxy could not complete the MCP tool. Check the registered origin, scoped credentials and tool health.', 'mcp_invocation_failed', 'tool', provider_status=status))
    if status and status >= 500:
        return classify(IntegrationError('ArmorIQ returned a service error. No verified tool success is claimed.', 'provider_unavailable', 'provider', provider_status=status))
    return classify(IntegrationError('The integration operation failed. No verified tool success is claimed; inspect the connection check and action trail.', 'integration_failed', 'tool'))
