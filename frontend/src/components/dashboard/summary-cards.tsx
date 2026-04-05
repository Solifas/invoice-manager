import { DashboardSummary } from "@/lib/types";

const cards = [
  { key: "total_invoices", label: "Total invoices", note: "Across all statuses" },
  { key: "unpaid_invoices", label: "Unpaid invoices", note: "Draft, sent, and overdue" },
  { key: "overdue_invoices", label: "Overdue invoices", note: "Needs immediate follow-up" },
  { key: "total_amount_outstanding", label: "Outstanding amount", note: "Open balance still to collect" },
] as const;

export function SummaryCards({ summary }: { summary: DashboardSummary }) {
  return (
    <section className="summary-grid">
      {cards.map((card) => (
        <article className="card stat-card" key={card.key}>
          <div className="stat-card-header">
            <span>{card.label}</span>
            <small>{card.note}</small>
          </div>
          <strong>
            {card.key === "total_amount_outstanding"
              ? summary.total_amount_outstanding
              : summary[card.key].toString()}
          </strong>
        </article>
      ))}
    </section>
  );
}
