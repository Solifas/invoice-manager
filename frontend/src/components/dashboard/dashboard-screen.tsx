"use client";

import { useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { fetchDashboardSummary, fetchInvoices } from "@/lib/api";
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

  const summaryQuery = useQuery({
    queryKey: ["dashboard-summary"],
    queryFn: fetchDashboardSummary,
  });

  const invoicesQuery = useQuery({
    queryKey: ["invoices", status, search],
    queryFn: () => fetchInvoices({ status, search }),
  });

  return (
    <div className="dashboard-stack">
      <section className="hero-panel">
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
        <SummaryCards summary={summaryQuery.data} />
      )}

      <section className="card panel">
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
              onChange={(event) => setStatus(event.target.value as InvoiceStatus | "all")}
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
