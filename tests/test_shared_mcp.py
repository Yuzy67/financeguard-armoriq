"""Exercise scoped MCP calls across isolated temporary function stores."""
import tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import mcp_access,workspace

class SharedMCPCredentialTests(unittest.TestCase):
    def test_separate_origin_without_shared_grant_store_fails_closed(self):
        with tempfile.TemporaryDirectory() as first,tempfile.TemporaryDirectory() as second,patch.dict('os.environ',{'VERCEL':'1','FINANCEGUARD_MCP_SIGNING_KEY':'unit-test-shared-key-'+'a'*32}):
            with patch.object(workspace,'RUNTIME',Path(first)):
                _,rows=workspace.source('cross-instance-owner')
                credential=mcp_access.issue('cross-instance-owner','summarize_overdue_invoices',rows)
            with patch.object(workspace,'RUNTIME',Path(second)):
                with self.assertRaises(Exception):mcp_access.invoke('summarize_overdue_invoices',credential)
                with patch.dict('os.environ',{'FINANCEGUARD_MCP_SIGNING_KEY':'unit-test-different-key-'+'b'*32}):
                    with self.assertRaises(Exception):mcp_access.invoke('summarize_overdue_invoices',credential)
    def test_short_configured_signer_is_rejected(self):
        with patch.dict('os.environ',{'FINANCEGUARD_MCP_SIGNING_KEY':'too-short'}):
            with self.assertRaises(RuntimeError):mcp_access.issue('owner','list_invoices',[])
