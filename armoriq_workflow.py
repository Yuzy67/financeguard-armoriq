"""Real SDK sessions and delivery receipts, separate from application audit IDs."""
import os
import time
from uuid import uuid4

TARGET_ORG = '68c3541d-e2d8-462a-8393-243925a5ed23'


class ConfigurationError(RuntimeError):
    pass


class ActionDenied(RuntimeError):
    pass


class ArmorIQWorkflow:
    def __init__(self, tool, credential=None):
        from armoriq_sdk import ArmorIQClient, SessionOptions
        from armoriq_sdk.observability import ObservabilityConfig
        self.tool = tool
        self.trace_ids = []
        self.receipts = []
        self.last_flush_start = 0
        self.enforce_status = None
        self.session = None
        credentials = {'finance-mcp': {'authType': 'bearer', 'token': credential}} if credential else None
        self.client = ArmorIQClient(
            api_key=os.environ['ARMORIQ_API_KEY'],
            user_id='financeguard-operator',
            agent_id=os.environ.get('ARMORIQ_AGENT_ID', 'financeguard-demo'),
            mcp_credentials=credentials, timeout=25, max_retries=0,
        )
        try:
            bootstrap = self.client.bootstrap()
            org = bootstrap.get('org') or {}
            self.org_id = org.get('orgId') or org.get('id')
            expected = os.environ.get('ARMORIQ_EXPECTED_ORG_ID', TARGET_ORG)
            if self.org_id != expected:
                raise ConfigurationError(f'ArmorIQ organization mismatch: key belongs to {self.org_id}; expected {expected}. Update the backend key, not the frontend.')
            endpoint = os.environ.get('MCP_SERVER_URL')
            registered = next((m for m in self.client.list_mcps() if m.get('name') == 'finance-mcp'), None)
            if not registered:
                raise ConfigurationError('finance-mcp is not registered in the API key organization.')
            if endpoint and registered.get('url', '').rstrip('/') != endpoint.rstrip('/'):
                raise ConfigurationError('MCP_SERVER_URL differs from the finance-mcp URL registered in ArmorIQ. Update the registration before running.')
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
        decision = self.session.check(tool, params, user_email=user_email)
        if tool == self.tool and (self.enforce_status is None or not 200 <= self.enforce_status < 300):
            raise RuntimeError('ArmorIQ policy service did not confirm a decision; no tool executed.')
        if not decision.allowed:
            if tool != self.tool:
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
                raise RuntimeError('MCP invocation failed.')
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
                'delivery': status, 'accepted': accepted, 'rejected': rejected,
                'console_verified': False}

    def close(self):
        if self.session:
            self.session.close()
        self.client.close()
