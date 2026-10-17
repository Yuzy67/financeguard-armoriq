"""User consent is an additional restriction, never an ArmorIQ policy override."""
import json
from datetime import datetime, timezone

import assistant_brain as brain

MODES = {'ask', 'automatic', 'never'}


def defaults():
    return {tool: 'ask' for tool in brain.SAFE}


def load(store, owner):
    with store.db() as conn:
        conn.execute('CREATE TABLE IF NOT EXISTS assistant_permissions(owner TEXT PRIMARY KEY,payload TEXT NOT NULL)')
        row = conn.execute('SELECT payload FROM assistant_permissions WHERE owner=?', (owner,)).fetchone()
    data = json.loads(row[0]) if row else {}
    # Missing or corrupt permissions never imply consent.
    tools = {tool: (data.get('tools', {}).get(tool) if data.get('tools', {}).get(tool) in MODES else 'ask') for tool in brain.SAFE}
    return {'configured': bool(row), 'tools': tools, 'updated_at': data.get('updated_at'),
            'storage': 'temporary' if store.TEMPORARY_STORAGE else 'persistent',
            'provider_policy_modified': False, 'automatic_engine': 'armoriq'}


def save(store, owner, tools):
    if set(tools) != set(brain.SAFE) or any(mode not in MODES for mode in tools.values()):
        raise ValueError('Choose ask, automatic or never for every supported safe task. Financial mutations cannot be enabled.')
    data = {'tools': tools, 'updated_at': datetime.now(timezone.utc).isoformat()}
    with store.db() as conn:
        conn.execute('CREATE TABLE IF NOT EXISTS assistant_permissions(owner TEXT PRIMARY KEY,payload TEXT NOT NULL)')
        conn.execute('INSERT OR REPLACE INTO assistant_permissions VALUES (?,?)', (owner, json.dumps(data)))
    return load(store, owner)
