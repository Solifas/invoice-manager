import { InvoiceStatus } from "@/lib/types";

export function StatusBadge({ status }: { status: InvoiceStatus }) {
  return (
    <span className={`status-badge status-${status}`}>
      <span className="status-dot" />
      {status}
    </span>
  );
}
