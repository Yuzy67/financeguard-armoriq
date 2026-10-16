import unittest
import workspace


class InvoiceImportTests(unittest.TestCase):
    def test_accounting_export_headers_and_currency(self):
        rows = workspace.preview('Invoice Number,Customer,Amount,Due Date,Status,Currency\nINV-22,Example Ltd,1250.50,2020-01-01,unpaid,INR\n')
        self.assertEqual(rows[0]['invoice_id'], 'INV-22')
        self.assertEqual(rows[0]['amount_inr'], 1250.50)
        self.assertEqual(rows[0]['status'], 'overdue')

    def test_foreign_currency_is_not_silently_converted(self):
        with self.assertRaisesRegex(ValueError, 'only INR'):
            workspace.preview('Invoice Number,Customer,Amount,Due Date,Status,Currency\nA,Name,10,2020-01-01,paid,USD\n')

    def test_ambiguous_export_columns_rejected(self):
        with self.assertRaisesRegex(ValueError, 'Ambiguous'):
            workspace.preview('invoice_id,Invoice Number,customer_name,amount_inr,due_date,status\nA,B,Name,10,2020-01-01,paid\n')
