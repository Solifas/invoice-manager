"use client";

import { useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { fetchPublicPayment } from "@/lib/api";
import { StatusBadge } from "@/components/invoices/status-badge";

export function PublicPaymentPage({ token }: { token: string }) {
  const [copiedField, setCopiedField] = useState<string | null>(null);
  const paymentQuery = useQuery({
    queryKey: ["public-payment", token],
    queryFn: () => fetchPublicPayment(token),
  });

  const copyValue = async (field: string, value: string) => {
    await navigator.clipboard.writeText(value);
    setCopiedField(field);
    window.setTimeout(() => setCopiedField(null), 1800);
  };

  if (paymentQuery.isLoading) {
    return <section className="card state-card">Loading payment page...</section>;
  }

  if (paymentQuery.isError || !paymentQuery.data) {
    return <section className="card state-card error">Payment page not found.</section>;
  }

  const payment = paymentQuery.data;
  const paidInFull = payment.status === "paid" || Number(payment.outstanding_amount) === 0;
  const cancelled = payment.status === "cancelled";

  const renderCopyRow = (field: string, label: string, value: string, copyValueText?: string) => {
    const isCopied = copiedField === field;

    return (
      <div className={`public-payment-detail-row ${isCopied ? "is-copied" : ""}`}>
        <span className="public-payment-detail-label">{label}</span>
        <span className={`public-payment-detail-text ${isCopied ? "is-copied" : ""}`}>{value}</span>
        <div className="public-payment-detail-actions">
          <button
            aria-label={`Copy ${label}`}
            className={`copy-action-button ${isCopied ? "is-copied" : ""}`}
            onClick={() => copyValue(field, copyValueText || value)}
            type="button"
          >
            {isCopied ? "Copied" : "Copy"}
          </button>
        </div>
      </div>
    );
  };

  return (
    <div className="public-payment-stack">
      <section className="card public-payment-hero">
        <div className="public-payment-hero-copy">
          <p className="eyebrow">Pay invoice</p>
          <h1>{payment.invoice_number}</h1>
          <div className="public-payment-meta">
            <span>{payment.client_name}</span>
            <span>Issued {payment.issue_date}</span>
            <span>Due {payment.due_date}</span>
          </div>
        </div>
        <StatusBadge status={payment.status} />
      </section>

      <section className="public-payment-summary">
        <article className="card stat-card public-payment-stat public-payment-stat-primary">
          <span>Outstanding</span>
          <strong>{payment.outstanding_amount}</strong>
        </article>
        <article className="card stat-card public-payment-stat">
          <span>Paid so far</span>
          <strong>{payment.amount_paid}</strong>
        </article>
        <article className="card stat-card public-payment-stat">
          <span>Total invoice</span>
          <strong>{payment.total}</strong>
        </article>
      </section>

      {cancelled ? (
        <section className="card panel public-payment-panel">
          <h2 className="section-title">This invoice has been cancelled</h2>
          <p className="subtle-copy">Payment instructions are no longer active for this invoice.</p>
        </section>
      ) : null}

      <section className="card panel public-payment-panel">
        <div className="panel-heading">
          <div className="public-payment-panel-copy">
            <p className="eyebrow">EFT details</p>
            <h2 className="section-title">{paidInFull ? "Payment received" : "Transfer by bank payment"}</h2>
            <p className="subtle-copy">
              {paidInFull
                ? "This invoice is already fully paid. Keep these details only for your records."
                : "Use the details below when making an EFT payment. Use the payment reference exactly as shown for easier reconciliation."}
            </p>
          </div>
        </div>

        <div className="public-payment-detail-list">
          {payment.eft_details.profile_name ? (
            <div className="public-payment-detail-row">
              <span className="public-payment-detail-label">Profile</span>
              <span className="public-payment-detail-text">{payment.eft_details.profile_name}</span>
            </div>
          ) : null}
          <div className="public-payment-detail-row">
            <span className="public-payment-detail-label">Bank</span>
            <span className="public-payment-detail-text">{payment.eft_details.bank_name}</span>
          </div>
          {renderCopyRow("holder", "Account name", payment.eft_details.account_holder_name)}
          {payment.eft_details.branch_code ? (
            <div className="public-payment-detail-row">
              <span className="public-payment-detail-label">Branch code</span>
              <span className="public-payment-detail-text">{payment.eft_details.branch_code}</span>
            </div>
          ) : null}
          {payment.eft_details.account_type ? (
            <div className="public-payment-detail-row">
              <span className="public-payment-detail-label">Account type</span>
              <span className="public-payment-detail-text">{payment.eft_details.account_type}</span>
            </div>
          ) : null}
          {renderCopyRow("account", "Account number", payment.eft_details.account_number)}
        </div>

        <div className="public-payment-reference-strip">
          <div className="public-payment-reference-copy">
            <p className="public-payment-reference-label">Use this EFT reference</p>
            <p className={`public-payment-reference-value ${copiedField === "reference" ? "is-copied" : ""}`}>
              {payment.payment_reference}
            </p>
          </div>
          <div className="public-payment-detail-actions">
            <button
              aria-label="Copy payment reference"
              className={`copy-action-button ${copiedField === "reference" ? "is-copied" : ""}`}
              onClick={() => copyValue("reference", payment.payment_reference)}
              type="button"
            >
              {copiedField === "reference" ? "Copied" : "Copy"}
            </button>
          </div>
        </div>
      </section>
    </div>
  );
}
