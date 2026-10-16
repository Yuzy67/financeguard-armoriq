"""Persistent, owner-scoped demo data. No cloud credentials stored here."""
import csv
import io
import json
import os
import sqlite3
import tempfile
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from uuid import uuid4

ROOT=Path(__file__).parent
# Deployed source is read-only; Vercel only provides temporary scratch space.
TEMPORARY_STORAGE=os.environ.get('VERCEL')=='1'
DEFAULT_RUNTIME=Path(tempfile.gettempdir())/'financeguard' if TEMPORARY_STORAGE else ROOT/'runtime'
RUNTIME=Path(os.environ.get('FINANCEGUARD_RUNTIME',str(DEFAULT_RUNTIME)))
RUNTIME.mkdir(parents=True,exist_ok=True)

def db():
    connection=sqlite3.connect(RUNTIME/'workspace.sqlite3',timeout=15)
    connection.execute('CREATE TABLE IF NOT EXISTS invoices(owner TEXT PRIMARY KEY, source TEXT NOT NULL, payload TEXT NOT NULL)')
    connection.execute('CREATE TABLE IF NOT EXISTS events(id TEXT PRIMARY KEY,owner TEXT NOT NULL,timestamp TEXT NOT NULL,payload TEXT NOT NULL)')
    return connection

def source(owner):
    with db() as conn:row=conn.execute('SELECT source,payload FROM invoices WHERE owner=?',(owner,)).fetchone()
    if row:return row[0],json.loads(row[1])
    return 'sample',json.loads((ROOT/'data/invoices.json').read_text())

def save(owner,kind,rows):
    with db() as conn:conn.execute('INSERT OR REPLACE INTO invoices VALUES (?,?,?)',(owner,kind,json.dumps(rows)))

def reset(owner):
    with db() as conn:conn.execute('DELETE FROM invoices WHERE owner=?',(owner,))

def event(owner,action,status,reason,verified=False,engine='LOCAL_POLICY',observability=None):
    data={'id':str(uuid4()),'timestamp':datetime.now(timezone.utc).isoformat(),'action':action,'status':status,'reason':reason,'verified':verified,'engine':engine}
    if observability:data['observability']=observability
    with db() as conn:conn.execute('INSERT INTO events VALUES (?,?,?,?)',(data['id'],owner,data['timestamp'],json.dumps(data)))
    return data

def history(owner):
    with db() as conn:return [json.loads(r[0]) for r in conn.execute('SELECT payload FROM events WHERE owner=? ORDER BY timestamp DESC LIMIT 100',(owner,))]

def normalize(raw,number):
    try:
        row={key:str(raw.get(key) or '').strip() for key in ['invoice_id','customer_name','amount_inr','due_date','status']}
        if not row['invoice_id'] or len(row['invoice_id'])>80:raise ValueError('Invoice ID is required (max 80 characters).')
        if not row['customer_name'] or len(row['customer_name'])>200:raise ValueError('Customer is required (max 200 characters).')
        amount=Decimal(row['amount_inr'])
        if not amount.is_finite() or amount<=0 or amount>100000000 or amount*100!=(amount*100).to_integral_value():raise ValueError('Use a positive INR amount with at most two decimal places.')
        due=date.fromisoformat(row['due_date'])
        status=row['status'].lower()
        if status not in {'unpaid','overdue','pending','paid','draft','void','uncollectible'}:raise ValueError('Invalid invoice status.')
        days=max(0,(date.today()-due).days) if status in {'unpaid','overdue','pending'} else 0
        row.update(amount_inr=float(amount),days_overdue=days,status=('overdue' if days else 'pending') if status in {'unpaid','pending','overdue'} else status)
        return row
    except (ValueError,InvalidOperation) as exc:raise ValueError(f'Row {number}: {exc}') from None

def preview(text):
    reader=csv.DictReader(io.StringIO(text.lstrip('\ufeff')))
    required={'invoice_id','customer_name','amount_inr','due_date','status'}
    if not reader.fieldnames or not required.issubset(reader.fieldnames):raise ValueError('Required columns: '+', '.join(sorted(required)))
    rows=[];seen=set()
    for number,raw in enumerate(reader,2):
        if len(rows)>=500:raise ValueError('Maximum 500 invoices per import.')
        row=normalize(raw,number)
        if row['invoice_id'] in seen:raise ValueError(f'Row {number}: duplicate invoice ID.')
        seen.add(row['invoice_id']);rows.append(row)
    if not rows:raise ValueError('No invoice rows found.')
    return rows

def summary(rows):
    overdue=[r for r in rows if r['status']=='overdue']
    return {'overdue_invoice_count':len(overdue),'total_overdue_amount_inr':round(sum(r['amount_inr'] for r in overdue),2),'invoices':overdue}

def local_tool(tool,rows):
    if tool=='list_invoices':return {'invoices':rows}
    if tool=='summarize_overdue_invoices':return summary(rows)
    if tool=='create_draft_payment_reminders':
        drafts=[{'invoice_id':r['invoice_id'],'customer_name':r['customer_name'],'subject':'Payment reminder: '+r['invoice_id'],'body':f"Hello {r['customer_name']}, please review invoice {r['invoice_id']} for INR {r['amount_inr']:,.2f}, due {r['due_date']}.",'status':'draft'} for r in rows if r['status']=='overdue']
        return {'draft_count':len(drafts),'drafts':drafts,'emails_sent':0}
    if tool=='export_sandbox_reports':return {'report':summary(rows),'invoices':rows}
    raise ValueError('Tool not available.')
