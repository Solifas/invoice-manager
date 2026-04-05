import { PublicPaymentPage } from "@/components/payments/public-payment-page";

export default async function PayInvoicePage({
  params,
}: {
  params: Promise<{ token: string }>;
}) {
  const { token } = await params;
  return <PublicPaymentPage token={token} />;
}
