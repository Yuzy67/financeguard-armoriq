# Connect invoices without a payment gateway

FinanceGuard accepts invoice CSV exports, including exports from spreadsheets
and accounting software that contain the required fields. An API key, bank
account, or gateway account is not required. PDF/image extraction, OAuth account
connections and automatic Google Sheets synchronization are not implemented.

## User workflow

1. Sign in, then open Invoices -> Add invoices.
2. Download the template or export your existing invoice list as CSV.
3. Choose **Link an invoice file** in a supported desktop browser, or **Import a
   CSV** for a one-time snapshot.
4. Check the preview and confirm. This replaces only your workspace's invoices
   and clears existing approvals. All amounts are interpreted as INR.
5. Search by customer or invoice number, filter by status, sort, or open details.
6. Open Invoice assistant, choose a task and protection mode, approve, then run.
   Tool execution still uses the existing scoped MCP and policy workflow.
7. After changing your linked file, save it and click Refresh file. Review and
   confirm the new snapshot, then approve any subsequent assistant task again.

File permission is read-only. The source file is never modified. A handle is
kept only in memory for the current signed-in session; reconnect after reload
or account changes. Permission loss or a moved file requires reconnection.
After the initial confirmed import, opt-in Auto-sync checks the selected file
every ten seconds while this page is open and visible. Explicit consent allows
subsequent validated snapshots to replace the workspace automatically. Invalid
CSV or lost permission pauses sync and preserves the previous records. Disable
the toggle to stop it. It pauses during an assistant request or open dialog;
it does not run after closing the browser and does not send emails or move money.
Changed datasets invalidate approvals and old conversation context. This is a
user-enabled source importer, not an autonomous model tool or an ArmorIQ decision.
Imported data has the storage lifetime
shown in the app; Vercel's temporary storage is not durable shared storage.

## Supported CSV

Required fields: invoice ID, customer, amount in INR, due date, and status.
Dates must use YYYY-MM-DD. Amounts must be plain positive numbers with no more
than two decimal places. Currency conversion is not performed. If a Currency
column exists, every value must be INR. Without it, the preview explicitly
states that amounts are INR. Confirm the denomination before importing.

Common aliases include Invoice Number / Invoice No / invoice_id,
Customer / Client / customer_name, Amount / Total / amount_inr,
Due Date / Payment Due Date / due_date, and Status / Invoice Status.
Ambiguous mappings are rejected. Extra unrelated columns are ignored.
Use paid, unpaid, pending, overdue, draft, void, or uncollectible for status.
Unpaid, pending and overdue records are classified against the due date on
import. Dates and statuses in sample data remain a clearly labeled fixed demo.
Maximum 500 invoices and a file smaller than 650 KB through the interface.

## Verification on 16 October 2026

- 27 backend tests passed, including header mapping, currency refusal, owner
  isolation, changed-data approval invalidation and real MCP protocol tests.
- Actual Firebase browser sign-in passed using the existing synthetic account.
- Browser CSV upload using common headings imported two synthetic invoices.
  Approved local execution returned the actual imported overdue total INR
  1,234.50. Refund under that summary plan was blocked by local policy.
- Linked-file refresh used a real browser storage file handle with a controlled
  picker fixture: INR 100 remained visible until confirmation, then became INR
  275 and the prior approval was cleared. The native operating-system file
  picker and its permission dialog were not automated in this check.
- Browser sign-out restored a fresh sample workspace. Search, status filters,
  invoice details and the source dialog passed desktop/mobile checks; the final
  390-pixel mobile page had no document-level horizontal overflow (the invoice
  table scrolls within its own container).
- These checks do not prove ArmorIQ cloud verification; registration's HTTP
  500 remains separately documented in MCP-CONNECTION-STATUS.md.
- The invoice UI deployed successfully and GitHub CI passed. A public browser
  smoke check encountered "Start a demo or sign in" during approval: guest
  identity and approvals are held in process memory and can disappear across
  Vercel instances. Hosted action reliability is not confirmed; use the tested
  local origin until shared session/storage and hosting settings are resolved.

Official browser file-access reference:
https://developer.chrome.com/docs/capabilities/web-apis/file-system-access
