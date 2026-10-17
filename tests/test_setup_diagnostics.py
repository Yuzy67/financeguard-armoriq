"""Discovery readiness must never imply policy attachment or execution."""
import contextlib,io,json,os,unittest
from types import SimpleNamespace
from unittest.mock import MagicMock,patch
from tools.check_setup import main

class SetupDiagnosticsTests(unittest.TestCase):
    def inspect(self, routing_name='finance-mcp', bootstrap_agent='existing-agent'):
        identifier='2da563ef-544e-4db7-a418-0c404cf75180'
        client=MagicMock()
        client.__enter__.return_value=client
        client.agent_id='existing-agent'
        client.bootstrap.return_value={'org':{'orgId':'expected-org'},'agent':{'agentId':bootstrap_agent}}
        client.list_mcps.return_value=[{'id':identifier,'name':routing_name,'url':'https://origin.example/mcp'}]
        output=io.StringIO()
        with patch.dict(os.environ,{'ARMORIQ_EXPECTED_ORG_ID':'expected-org','ARMORIQ_AGENT_ID':'existing-agent','ARMORIQ_MCP_SERVER_ID':identifier,'ARMORIQ_API_KEY':'ak_test_placeholder','MCP_SERVER_URL':'https://origin.example/mcp'}), patch('runtime_config.require_armoriq_configuration'), patch('armoriq_sdk.ArmorIQClient',return_value=client), patch('armoriq_sdk.cli.discover_mcp_tools',return_value=SimpleNamespace(reachable=True,tools=[None]*8)), contextlib.redirect_stdout(output):
            status=main()
        return status,json.loads(output.getvalue())

    def test_discovery_is_separate_from_policy_and_execution(self):
        status,result=self.inspect()
        self.assertEqual(status,0)
        self.assertTrue(result['connection_ready'])
        for field in ['policy_attachment_verified','runtime_policy_decision_verified','tool_execution_verified','end_to_end_verified']:
            self.assertFalse(result[field])
        self.assertNotIn('ak_test_placeholder',json.dumps(result))

    def test_wrong_routing_name_is_not_connection_ready(self):
        status,result=self.inspect(routing_name='different-server')
        self.assertEqual(status,1)
        self.assertFalse(result['connection_ready'])

    def test_mismatched_bootstrap_identity_is_not_connection_ready(self):
        status,result=self.inspect(bootstrap_agent='other-agent')
        self.assertEqual(status,1)
        self.assertFalse(result['connection_ready'])
