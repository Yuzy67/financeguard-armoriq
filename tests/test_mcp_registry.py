"""The real SDK registry DTO uses mcpId, not id. No name-only authorization."""
import unittest
from mcp_registry import resolve_existing_mcp
from integration_errors import ConfigurationError

class RegistryTests(unittest.TestCase):
    identifier='2da563ef-544e-4db7-a418-0c404cf75180'
    def test_actual_api_dto_resolves_exact_existing_record(self):
        rows=[{'mcpId':self.identifier,'name':'finance-mcp','url':'https://example.com/mcp'}]
        self.assertIsNone(next((r for r in rows if r.get('id')==self.identifier),None))
        result=resolve_existing_mcp(rows,self.identifier)
        self.assertEqual(result['id'],self.identifier)
        self.assertEqual(result['mcpId'],self.identifier)
        self.assertNotIn('id',rows[0])
    def test_legacy_id_still_resolves(self):
        self.assertEqual(resolve_existing_mcp([{'id':self.identifier}],self.identifier)['id'],self.identifier)
    def test_uuid_case_does_not_change_resource_identity(self):
        self.assertEqual(resolve_existing_mcp([{'mcpId':self.identifier}],self.identifier.upper())['id'],self.identifier)
    def test_same_name_is_not_authorization_for_another_id(self):
        rows=[{'mcpId':'11111111-1111-4111-8111-111111111111','name':'finance-mcp'}]
        self.assertIsNone(resolve_existing_mcp(rows,self.identifier))
    def test_slug_or_name_cannot_replace_record_uuid(self):
        self.assertIsNone(resolve_existing_mcp([{'id':'finance-mcp','name':'finance-mcp'}],self.identifier))
    def test_conflicting_resource_ids_fail_closed(self):
        with self.assertRaises(ConfigurationError):
            resolve_existing_mcp([{'mcpId':self.identifier,'id':'11111111-1111-4111-8111-111111111111'}],self.identifier)
    def test_duplicate_exact_records_fail_closed(self):
        with self.assertRaises(ConfigurationError):
            resolve_existing_mcp([{'mcpId':self.identifier}]*2,self.identifier)
    def test_invalid_registry_shapes_are_not_treated_as_missing_records(self):
        for rows in [None,{},['private-provider-response']]:
            with self.assertRaises(ConfigurationError) as error:
                resolve_existing_mcp(rows,self.identifier)
            self.assertEqual(error.exception.code,'mcp_registry_response_invalid')
            self.assertNotIn('private-provider-response',str(error.exception))
    def test_unknown_uuid_is_not_replaced_with_first_record(self):
        self.assertIsNone(resolve_existing_mcp([],self.identifier))
