"use client";

import Link from "next/link";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import {
  deleteInvoice,
  fetchInvoice,
  getErrorMessage,
  getInvoicePdfUrl,
  recordInvoicePayment,
  regeneratePaymentPageToken,
  sendReminder,
  updateInvoiceStatus,
} from "@/lib/api";
import { InvoicePayment, InvoiceStatus, ReminderChannel } from "@/lib/types";
import { StatusBadge } from "@/components/invoices/status-badge";

const buildDefaultPaymentState = (): Omit<InvoicePayment, "id" | "created_at" | "updated_at"> => ({
  amount: "",
  payment_date: "",
  payment_method: "eft",
  reference: "",
  notes: "",
});

export function InvoiceDetail({ invoiceId }: { invoiceId: string }) {
  const router = useRouter();
  const queryClient = useQueryClient();
  const [paymentForm, setPaymentForm] = useState(buildDefaultPaymentState);
  const [copyState, setCopyState] = useState<"idle" | "copied">("idle");
  const [selectedStatus, setSelectedStatus] = useState<InvoiceStatus>("draft");
  const invoiceQuery = useQuery({
    queryKey: ["invoice", invoiceId],
    queryFn: () => fetchInvoice(invoiceId),
  });

  const statusMutation = useMutation({
    mutationFn: (status: string) => updateInvoiceStatus(invoiceId, status),
    onSuccess: (updatedInvoice) => {
      queryClient.setQueryData(["invoice", invoiceId], updatedInvoice);
      setSelectedStatus(updatedInvoice.status);
    },
  });

  const reminderMutation = useMutation({
    mutationFn: (channel: ReminderChannel) => sendReminder(invoiceId, channel),
  });

  const paymentMutation = useMutation({
    mutationFn: () => recordInvoicePayment(invoiceId, paymentForm),
    onSuccess: () => {
      setPaymentForm(buildDefaultPaymentState());
      invoiceQuery.refetch();
    },
  });

  const regenerateTokenMutation = useMutation({
    mutationFn: () => regeneratePaymentPageToken(invoiceId),
    onSuccess: (updatedInvoice) => {
      queryClient.setQueryData(["invoice", invoiceId], updatedInvoice);
    },
  });

  const deleteMutation = useMutation({
    mutationFn: () => deleteInvoice(invoiceId),
    onSuccess: () => router.push("/"),
  });

  useEffect(() => {
    if (invoiceQuery.data?.status) {
      setSelectedStatus(invoiceQuery.data.status);
    }
  }, [invoiceQuery.data?.status]);

  useEffect(() => {
    if (!paymentForm.payment_date) {
      setPaymentForm((current) => ({
        ...current,
        payment_date: new Date().toISOString().slice(0, 10),
      }));
    }
  }, [paymentForm.payment_date]);

  if (invoiceQuery.isLoading) {
    return <div className="card state-card">Loading invoice...</div>;
  }

  if (invoiceQuery.isError || !invoiceQuery.data) {
    return <div className="card state-card error">Unable to load invoice.</div>;
  }

  const invoice = invoiceQuery.data;
  const paymentLinkAvailable = invoice.payment_link_available && Boolean(invoice.public_payment_url);

  const copyPaymentLink = async () => {
    if (!paymentLinkAvailable) {
      return;
    }
    await navigator.clipboard.writeText(invoice.public_payment_url || "");
    setCopyState("copied");
    window.setTimeout(() => setCopyState("idle"), 2000);
  };

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
          <button className="button button-danger" onClick={() => deleteMutation.mutate()} type="button">
            Delete
          </button>
        </div>
      </section>

      <section className="card detail-grid">
        <div className="detail-card detail-card-status">
          <h3>Client</h3>
          <p>{invoice.client.name}</p>
          <p>{invoice.client.email}</p>
          <p>{invoice.client.phone_number || "No phone number saved"}</p>
          <p>{invoice.client.address}</p>
        </div>
        <div className="detail-card detail-card-reminders">
          <h3>Dates</h3>
          <p>Issue: {invoice.issue_date}</p>
          <p>Due: {invoice.due_date}</p>
          <p>Currency: {invoice.currency}</p>
        </div>
        <div className="detail-card detail-card-payment-page">
          <h3>Status</h3>
          <select
            className="input"
            onChange={(event) => setSelectedStatus(event.target.value as InvoiceStatus)}
            value={selectedStatus}
          >
            {["draft", "sent", "paid", "overdue", "cancelled"].map((status) => (
              <option key={status} value={status}>
                {status}
              </option>
            ))}
          </select>
          <div className="stack-actions">
            <button
              className="button button-secondary"
              disabled={statusMutation.isPending || selectedStatus === invoice.status}
              onClick={() => statusMutation.mutate(selectedStatus)}
              type="button"
            >
              {statusMutation.isPending ? "Saving..." : "Save status"}
            </button>
          </div>
          {selectedStatus !== invoice.status ? (
            <p className="subtle-copy">Status change is pending until you save it.</p>
          ) : (
            <p className="subtle-copy">Status is saved. Paid and overdue states can still update automatically from payments and due dates.</p>
          )}
          {statusMutation.isError ? <p className="form-error">{getErrorMessage(statusMutation.error)}</p> : null}
        </div>
      </section>

      <section className="card totals-grid">
        <div>
          <span>Subtotal</span>
          <strong>
            {invoice.currency} {invoice.subtotal}
          </strong>
        </div>
        <div>
          <span>Tax</span>
          <strong>
            {invoice.currency} {invoice.tax_amount}
          </strong>
        </div>
        <div>
          <span>Total</span>
          <strong>
            {invoice.currency} {invoice.total_amount}
          </strong>
        </div>
        <div>
          <span>Paid</span>
          <strong>
            {invoice.currency} {invoice.amount_paid}
          </strong>
        </div>
        <div>
          <span>Outstanding</span>
          <strong>
            {invoice.currency} {invoice.outstanding_amount}
          </strong>
        </div>
      </section>

      <section className="card detail-grid">
        <div className="detail-card">
          <h3>Reminders</h3>
          <div className="stack-actions action-pill-row">
            <button className="button button-secondary action-chip" onClick={() => reminderMutation.mutate("email")} type="button">
              {reminderMutation.isPending ? "Queueing..." : "Send email reminder"}
            </button>
            <button className="button button-secondary action-chip" onClick={() => reminderMutation.mutate("whatsapp")} type="button">
              {reminderMutation.isPending ? "Queueing..." : "Send WhatsApp reminder"}
            </button>
          </div>
          {reminderMutation.isError ? <p className="form-error">{getErrorMessage(reminderMutation.error)}</p> : null}
        </div>

        <div className="detail-card">
          <h3>Payment page</h3>
          <p>
            {paymentLinkAvailable
              ? "Public EFT page is active."
              : invoice.status === "paid"
                ? "Payment link is unavailable because this invoice has already been paid."
                : invoice.status === "cancelled"
                  ? "Payment link is unavailable because this invoice is cancelled."
                  : "Public EFT page is disabled."}
          </p>
          <div className="detail-copy-list">
            <p>Source: {invoice.eft_snapshot.mode ? invoice.eft_snapshot.mode.replace("_", " ") : "No EFT details attached"}</p>
            <p>Profile: {invoice.eft_snapshot.profile_name || "Not set"}</p>
            <p>Account holder: {invoice.eft_snapshot.account_holder_name || "Not set"}</p>
            <p>Bank: {invoice.eft_snapshot.bank_name || "Not set"}</p>
            <p>Reference: {invoice.eft_snapshot.payment_reference || invoice.invoice_number}</p>
          </div>
          <div className="stack-actions action-pill-row">
            <button className="button button-secondary action-chip" disabled={!paymentLinkAvailable} onClick={copyPaymentLink} type="button">
              {copyState === "copied" ? "Link copied" : "Copy link"}
            </button>
            <a
              aria-disabled={!paymentLinkAvailable}
              className={`button button-secondary action-chip ${!paymentLinkAvailable ? "button-disabled" : ""}`}
              href={paymentLinkAvailable ? invoice.public_payment_url : undefined}
              rel="noreferrer"
              target="_blank"
            >
              Open page
            </a>
            <button
              className="button button-ghost action-chip"
              disabled={!paymentLinkAvailable}
              onClick={() => regenerateTokenMutation.mutate()}
              type="button"
            >
              {regenerateTokenMutation.isPending ? "Refreshing..." : "Regenerate token"}
            </button>
          </div>
          <p className={`subtle-copy payment-link-copy ${paymentLinkAvailable ? "is-active" : ""}`}>
            {invoice.public_payment_url || "No payment link available for this invoice."}
          </p>
          {regenerateTokenMutation.isError ? <p className="form-error">{getErrorMessage(regenerateTokenMutation.error)}</p> : null}
        </div>
      </section>

      <section className="card panel">
        <div className="panel-heading">
          <div>
            <p className="eyebrow">Payments</p>
            <h3 className="section-title">Payment history</h3>
          </div>
        </div>
        {invoice.payments?.length ? (
          <div className="table-wrap">
            <table className="invoice-table">
              <thead>
                <tr>
                  <th>Date</th>
                  <th>Amount</th>
                  <th>Method</th>
                  <th>Reference</th>
                  <th>Notes</th>
                </tr>
              </thead>
              <tbody>
                {invoice.payments.map((payment) => (
                  <tr key={payment.id}>
                    <td>{payment.payment_date}</td>
                    <td>
                      {invoice.currency} {payment.amount}
                    </td>
                    <td>{payment.payment_method || "Not provided"}</td>
                    <td>{payment.reference || "Not provided"}</td>
                    <td>{payment.notes || "No notes"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="subtle-copy">No payments recorded yet.</p>
        )}
      </section>

      <section className="card form-section">
        <div className="section-heading">
          <div>
            <p className="eyebrow">Record payment</p>
            <h3 className="section-title">Add a partial or full payment</h3>
          </div>
        </div>
        <div className="field-grid">
          <label>
            <span className="field-label">Amount</span>
            <input
              className="input"
              min="0.01"
              onChange={(event) => setPaymentForm((current) => ({ ...current, amount: event.target.value }))}
              step="0.01"
              type="number"
              value={paymentForm.amount}
            />
          </label>
          <label>
            <span className="field-label">Payment date</span>
            <input
              className="input"
              onChange={(event) => setPaymentForm((current) => ({ ...current, payment_date: event.target.value }))}
              type="date"
              value={paymentForm.payment_date}
            />
          </label>
          <label>
            <span className="field-label">Method</span>
            <input
              className="input"
              onChange={(event) => setPaymentForm((current) => ({ ...current, payment_method: event.target.value }))}
              value={paymentForm.payment_method}
            />
          </label>
          <label>
            <span className="field-label">Reference</span>
            <input
              className="input"
              onChange={(event) => setPaymentForm((current) => ({ ...current, reference: event.target.value }))}
              value={paymentForm.reference}
            />
          </label>
          <label className="field-span">
            <span className="field-label">Notes</span>
            <textarea
              className="input textarea"
              onChange={(event) => setPaymentForm((current) => ({ ...current, notes: event.target.value }))}
              rows={3}
              value={paymentForm.notes}
            />
          </label>
        </div>
        <div className="form-actions">
          <button className="button button-large" onClick={() => paymentMutation.mutate()} type="button">
            {paymentMutation.isPending ? "Saving..." : "Record payment"}
          </button>
          {paymentMutation.isError ? <span className="form-error">{getErrorMessage(paymentMutation.error)}</span> : null}
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
              {invoice.line_items?.map((item) => (
                <tr key={item.id}>
                  <td>{item.description}</td>
                  <td>{item.quantity}</td>
                  <td>
                    {invoice.currency} {item.unit_price}
                  </td>
                  <td>
                    {invoice.currency} {item.line_total}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section className="card panel">
        <h3>Notes</h3>
        <p>{invoice.notes || "No notes provided."}</p>
      </section>
    </div>
  );
}
