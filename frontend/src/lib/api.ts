import {
  BankingProfile,
  BankingProfileInput,
  Client,
  Contractor,
  DashboardSummary,
  Invoice,
  InvoiceEftSnapshot,
  InvoiceListResponse,
  InvoicePayment,
  PublicInvoicePaymentPage,
  RecurringInvoice,
  RecurringInvoiceListResponse,
  ReminderChannel,
  UserProfile,
} from "@/lib/types";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000/api";

export class ApiError extends Error {
  status: number;
  payload: unknown;

  constructor(message: string, status: number, payload: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.payload = payload;
  }
}

function getCookie(name: string) {
  if (typeof document === "undefined") {
    return "";
  }

  return document.cookie
    .split("; ")
    .find((cookie) => cookie.startsWith(`${name}=`))
    ?.split("=")[1] || "";
}

async function ensureCsrfCookie() {
  if (typeof window === "undefined" || getCookie("csrftoken")) {
    return;
  }

  await fetch(`${API_BASE_URL}/auth/csrf/`, {
    credentials: "include",
    cache: "no-store",
  });
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const method = (init?.method || "GET").toUpperCase();
  const headers = new Headers(init?.headers || {});
  const needsCsrf = !["GET", "HEAD", "OPTIONS", "TRACE"].includes(method);

  if (!headers.has("Content-Type") && init?.body) {
    headers.set("Content-Type", "application/json");
  }

  if (needsCsrf) {
    await ensureCsrfCookie();
    const csrfToken = getCookie("csrftoken");
    if (csrfToken) {
      headers.set("X-CSRFToken", decodeURIComponent(csrfToken));
    }
  }

  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    credentials: "include",
    headers,
    cache: "no-store",
  });

  if (!response.ok) {
    const contentType = response.headers.get("content-type");
    const payload = contentType?.includes("application/json") ? await response.json() : await response.text();
    throw new ApiError(typeof payload === "string" ? payload : JSON.stringify(payload), response.status, payload);
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
    payment_page_enabled: invoice.payment_page_enabled ?? false,
    line_items: (invoice.line_items ?? []).map((item) => ({
      description: item.description,
      quantity: item.quantity,
      unit_price: item.unit_price,
    })),
  };
}

export function getErrorMessage(error: unknown) {
  if (error instanceof ApiError && typeof error.payload === "object" && error.payload !== null) {
    return Object.entries(error.payload as Record<string, string[] | string>)
      .map(([key, value]) => `${key}: ${Array.isArray(value) ? value.join(", ") : value}`)
      .join(" | ");
  }

  if (error instanceof Error) {
    try {
      const parsed = JSON.parse(error.message) as Record<string, string[] | string>;
      return Object.entries(parsed)
        .map(([key, value]) => `${key}: ${Array.isArray(value) ? value.join(", ") : value}`)
        .join(" | ");
    } catch {
      return error.message;
    }
  }

  return "Something went wrong.";
}

export async function fetchCsrfCookie() {
  await ensureCsrfCookie();
}

export async function fetchCurrentUser() {
  return request<UserProfile>("/auth/me/");
}

export async function loginUser(payload: { email: string; password: string }) {
  return request<UserProfile>("/auth/login/", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function registerUser(payload: {
  email: string;
  password: string;
  confirm_password: string;
  first_name?: string;
  last_name?: string;
  banking_profile?: BankingProfileInput;
}) {
  return request<UserProfile>("/auth/register/", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function logoutUser() {
  return request<void>("/auth/logout/", {
    method: "POST",
    body: JSON.stringify({}),
  });
}

export async function forgotPassword(payload: { email: string }) {
  return request<{ detail: string }>("/auth/forgot-password/", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function resetPassword(payload: {
  uid: string;
  token: string;
  password: string;
  confirm_password: string;
}) {
  return request<{ detail: string }>("/auth/reset-password/", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function fetchInvoices(params?: { status?: string; search?: string; statusGroup?: string }) {
  const searchParams = new URLSearchParams();
  if (params?.status && params.status !== "all") {
    searchParams.set("status", params.status);
  }
  if (params?.statusGroup) {
    searchParams.set("status_group", params.statusGroup);
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

export async function fetchPublicPayment(token: string) {
  return request<PublicInvoicePaymentPage>(`/public/pay/${token}/`);
}

export async function fetchDashboardSummary() {
  return request<DashboardSummary>("/invoices/dashboard-summary/");
}

export async function fetchClients() {
  return request<Client[]>("/clients/");
}

export async function fetchContractors() {
  return request<Contractor[]>("/contractors/");
}

export async function fetchBankingProfiles() {
  return request<BankingProfile[]>("/banking-profiles/");
}

export async function createBankingProfile(payload: BankingProfileInput & { is_default?: boolean }) {
  return request<BankingProfile>("/banking-profiles/", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function updateBankingProfile(id: string, payload: Partial<BankingProfileInput> & { is_default?: boolean }) {
  return request<BankingProfile>(`/banking-profiles/${id}/`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export async function deleteBankingProfile(id: string) {
  return request<void>(`/banking-profiles/${id}/`, {
    method: "DELETE",
  });
}

export async function setDefaultBankingProfile(id: string) {
  return request<BankingProfile>(`/banking-profiles/${id}/set-default/`, {
    method: "POST",
    body: JSON.stringify({}),
  });
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

export async function fetchInvoiceEftDetails(id: string) {
  return request<InvoiceEftSnapshot>(`/invoices/${id}/eft-details/`);
}

export async function updateInvoiceEftDetails(id: string, payload: unknown) {
  return request<InvoiceEftSnapshot>(`/invoices/${id}/eft-details/`, {
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

export async function sendReminder(id: string, channel: ReminderChannel = "email") {
  return request<{ detail: string }>(`/invoices/${id}/remind/`, {
    method: "POST",
    body: JSON.stringify({ channel }),
  });
}

export async function recordInvoicePayment(id: string, payload: Omit<InvoicePayment, "id" | "created_at" | "updated_at">) {
  return request<InvoicePayment>(`/invoices/${id}/payments/`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function updateInvoicePayment(id: string, payload: Partial<InvoicePayment>) {
  return request<InvoicePayment>(`/payments/${id}/`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export async function regeneratePaymentPageToken(id: string) {
  return request<Invoice>(`/invoices/${id}/payment-page/regenerate-token/`, {
    method: "POST",
  });
}

export async function fetchRecurringInvoices() {
  return request<RecurringInvoiceListResponse>("/recurring-invoices/");
}

export async function fetchRecurringInvoice(id: string) {
  return request<RecurringInvoice>(`/recurring-invoices/${id}/`);
}

export async function createRecurringInvoice(payload: unknown) {
  return request<RecurringInvoice>("/recurring-invoices/", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function updateRecurringInvoice(id: string, payload: unknown) {
  return request<RecurringInvoice>(`/recurring-invoices/${id}/`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export async function deleteRecurringInvoice(id: string) {
  return request<void>(`/recurring-invoices/${id}/`, {
    method: "DELETE",
  });
}

export function getInvoicePdfUrl(id: string) {
  return `${API_BASE_URL}/invoices/${id}/pdf/`;
}
