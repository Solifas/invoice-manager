"use client";

import Link from "next/link";
import { useMutation, useQuery } from "@tanstack/react-query";

import { deleteRecurringInvoice, fetchRecurringInvoices, getErrorMessage } from "@/lib/api";

function formatRecurringStatus(status: string) {
  return status.charAt(0).toUpperCase() + status.slice(1);
}

export function RecurringInvoiceList() {
  const recurringQuery = useQuery({
    queryKey: ["recurring-invoices"],
    queryFn: fetchRecurringInvoices,
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => deleteRecurringInvoice(id),
    onSuccess: () => recurringQuery.refetch(),
  });

  if (recurringQuery.isLoading) {
    return <div className="card state-card">Loading recurring invoices...</div>;
  }

  if (recurringQuery.isError || !recurringQuery.data) {
    return <div className="card state-card error">Unable to load recurring invoices.</div>;
  }

  const recurringInvoices = recurringQuery.data.results;
  const activeCount = recurringInvoices.filter((item) => item.status === "active").length;
  const pausedCount = recurringInvoices.filter((item) => item.status === "paused").length;
  const upcomingRuns = recurringInvoices
    .map((item) => item.next_run_date)
    .filter((value): value is string => Boolean(value))
    .sort();
  const nextRun = upcomingRuns[0];

  return (
    <div className="dashboard-stack recurring-page">
      <section className="card recurring-header-card">
        <div className="recurring-header-copy">
          <p className="eyebrow">Recurring invoices</p>
          <h2 className="section-title">Recurring schedules that stay readable and reliable</h2>
          <p className="subtle-copy">
            Manage repeating invoice templates, review upcoming schedule dates, and stop templates without losing the billing history already generated.
          </p>
        </div>
        <div className="recurring-header-actions">
          <Link className="button" href="/recurring-invoices/new">
            New recurring invoice
          </Link>
        </div>
      </section>

      <section className="summary-grid recurring-summary-grid">
        <article className="card stat-card recurring-stat-card">
          <div className="stat-card-header">
            <span>Templates</span>
            <small>Total recurring schedules configured</small>
          </div>
          <strong>{recurringInvoices.length}</strong>
        </article>
        <article className="card stat-card recurring-stat-card">
          <div className="stat-card-header">
            <span>Active</span>
            <small>Schedules that can generate invoices automatically</small>
          </div>
          <strong>{activeCount}</strong>
        </article>
        <article className="card stat-card recurring-stat-card">
          <div className="stat-card-header">
            <span>Paused</span>
            <small>Templates kept for later without generating invoices</small>
          </div>
          <strong>{pausedCount}</strong>
        </article>
        <article className="card stat-card recurring-stat-card">
          <div className="stat-card-header">
            <span>Next scheduled run</span>
            <small>The nearest upcoming invoice date across all templates</small>
          </div>
          <strong>{nextRun || "Not scheduled"}</strong>
        </article>
      </section>

      <section className="card panel recurring-list-panel">
        <div className="panel-heading">
          <div>
            <p className="eyebrow">Schedule list</p>
            <h3 className="section-title">Recurring templates</h3>
          </div>
        </div>

        {recurringInvoices.length ? (
          <div className="recurring-card-list">
            {recurringInvoices.map((recurringInvoice) => (
              <article className="recurring-item-card" key={recurringInvoice.id}>
                <div className="recurring-item-main">
                  <Link className="invoice-link" href={`/recurring-invoices/${recurringInvoice.id}`}>
                    <span>{recurringInvoice.template_name}</span>
                    <small>{recurringInvoice.client?.name || `Client #${recurringInvoice.client_id}`}</small>
                  </Link>
                  <div className="recurring-item-meta">
                    <div>
                      <span className="field-label">Frequency</span>
                      <p>{formatRecurringStatus(recurringInvoice.frequency)}</p>
                    </div>
                    <div>
                      <span className="field-label">Next run</span>
                      <p>{recurringInvoice.next_run_date || "Not scheduled"}</p>
                    </div>
                    <div>
                      <span className="field-label">Status</span>
                      <span className={`schedule-status-badge schedule-status-${recurringInvoice.status}`}>
                        {formatRecurringStatus(recurringInvoice.status)}
                      </span>
                    </div>
                    <div>
                      <span className="field-label">Terms</span>
                      <p>{recurringInvoice.payment_terms_days} day terms</p>
                    </div>
                  </div>
                </div>
                <div className="recurring-item-actions">
                  <Link className="button button-ghost" href={`/recurring-invoices/${recurringInvoice.id}`}>
                    Open
                  </Link>
                  <button
                    className="button button-danger"
                    disabled={deleteMutation.isPending}
                    onClick={() => deleteMutation.mutate(String(recurringInvoice.id))}
                    type="button"
                  >
                    Stop schedule
                  </button>
                </div>
              </article>
            ))}
          </div>
        ) : (
          <div className="state-card">No recurring invoices configured yet.</div>
        )}
        {deleteMutation.isError ? <p className="form-error">{getErrorMessage(deleteMutation.error)}</p> : null}
      </section>
    </div>
  );
}
