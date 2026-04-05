"use client";

import Link from "next/link";
import { useMutation, useQuery } from "@tanstack/react-query";
import { useRouter } from "next/navigation";

import { deleteInvoice, fetchInvoice, getInvoicePdfUrl, sendReminder, updateInvoiceStatus } from "@/lib/api";
import { InvoiceStatus } from "@/lib/types";
import { StatusBadge } from "@/components/invoices/status-badge";

export function InvoiceDetail({ invoiceId }: { invoiceId: string }) {
  const router = useRouter();
  const invoiceQuery = useQuery({
    queryKey: ["invoice", invoiceId],
    queryFn: () => fetchInvoice(invoiceId),
  });

  const statusMutation = useMutation({
    mutationFn: (status: string) => updateInvoiceStatus(invoiceId, status),
    onSuccess: () => invoiceQuery.refetch(),
  });

  const reminderMutation = useMutation({
    mutationFn: () => sendReminder(invoiceId),
  });

  const deleteMutation = useMutation({
    mutationFn: () => deleteInvoice(invoiceId),
    onSuccess: () => router.push("/"),
  });

  if (invoiceQuery.isLoading) {
    return <div className="card state-card">Loading invoice...</div>;
  }

  if (invoiceQuery.isError || !invoiceQuery.data) {
    return <div className="card state-card error">Unable to load invoice.</div>;
  }

  const invoice = invoiceQuery.data;

  return (
    <div className="detail-stack">
      <section className="card detail-hero">
        <div className="detail-hero-copy">
          <p className="eyebrow">Invoice</p>
          <h2 className="section-title">{invoice.invoice_number}</h2>
          <p className="subtle-copy">
            Issued to {invoice.client.name} and currently tracked in {invoice.currency}.
          </p>
          <StatusBadge status={invoice.status} />
        </div>
        <div className="detail-actions">
          <Link className="button button-ghost" href={`/invoices/${invoice.id}/edit`}>
            Edit
          </Link>
          <a className="button button-secondary" href={getInvoicePdfUrl(invoiceId)} rel="noreferrer" target="_blank">
            Download PDF
          </a>
          <button className="button button-secondary" onClick={() => reminderMutation.mutate()} type="button">
            {reminderMutation.isPending ? "Queueing..." : "Send reminder"}
          </button>
          <button className="button button-danger" onClick={() => deleteMutation.mutate()} type="button">
            Delete
          </button>
        </div>
      </section>

      <section className="card detail-grid">
        <div className="detail-card">
          <h3>Client</h3>
          <p>{invoice.client.name}</p>
          <p>{invoice.client.email}</p>
          <p>{invoice.client.address}</p>
        </div>
        <div className="detail-card">
          <h3>Dates</h3>
          <p>Issue: {invoice.issue_date}</p>
          <p>Due: {invoice.due_date}</p>
          <p>Currency: {invoice.currency}</p>
        </div>
        <div className="detail-card">
          <h3>Status</h3>
          <select
            className="input"
            defaultValue={invoice.status}
            onChange={(event) => statusMutation.mutate(event.target.value as InvoiceStatus)}
          >
            {["draft", "sent", "paid", "overdue", "cancelled"].map((status) => (
              <option key={status} value={status}>
                {status}
              </option>
            ))}
          </select>
        </div>
      </section>

      <section className="card panel">
        <h3>Line items</h3>
        <div className="table-wrap">
          <table className="invoice-table">
            <thead>
              <tr>
                <th>Description</th>
                <th>Quantity</th>
                <th>Unit price</th>
                <th>Total</th>
              </tr>
            </thead>
            <tbody>
              {invoice.line_items.map((item) => (
                <tr key={item.id}>
                  <td>{item.description}</td>
                  <td>{item.quantity}</td>
                  <td>{invoice.currency} {item.unit_price}</td>
                  <td>{invoice.currency} {item.line_total}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section className="card totals-grid">
        <div>
          <span>Subtotal</span>
          <strong>{invoice.currency} {invoice.subtotal}</strong>
        </div>
        <div>
          <span>Tax</span>
          <strong>{invoice.currency} {invoice.tax_amount}</strong>
        </div>
        <div>
          <span>Total</span>
          <strong>{invoice.currency} {invoice.total_amount}</strong>
        </div>
      </section>

      <section className="card panel">
        <h3>Notes</h3>
        <p>{invoice.notes || "No notes provided."}</p>
      </section>
    </div>
  );
}
