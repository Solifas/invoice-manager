import { DashboardSummary, Invoice, InvoiceListResponse } from "@/lib/types";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000/api";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers || {}),
    },
    cache: "no-store",
  });

  if (!response.ok) {
    const contentType = response.headers.get("content-type");
    const payload = contentType?.includes("application/json") ? await response.json() : await response.text();
    throw new Error(typeof payload === "string" ? payload : JSON.stringify(payload));
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return response.json() as Promise<T>;
}

function invoicePayload(invoice: Invoice) {
  return {
    invoice_number: invoice.invoice_number,
    client: invoice.client,
    issue_date: invoice.issue_date,
    due_date: invoice.due_date,
    status: invoice.status,
    notes: invoice.notes,
    currency: invoice.currency,
    tax_type: invoice.tax_type,
    tax_rate: invoice.tax_rate,
    line_items: invoice.line_items.map((item) => ({
      description: item.description,
      quantity: item.quantity,
      unit_price: item.unit_price,
    })),
  };
}

export async function fetchInvoices(params?: { status?: string; search?: string }) {
  const searchParams = new URLSearchParams();
  if (params?.status && params.status !== "all") {
    searchParams.set("status", params.status);
  }
  if (params?.search) {
    searchParams.set("search", params.search);
  }
  const query = searchParams.toString();
  return request<InvoiceListResponse>(`/invoices/${query ? `?${query}` : ""}`);
}

export async function fetchInvoice(id: string) {
  return request<Invoice>(`/invoices/${id}/`);
}

export async function fetchDashboardSummary() {
  return request<DashboardSummary>("/invoices/dashboard-summary/");
}

export async function createInvoice(payload: unknown) {
  return request<Invoice>("/invoices/", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function updateInvoice(id: string, payload: unknown) {
  return request<Invoice>(`/invoices/${id}/`, {
    method: "PUT",
    body: JSON.stringify(payload),
  });
}

export async function updateInvoiceStatus(id: string, status: string) {
  const invoice = await fetchInvoice(id);
  return updateInvoice(id, { ...invoicePayload(invoice), status });
}

export async function deleteInvoice(id: string) {
  return request<void>(`/invoices/${id}/`, {
    method: "DELETE",
  });
}

export async function sendReminder(id: string) {
  return request<{ detail: string }>(`/invoices/${id}/send-reminder/`, {
    method: "POST",
  });
}

export function getInvoicePdfUrl(id: string) {
  return `${API_BASE_URL}/invoices/${id}/pdf/`;
}
