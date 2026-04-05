import { RecurringInvoiceForm } from "@/components/recurring-invoices/recurring-invoice-form";

export default async function RecurringInvoiceDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return <RecurringInvoiceForm recurringInvoiceId={id} />;
}
