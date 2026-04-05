import Link from "next/link";

import { Invoice } from "@/lib/types";
import { StatusBadge } from "@/components/invoices/status-badge";

export function InvoiceTable({
  invoices,
  isLoading,
  isError,
}: {
  invoices: Invoice[];
  isLoading: boolean;
  isError: boolean;
}) {
  if (isLoading) {
    return <div className="state-card">Loading invoices...</div>;
  }

  if (isError) {
    return <div className="state-card error">Unable to load invoices.</div>;
  }

  if (!invoices.length) {
    return <div className="state-card">No invoices matched your filters.</div>;
  }

  return (
    <div className="table-wrap">
      <table className="invoice-table">
        <thead>
          <tr>
            <th>Invoice</th>
            <th>Client</th>
            <th>Issue date</th>
            <th>Due date</th>
            <th>Status</th>
            <th>Total</th>
          </tr>
        </thead>
        <tbody>
          {invoices.map((invoice) => (
            <tr key={invoice.id}>
              <td>
                <Link className="invoice-link" href={`/invoices/${invoice.id}`}>
                  <span>{invoice.invoice_number}</span>
                  <small>{invoice.client.email}</small>
                </Link>
              </td>
              <td>{invoice.client.name}</td>
              <td>{invoice.issue_date}</td>
              <td>{invoice.due_date}</td>
              <td>
                <StatusBadge status={invoice.status} />
              </td>
              <td>
                <span className="table-total">
                  {invoice.currency} {invoice.total_amount}
                </span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
