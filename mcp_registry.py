"""Normalize registry identifiers without relaxing the existing resource binding."""
from uuid import UUID

from integration_errors import ConfigurationError


def uuid_string(value):
    try:
        return str(UUID(value)) if isinstance(value, str) else None
    except ValueError:
        return None


def resolve_existing_mcp(records, expected_id):
    """The live /mcp/my-servers DTO uses mcpId; older fixtures used id."""
    expected = uuid_string(expected_id)
    if not expected:
        raise ConfigurationError('ARMORIQ_MCP_SERVER_ID must be the existing record UUID.', 'mcp_registry_id_invalid')
    if not isinstance(records, list) or any(not isinstance(row, dict) for row in records):
        raise ConfigurationError('ArmorIQ registry returned an unsupported record list. No resource binding was inferred.', 'mcp_registry_response_invalid')
    matches = []
    for row in records:
        current, legacy = uuid_string(row.get('mcpId')), uuid_string(row.get('id'))
        if expected not in {current, legacy}:
            continue
        if current and legacy and current != legacy:
            raise ConfigurationError('ArmorIQ returned conflicting identifiers for this MCP record. Execution refused.', 'mcp_registry_id_conflict')
        matches.append({**row, 'id': current or legacy})
    if len(matches) > 1:
        raise ConfigurationError('ArmorIQ returned duplicate entries for the configured MCP UUID. Execution refused.', 'mcp_registry_ambiguous')
    return matches[0] if matches else None
