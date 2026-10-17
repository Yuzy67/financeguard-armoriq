"""Real SDK sessions and delivery receipts, separate from application audit IDs."""
import os
import logging
import time
from uuid import uuid4
from integration_errors import ConfigurationError, IntegrationError
from runtime_config import require_armoriq_configuration, SDK_ENDPOINTS
from mcp_registry import resolve_existing_mcp

# Upstream SDK messages can embed arbitrary HTTP response bodies. Emit only our
# sanitized errors and explicit ingestion receipts, never upstream log content.
class _SanitizedSDKLog(logging.Filter):
    def filter(self, record):
        record.msg = 'ArmorIQ SDK diagnostic details withheld; inspect FinanceGuard sanitized action status.'
        record.args = ()
        record.exc_info = None
        record.exc_text = None
        record.stack_info = None
        return True

for _name in ('armoriq_sdk.client', 'armoriq_sdk.session', 'armoriq_sdk.observability.shipper', 'armoriq_sdk.observability.recorder'):
    logging.getLogger(_name).addFilter(_SanitizedSDKLog())

TARGET_ORG = '68c3541d-e2d8-462a-8393-243925a5ed23'


class ActionDenied(RuntimeError):
    pass


class ArmorIQWorkflow:
    def __init__(self, tool, credential=None):
        from armoriq_sdk import ArmorIQClient, SessionOptions
        from armoriq_sdk.observability import ObservabilityConfig
        require_armoriq_configuration()
        self.tool = tool
        self.trace_ids = []
        self.receipts = []
        self.last_flush_start = 0
        self.enforce_status = None
        self.enforce_response_valid = False
        self.enforce_json_response = False
        self.policy_receipt = None
        self.agent_registry_verified = False
        self.mcp_server_id = None
        self.session = None
        credentials = {'finance-mcp': {'authType': 'bearer', 'token': credential}} if credential else None
        self.client = ArmorIQClient(
            api_key=os.environ['ARMORIQ_API_KEY'],
            user_id='financeguard-operator',
            agent_id=os.environ['ARMORIQ_AGENT_ID'],
            mcp_credentials=credentials, timeout=25, max_retries=0,
            verify_ssl=True, **SDK_ENDPOINTS,
        )
        try:
            bootstrap = self.client.bootstrap()
            org = bootstrap.get('org') or {}
            self.org_id = org.get('orgId') or org.get('id')
            expected = os.environ['ARMORIQ_EXPECTED_ORG_ID']
            if self.org_id != expected:
                raise ConfigurationError('ArmorIQ organization mismatch. The API key must belong to ARMORIQ_EXPECTED_ORG_ID.', 'organization_mismatch')
            # Compare only explicit SDK identity fields. Display names alone
            # cannot establish which existing agent a policy targets.
            agent = bootstrap.get('agent') or {}
            resolved = agent.get('agentId') or agent.get('agent_id') if isinstance(agent,dict) else None
            if resolved and resolved != self.client.agent_id:
                raise ConfigurationError('The API key bootstrap agent differs from ARMORIQ_AGENT_ID. Resolve the existing registry identity before approving a plan.', 'agent_identity_mismatch')
            self.agent_registry_verified = bool(resolved and resolved == self.client.agent_id)
            endpoint = os.environ.get('MCP_SERVER_URL')
            registered = resolve_existing_mcp(self.client.list_mcps(), os.environ['ARMORIQ_MCP_SERVER_ID'])
            if not registered:
                raise ConfigurationError('The existing ARMORIQ_MCP_SERVER_ID is not exposed in this key organization registry. Verify the record ID and account access; do not create a duplicate.', 'mcp_not_registered')
            self.mcp_server_id = registered['id']
            if registered.get('name') != 'finance-mcp':
                raise ConfigurationError('The existing MCP record has a different SDK routing name than finance-mcp. Inspect the record and policy before changing routing.', 'mcp_routing_name_mismatch')
            if endpoint and registered.get('url', '').rstrip('/') != endpoint.rstrip('/'):
                raise ConfigurationError('MCP_SERVER_URL differs from the finance-mcp URL registered in ArmorIQ. Update the registration before running.', 'mcp_registration_mismatch')
            self.client.http_client.event_hooks.setdefault('response', []).append(self._delivery_receipt)
            enabled = os.environ.get('ARMORIQ_OBSERVABILITY', 'true').lower() not in {'0', 'false', 'no', 'off'}
            self.session = self.client.start_session(SessionOptions(
                mode='sdk', default_mcp_name='finance-mcp', validity_seconds=300,
                llm='financeguard-command-workflow', session_id=str(uuid4()),
                observability=ObservabilityConfig(enabled=enabled, flush_interval_ms=60000),
            ))
            self.token = self.session.start_plan([{'name': tool, 'args': {}}], goal='Review invoices without money movement.')
            self._remember_trace()
        except Exception:
            self.close()
            raise

    def _delivery_receipt(self, response):
        # Do not persist request headers, tokens, bodies, or arbitrary provider text.
        if response.request.url.path.endswith('/iap/sdk/enforce'):
            self.enforce_status = response.status_code
            try:
                response.read()
                body = response.json()
                self.enforce_json_response = isinstance(body, dict)
                self.enforce_response_valid = isinstance(body, dict) and isinstance(body.get('allowed'), bool)
                self.policy_receipt = {'http_status':response.status_code,'response_valid':self.enforce_response_valid,
                    'allowed':body.get('allowed') if self.enforce_response_valid else None,
                    'source':'ARMORIQ_ENFORCEMENT_API','dashboard_decision_confirmed':False}
                matched = body.get('matchedPolicy') if isinstance(body,dict) else None
                if isinstance(matched,dict):
                    identifier = matched.get('id') or matched.get('policyId')
                    if isinstance(identifier,str):
                        try:self.policy_receipt['matched_policy_id'] = str(__import__('uuid').UUID(identifier))
                        except ValueError:pass
            except Exception:
                self.enforce_response_valid = False
        if not response.request.url.path.endswith('/observability/spans'):
            return
        try:
            response.read()
            body = response.json() if 200 <= response.status_code < 300 else {}
            self.receipts.append({
                'http_status': response.status_code,
                'accepted': int(body.get('accepted', 0) or 0),
                'rejected': int(body.get('rejected', 0) or 0),
            })
        except Exception:
            self.receipts.append({'http_status': response.status_code, 'accepted': 0, 'rejected': 0})

    def _remember_trace(self):
        ctx = self.session.active_plan_trace_context if self.session else None
        if ctx and ctx.trace_id not in self.trace_ids:
            self.trace_ids.append(ctx.trace_id)

    def invoke(self, tool, params, user_email):
        from armoriq_sdk import ReportOptions
        self._remember_trace()
        self.enforce_status = None
        self.enforce_response_valid = False
        self.enforce_json_response = False
        self.policy_receipt = None
        decision = self.session.check(tool, params, user_email=user_email)
        if tool == self.tool:
            if self.enforce_status in {401, 403}:
                if not self.enforce_json_response:
                    raise IntegrationError('The enforcement endpoint returned a non-JSON access rejection before a valid policy response. No tool executed; credential validity is unconfirmed.', 'service_access_denied', 'network', provider_status=self.enforce_status)
                raise IntegrationError('ArmorIQ policy service rejected the backend credential or account access. No tool executed.', 'authentication_failed', 'authentication', provider_status=self.enforce_status)
            if self.enforce_status is None:
                raise IntegrationError('ArmorIQ policy service did not return a confirmed response. No tool executed.', 'policy_unreachable', 'network')
            if not 200 <= self.enforce_status < 300:
                raise IntegrationError('ArmorIQ policy service returned an HTTP error. No tool executed.', 'policy_service_error', 'provider', provider_status=self.enforce_status)
            if not self.enforce_response_valid or str(getattr(decision, 'reason', '') or '').startswith('enforce-unavailable:'):
                raise IntegrationError('ArmorIQ policy response was invalid or incomplete. No tool executed.', 'policy_response_invalid', 'provider')
        if not decision.allowed:
            if getattr(decision, 'action', None) == 'hold':
                if self.policy_receipt is not None:
                    self.policy_receipt['enforcement_action'] = 'hold'
                    identifier = getattr(decision, 'delegation_id', None)
                    if identifier:
                        try:self.policy_receipt['delegation_id'] = str(__import__('uuid').UUID(identifier))
                        except (ValueError, TypeError):pass
                raise IntegrationError('ArmorIQ held this action for reviewer approval. No tool executed. Review it in ArmorIQ Held Actions, then retry the same task before its plan expires.', 'policy_hold', 'policy', http_status=200)
            if tool != self.tool:
                self.policy_receipt = {'source':'ARMORIQ_SDK_INTENT_BINDING','allowed':False,'http_status':None,'dashboard_decision_confirmed':False}
                # Preserve the original SDK intent-binding rejection. invoke()
                # rejects this action before any proxy request is transmitted.
                self.client.invoke('finance-mcp', tool, self.token, params, user_email=user_email)
                raise ActionDenied('SDK unexpectedly returned for an out-of-plan action; FinanceGuard refused the result.')
            raise ActionDenied('ArmorIQ session denied the action. No MCP tool executed.')
        if tool != self.tool:
            raise ActionDenied('Action is outside the approved FinanceGuard scope.')
        started = time.perf_counter()
        try:
            result = self.client.invoke('finance-mcp', tool, self.token, params, user_email=user_email)
            if result.status != 'success' or isinstance(result.result, dict) and result.result.get('isError'):
                raise IntegrationError('The MCP tool returned a failure. No successful result is claimed.', 'tool_failed', 'tool')
        except Exception:
            self.session.report(tool, {}, {'execution': 'failed'}, ReportOptions(status='error', error_message='MCP execution failed; details withheld.', duration_ms=(time.perf_counter()-started)*1000))
            raise
        # Report an actual execution, without uploading invoice contents.
        self.session.report(tool, {}, {'execution': 'completed', 'sdk_verified': result.verified is True}, ReportOptions(duration_ms=(time.perf_counter()-started)*1000))
        return result

    def flush(self):
        self.last_flush_start = len(self.receipts)
        if self.session:
            self.session.flush_observability()
        return self.snapshot()

    def snapshot(self):
        receipts = self.receipts[self.last_flush_start:]
        accepted = sum(r['accepted'] for r in receipts)
        rejected = sum(r['rejected'] for r in receipts)
        failed = rejected or any(r['http_status'] >= 400 for r in receipts)
        status = 'accepted' if accepted and not failed else 'partial' if accepted else 'rejected' if failed else 'unconfirmed'
        if not self.session or self.session.observability_recorder is None:
            status = 'disabled'
        return {'session_id': self.session.session_id if self.session else None,
                'trace_ids': list(self.trace_ids), 'organization_id': getattr(self, 'org_id', None),
                'agent_id':self.client.agent_id,'agent_registry_verified':self.agent_registry_verified,
                'mcp_server_id':self.mcp_server_id,'runtime_policy':self.policy_receipt,
                'delivery': status, 'accepted': accepted, 'rejected': rejected,
                'console_verified': False}

    def close(self):
        try:
            if self.session:
                self.session.close()
        finally:
            self.client.close()
