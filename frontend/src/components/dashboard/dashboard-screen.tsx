"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { fetchDashboardSummary, fetchInvoices, fetchRecurringInvoices } from "@/lib/api";
import { InvoiceStatus } from "@/lib/types";
import { SummaryCards } from "@/components/dashboard/summary-cards";
import { InvoiceTable } from "@/components/invoices/invoice-table";

const statusOptions: Array<{ label: string; value: InvoiceStatus | "all" }> = [
  { label: "All", value: "all" },
  { label: "Draft", value: "draft" },
  { label: "Sent", value: "sent" },
  { label: "Paid", value: "paid" },
  { label: "Overdue", value: "overdue" },
  { label: "Cancelled", value: "cancelled" },
];

export function DashboardScreen() {
  const [status, setStatus] = useState<InvoiceStatus | "all">("all");
  const [search, setSearch] = useState("");
  const [statusGroup, setStatusGroup] = useState<"all" | "unpaid" | "overdue">("all");

  const summaryQuery = useQuery({
    queryKey: ["dashboard-summary"],
    queryFn: fetchDashboardSummary,
  });

  const invoicesQuery = useQuery({
    queryKey: ["invoices", status, statusGroup, search],
    queryFn: () => fetchInvoices({ status, statusGroup: statusGroup === "all" ? undefined : statusGroup, search }),
  });
  const recurringQuery = useQuery({
    queryKey: ["recurring-invoices"],
    queryFn: fetchRecurringInvoices,
  });

  const recurringInvoices = recurringQuery.data?.results ?? [];
  const activeRecurringCount = recurringInvoices.filter((item) => item.status === "active").length;
  const recurringNextRun = recurringInvoices
    .map((item) => item.next_run_date)
    .filter((value): value is string => Boolean(value))
    .sort()[0];

  return (
    <div className="dashboard-stack">
      <section className="hero-panel dashboard-hero">
        <div>
          <p className="eyebrow">Overview</p>
          <h2 className="section-title">Your invoice desk</h2>
          <p className="subtle-copy">
            Review open balances, catch overdue accounts, and jump straight into the invoices that need attention.
          </p>
        </div>
      </section>

      {summaryQuery.isLoading ? (
        <section className="summary-grid">
          {Array.from({ length: 4 }).map((_, index) => (
            <div className="card skeleton" key={index} />
          ))}
        </section>
      ) : summaryQuery.isError || !summaryQuery.data ? (
        <div className="card state-card error">Unable to load summary data.</div>
      ) : (
        <SummaryCards
          activeFilter={statusGroup}
          onSelectFilter={(filter) => {
            setStatusGroup(filter);
            if (filter !== "all") {
              setStatus("all");
            }
          }}
          summary={summaryQuery.data}
        />
      )}

      <section className="card panel dashboard-recurring-panel">
        <div className="panel-heading">
          <div>
            <p className="eyebrow">Recurring</p>
            <h3 className="section-title">Schedules at a glance</h3>
            <p className="subtle-copy">
              Keep an eye on repeating templates and the next invoice dates without leaving the dashboard.
            </p>
          </div>
          <div className="detail-actions">
            <Link className="button button-ghost" href="/recurring-invoices">
              Open recurring
            </Link>
            <Link className="button" href="/recurring-invoices/new">
              New schedule
            </Link>
          </div>
        </div>

        {recurringQuery.isLoading ? (
          <div className="summary-grid">
            {Array.from({ length: 3 }).map((_, index) => (
              <div className="card skeleton" key={index} />
            ))}
          </div>
        ) : recurringQuery.isError ? (
          <div className="state-card error">Unable to load recurring schedules.</div>
        ) : recurringInvoices.length ? (
          <>
            <div className="summary-grid dashboard-recurring-summary">
              <article className="card stat-card recurring-stat-card">
                <div className="stat-card-header">
                  <span>Recurring templates</span>
                  <small>Total schedules configured</small>
                </div>
                <strong>{recurringInvoices.length}</strong>
              </article>
              <article className="card stat-card recurring-stat-card">
                <div className="stat-card-header">
                  <span>Active schedules</span>
                  <small>Templates that can generate invoices</small>
                </div>
                <strong>{activeRecurringCount}</strong>
              </article>
              <article className="card stat-card recurring-stat-card">
                <div className="stat-card-header">
                  <span>Next run</span>
                  <small>Nearest upcoming scheduled invoice</small>
                </div>
                <strong>{recurringNextRun || "Not scheduled"}</strong>
              </article>
            </div>

            <div className="dashboard-recurring-list">
              {recurringInvoices.slice(0, 3).map((recurringInvoice) => (
                <article className="recurring-item-card dashboard-recurring-item" key={recurringInvoice.id}>
                  <div className="recurring-item-main">
                    <Link className="invoice-link" href={`/recurring-invoices/${recurringInvoice.id}`}>
                      <span>{recurringInvoice.template_name}</span>
                      <small>{recurringInvoice.client?.name || `Client #${recurringInvoice.client_id}`}</small>
                    </Link>
                    <div className="recurring-item-meta">
                      <div>
                        <span className="field-label">Frequency</span>
                        <p>{recurringInvoice.frequency}</p>
                      </div>
                      <div>
                        <span className="field-label">Next run</span>
                        <p>{recurringInvoice.next_run_date || "Not scheduled"}</p>
                      </div>
                      <div>
                        <span className="field-label">Status</span>
                        <span className={`schedule-status-badge schedule-status-${recurringInvoice.status}`}>
                          {recurringInvoice.status}
                        </span>
                      </div>
                    </div>
                  </div>
                  <div className="recurring-item-actions">
                    <Link className="button button-ghost" href={`/recurring-invoices/${recurringInvoice.id}`}>
                      Open
                    </Link>
                  </div>
                </article>
              ))}
            </div>
          </>
        ) : (
          <div className="state-card">No recurring schedules configured yet.</div>
        )}
      </section>

      <section className="card panel dashboard-panel">
        <div className="panel-heading">
          <div>
            <p className="eyebrow">Invoices</p>
            <h3 className="section-title">Recent activity</h3>
          </div>
          <div className="toolbar">
            <input
              aria-label="Search invoices"
              className="input toolbar-search"
              placeholder="Search by client or invoice number"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
            />
            <select
              className="input toolbar-select"
              value={status}
              onChange={(event) => {
                setStatus(event.target.value as InvoiceStatus | "all");
                setStatusGroup("all");
              }}
            >
              {statusOptions.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </div>
        </div>

        <InvoiceTable
          invoices={invoicesQuery.data?.results ?? []}
          isLoading={invoicesQuery.isLoading}
          isError={invoicesQuery.isError}
        />
      </section>
    </div>
  );
}
