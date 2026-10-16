"""Run a real plan/check/invoke/report/flush demonstration, never mocked success."""
import json,os
from pathlib import Path
from dotenv import load_dotenv
ROOT=Path(__file__).parent
load_dotenv(ROOT/'.env')

def main():
    from armoriq_sdk.exceptions import IntentMismatchException
    from armoriq_workflow import ArmorIQWorkflow,ConfigurationError
    import mcp_access,workspace
    if not os.environ.get('ARMORIQ_API_KEY'):
        print('SETUP REQUIRED: set ARMORIQ_API_KEY privately in the backend environment.')
        return 1
    workflow=None;evidence={}
    try:
        owner='financeguard-cli-synthetic';_,rows=workspace.source(owner)
        credential=mcp_access.issue(owner,'summarize_overdue_invoices',rows) if os.environ.get('FINANCEGUARD_SCOPED_MCP')=='1' else None
        print('--- FinanceGuard: creating approved plan ---')
        workflow=ArmorIQWorkflow('summarize_overdue_invoices',credential)
        print('--- Safe request: summarize overdue invoices ---')
        safe=workflow.invoke('summarize_overdue_invoices',{},os.environ.get('FINANCEGUARD_USER_EMAIL','demo@example.com'))
        evidence['safe']={'status':safe.status,'verified':safe.verified is True}
        print('ALLOWED: summarize_overdue_invoices; SDK verified='+str(safe.verified is True))
        print('--- Risky request: simulate refunds ---')
        try:workflow.invoke('simulate_refunds',{'invoice_id':rows[0]['invoice_id'] if rows else 'demo-invoice'},os.environ.get('FINANCEGUARD_USER_EMAIL','demo@example.com'))
        except IntentMismatchException:
            evidence['refund']={'status':'BLOCKED','exception':'IntentMismatchException','source':'ARMORIQ_SDK'}
            print('BLOCKED AS EXPECTED: IntentMismatchException (SDK intent binding, before proxy invocation)')
        else:raise RuntimeError('Expected SDK intent mismatch was not raised.')
        return 0
    except ConfigurationError as exc:
        print('SETUP REQUIRED:',str(exc));return 1
    except Exception as exc:
        print('DEMO FAILED:',type(exc).__name__,'(no verified success claimed; inspect server configuration)');return 1
    finally:
        if workflow:
            evidence['observability']=workflow.flush()
            print('OBSERVABILITY:',json.dumps(evidence['observability']))
            print('Accepted ingestion is not independent confirmation of dashboard visibility.')
            (workspace.RUNTIME/'last-demo-evidence.json').write_text(json.dumps(evidence,indent=2))
            workflow.close()

if __name__=='__main__':raise SystemExit(main())
