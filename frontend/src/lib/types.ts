export type InvoiceStatus = "draft" | "sent" | "paid" | "overdue" | "cancelled";
export type TaxType = "none" | "percentage";

export interface Client {
  id?: number;
  name: string;
  email: string;
  address: string;
}

export interface InvoiceLineItem {
  id?: number;
  description: string;
  quantity: string;
  unit_price: string;
  line_total?: string;
}

export interface Invoice {
  id: number;
  invoice_number: string;
  client: Client;
  issue_date: string;
  due_date: string;
  status: InvoiceStatus;
  notes: string;
  currency: string;
  tax_type: TaxType;
  tax_rate: string;
  subtotal: string;
  tax_amount: string;
  total_amount: string;
  line_items: InvoiceLineItem[];
  created_at: string;
  updated_at: string;
}

export interface InvoiceListResponse {
  count: number;
  next: string | null;
  previous: string | null;
  results: Invoice[];
}

export interface DashboardSummary {
  total_invoices: number;
  unpaid_invoices: number;
  overdue_invoices: number;
  total_amount_outstanding: string;
}
