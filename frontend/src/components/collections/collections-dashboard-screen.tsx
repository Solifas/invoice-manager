"use client";

import Link from "next/link";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { fetchCollectionsAnalytics, fetchDashboardSummary, getErrorMessage, sendReminder } from "@/lib/api";
import { CollectionsInvoiceSummary } from "@/lib/types";
import { StatusBadge } from "@/components/invoices/status-badge";

const metricCards = [
  {
    key: "total_amount_outstanding",
    label: "Total outstanding",
    note: "Open balance across active invoices",
  },
  {
    key: "total_overdue_amount",
    label: "Total overdue",
    note: "Outstanding amount past due",
  },
  {
    key: "overdue_invoices",
    label: "Overdue invoices",
    note: "Invoices requiring follow-up",
  },
  {
    key: "due_next_7_days_invoices",
    label: "Due next 7 days",
    note: "Active invoices approaching due date",
  },
  {
    key: "paid_invoices_this_month",
    label: "Paid this month",
    note: "Invoices with payment activity",
  },
  {
    key: "collected_amount_this_month",
    label: "Collected this month",
    note: "Recorded EFT and manual payments",
  },
] as const;

function formatMetricValue(summary: NonNullable<Awaited<ReturnType<typeof fetchDashboardSummary>>>, key: string) {
  if (
    key === "total_amount_outstanding" ||
    key === "total_overdue_amount" ||
    key === "collected_amount_this_month"
  ) {
    return `R ${summary[key as "total_amount_outstanding" | "total_overdue_amount" | "collected_amount_this_month"]}`;
  }

  return summary[key as "overdue_invoices" | "due_next_7_days_invoices" | "paid_invoices_this_month"].toString();
}

function OverdueInvoicesTable({
  invoices,
  onSendReminder,
  sendingInvoiceId,
}: {
  invoices: CollectionsInvoiceSummary[];
  onSendReminder: (invoiceId: number) => void;
  sendingInvoiceId: number | null;
}) {
  if (!invoices.length) {
    return <div className="state-card">No overdue invoices to follow up.</div>;
  }

  return (
    <div className="table-wrap">
      <table className="invoice-table collections-table">
        <thead>
          <tr>
            <th>Invoice</th>
            <th>Client</th>
            <th>Due date</th>
            <th>Outstanding</th>
            <th>Status</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          {invoices.map((invoice) => (
            <tr key={invoice.id}>
              <td>
                <Link className="invoice-link" href={`/invoices/${invoice.id}`}>
                  <span>{invoice.invoice_number}</span>
                </Link>
              </td>
              <td>{invoice.client_name}</td>
              <td>{invoice.due_date}</td>
              <td>
                <span className="table-total">R {invoice.outstanding_amount}</span>
              </td>
              <td>
                <StatusBadge status={invoice.status} />
              </td>
              <td>
                <div className="table-actions">
                  <Link className="button button-ghost button-nav" href={`/invoices/${invoice.id}`}>
                    Open
                  </Link>
                  <button
                    className="button button-nav"
                    disabled={sendingInvoiceId === invoice.id}
                    onClick={() => onSendReminder(invoice.id)}
                    type="button"
                  >
                    {sendingInvoiceId === invoice.id ? "Sending..." : "Send reminder"}
                  </button>
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

const ageingBucketRows = [
  { key: "one_to_seven_days", label: "1 to 7 days late", note: "Nudge these clients before the debt ages." },
  { key: "eight_to_fourteen_days", label: "8 to 14 days late", note: "Worth a direct follow-up this week." },
  { key: "fifteen_to_thirty_days", label: "15 to 30 days late", note: "These invoices are starting to put cash flow at risk." },
  { key: "thirty_one_plus_days", label: "31+ days late", note: "Highest priority for recovery action." },
] as const;

export function CollectionsDashboardScreen() {
  const queryClient = useQueryClient();
  const summaryQuery = useQuery({
    queryKey: ["dashboard-summary"],
    queryFn: fetchDashboardSummary,
  });
  const analyticsQuery = useQuery({
    queryKey: ["collections-analytics"],
    queryFn: fetchCollectionsAnalytics,
  });

  const reminderMutation = useMutation({
    mutationFn: (invoiceId: number) => sendReminder(invoiceId.toString(), "email"),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["dashboard-summary"] });
      queryClient.invalidateQueries({ queryKey: ["collections-analytics"] });
    },
  });

  return (
    <div className="dashboard-stack collections-dashboard">
      <section className="hero-panel dashboard-hero dashboard-hero-compact">
        <div>
          <p className="eyebrow">Collections</p>
          <h2 className="section-title">Collections dashboard</h2>
          <p className="subtle-copy">
            Track overdue accounts, upcoming due dates, and cash collected from your invoice payment history.
          </p>
        </div>
        <div className="dashboard-hero-actions">
          <Link className="button button-ghost button-nav" href="/">
            Billing overview
          </Link>
          <Link className="button button-primary-nav button-nav" href="/invoices/new">
            Create invoice
          </Link>
        </div>
      </section>

      {summaryQuery.isLoading ? (
        <section className="summary-grid collections-summary-grid">
          {Array.from({ length: 6 }).map((_, index) => (
            <div className="card skeleton" key={index} />
          ))}
        </section>
      ) : summaryQuery.isError || !summaryQuery.data ? (
        <div className="card state-card error">Unable to load collections data.</div>
      ) : (
        <>
          <section className="summary-grid collections-summary-grid">
            {metricCards.map((card) => (
              <article className="card stat-card" key={card.key}>
                <div className="stat-card-header">
                  <span>{card.label}</span>
                  <small>{card.note}</small>
                </div>
                <strong>{formatMetricValue(summaryQuery.data, card.key)}</strong>
              </article>
            ))}
          </section>

          <section className="card panel collections-oldest-panel">
            <div className="panel-heading">
              <div>
                <p className="eyebrow">Priority</p>
                <h3 className="section-title">Oldest overdue invoice</h3>
              </div>
              {summaryQuery.data.oldest_overdue_invoice ? (
                <Link
                  className="button button-ghost"
                  href={`/invoices/${summaryQuery.data.oldest_overdue_invoice.id}`}
                >
                  Open invoice
                </Link>
              ) : null}
            </div>
            {summaryQuery.data.oldest_overdue_invoice ? (
              <div className="oldest-overdue-grid">
                <div>
                  <span className="field-label">Invoice</span>
                  <p>{summaryQuery.data.oldest_overdue_invoice.invoice_number}</p>
                </div>
                <div>
                  <span className="field-label">Client</span>
                  <p>{summaryQuery.data.oldest_overdue_invoice.client_name}</p>
                </div>
                <div>
                  <span className="field-label">Due date</span>
                  <p>{summaryQuery.data.oldest_overdue_invoice.due_date}</p>
                </div>
                <div>
                  <span className="field-label">Outstanding</span>
                  <p>R {summaryQuery.data.oldest_overdue_invoice.outstanding_amount}</p>
                </div>
              </div>
            ) : (
              <div className="state-card">No overdue invoices right now.</div>
            )}
          </section>

          <section className="card panel dashboard-panel">
            <div className="panel-heading">
              <div>
                <p className="eyebrow">Insights</p>
                <h3 className="section-title">Collections intelligence</h3>
                <p className="subtle-copy">
                  A practical view of what came in, what is still out, and which accounts need attention first.
                </p>
              </div>
            </div>
            {analyticsQuery.isLoading ? (
              <div className="state-card">Loading collections insights...</div>
            ) : analyticsQuery.isError || !analyticsQuery.data ? (
              <div className="state-card error">Unable to load collections insights.</div>
            ) : (
              <>
                <section className="summary-grid collections-insights-grid">
                  <article className="card stat-card">
                    <div className="stat-card-header">
                      <span>Collection rate</span>
                      <small>How much of this month's invoices has been collected</small>
                    </div>
                    <strong>{analyticsQuery.data.collection_rate_percentage}%</strong>
                  </article>
                  <article className="card stat-card">
                    <div className="stat-card-header">
                      <span>Average time to get paid</span>
                      <small>Based on fully paid invoices</small>
                    </div>
                    <strong>{analyticsQuery.data.average_days_to_payment} days</strong>
                  </article>
                  <article className="card stat-card">
                    <div className="stat-card-header">
                      <span>At risk now</span>
                      <small>Invoices over 14 days late or repeatedly reminded</small>
                    </div>
                    <strong>{analyticsQuery.data.high_risk_invoices.length}</strong>
                  </article>
                </section>

                <div className="ageing-bucket-grid">
                  {ageingBucketRows.map((bucket) => {
                    const value = analyticsQuery.data.overdue_ageing_buckets[bucket.key];
                    return (
                      <article className="oldest-overdue-grid-item" key={bucket.key}>
                        <span className="field-label">{bucket.label}</span>
                        <p>R {value.amount}</p>
                        <small>{value.count} invoice{value.count === 1 ? "" : "s"}. {bucket.note}</small>
                      </article>
                    );
                  })}
                </div>

                {analyticsQuery.data.high_risk_invoices.length ? (
                  <div className="table-wrap">
                    <table className="invoice-table collections-table">
                      <thead>
                        <tr>
                          <th>Invoice</th>
                          <th>Client</th>
                          <th>Days late</th>
                          <th>Outstanding</th>
                          <th>Reminders</th>
                          <th>Action</th>
                        </tr>
                      </thead>
                      <tbody>
                        {analyticsQuery.data.high_risk_invoices.map((invoice) => (
                          <tr key={invoice.id}>
                            <td>{invoice.invoice_number}</td>
                            <td>{invoice.client_name}</td>
                            <td>{invoice.days_overdue}</td>
                            <td>R {invoice.outstanding_amount}</td>
                            <td>{invoice.reminder_sent_count}</td>
                            <td>
                              <Link className="button button-ghost button-nav" href={`/invoices/${invoice.id}`}>
                                Open
                              </Link>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : (
                  <div className="state-card">No high-risk invoices right now.</div>
                )}
              </>
            )}
          </section>

          <section className="card panel dashboard-panel">
            <div className="panel-heading">
              <div>
                <p className="eyebrow">Overdue</p>
                <h3 className="section-title">Invoices ordered by oldest due date</h3>
              </div>
              {reminderMutation.isError ? (
                <span className="inline-error">{getErrorMessage(reminderMutation.error)}</span>
              ) : null}
            </div>

            <OverdueInvoicesTable
              invoices={summaryQuery.data.overdue_invoice_table}
              onSendReminder={(invoiceId) => reminderMutation.mutate(invoiceId)}
              sendingInvoiceId={reminderMutation.isPending ? Number(reminderMutation.variables) : null}
            />
          </section>
        </>
      )}
    </div>
  );
}
