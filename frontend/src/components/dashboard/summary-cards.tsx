import { DashboardSummary } from "@/lib/types";

const cards = [
  { key: "total_invoices", label: "Total invoices", note: "Across all statuses", filterKey: "all" },
  { key: "unpaid_invoices", label: "Unpaid invoices", note: "Draft, sent, and overdue", filterKey: "unpaid" },
  { key: "overdue_invoices", label: "Overdue invoices", note: "Needs immediate follow-up", filterKey: "overdue" },
  { key: "total_amount_outstanding", label: "Outstanding amount", note: "Open balance still to collect", filterKey: "unpaid" },
] as const;

export function SummaryCards({
  summary,
  activeFilter,
  onSelectFilter,
}: {
  summary: DashboardSummary;
  activeFilter: "all" | "unpaid" | "overdue";
  onSelectFilter: (filter: "all" | "unpaid" | "overdue") => void;
}) {
  return (
    <section className="summary-grid">
      {cards.map((card) => (
        <button
          className={`card stat-card stat-card-button ${activeFilter === card.filterKey ? "is-active" : ""}`}
          key={card.key}
          onClick={() => onSelectFilter(card.filterKey)}
          type="button"
        >
          <div className="stat-card-header">
            <span>{card.label}</span>
            <small>{card.note}</small>
          </div>
          <strong>
            {card.key === "total_amount_outstanding"
              ? summary.total_amount_outstanding
              : summary[card.key].toString()}
          </strong>
        </button>
      ))}
    </section>
  );
}
