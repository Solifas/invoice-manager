export type InvoiceStatus = "draft" | "sent" | "paid" | "overdue" | "cancelled";
export type TaxType = "none" | "percentage";
export type ReminderChannel = "email" | "whatsapp";
export type RecurringInvoiceFrequency = "weekly" | "monthly" | "quarterly";
export type RecurringInvoiceStatus = "active" | "paused" | "cancelled";
export type CurrencyCode = string;
export type InvoiceEftMode = "saved_profile" | "manual" | "";

export interface CurrencyOption {
  code: string;
  name: string;
}

export interface UserProfile {
  id: number;
  email: string;
  first_name: string;
  last_name: string;
}

export interface BankingProfile {
  id: number;
  profile_name: string;
  account_holder_name: string;
  bank_name: string;
  account_number: string;
  account_type: string;
  branch_code: string;
  default_payment_reference: string;
  is_default: boolean;
  is_active: boolean;
  created_at?: string;
  updated_at?: string;
}

export interface BankingProfileInput {
  profile_name: string;
  account_holder_name: string;
  bank_name: string;
  account_number: string;
  account_type?: string;
  branch_code?: string;
  default_payment_reference?: string;
}

export type BusinessVerificationStatus = "not_started" | "pending" | "verified" | "rejected";

export interface BusinessProfile {
  id: number;
  business_name: string;
  business_type: string;
  registration_number: string;
  vat_number: string;
  trading_name: string;
  contact_email: string;
  contact_phone_number: string;
  business_address: string;
  verification_status: BusinessVerificationStatus;
  completeness_percentage: number;
  created_at?: string;
  updated_at?: string;
}

export type BusinessProfileInput = Omit<BusinessProfile, "id" | "completeness_percentage" | "created_at" | "updated_at">;

export interface InvoiceEftSnapshot {
  mode: InvoiceEftMode;
  banking_profile_id: number | null;
  profile_name: string;
  account_holder_name: string;
  bank_name: string;
  account_number: string;
  account_type: string;
  branch_code: string;
  payment_reference: string;
  has_snapshot: boolean;
}

export interface Client {
  id?: number;
  name: string;
  email: string;
  address: string;
  phone_number: string;
}

export interface Contractor {
  id: number;
  name: string;
  email: string;
  contact_number: string;
  address: string;
}

export type ContractorInput = Omit<Contractor, "id">;

export interface InvoiceLineItem {
  id?: number;
  description: string;
  quantity: string;
  unit_price: string;
  line_total?: string;
}

export interface InvoicePayment {
  id?: number;
  amount: string;
  payment_date: string;
  payment_method: string;
  reference: string;
  notes: string;
  created_at?: string;
  updated_at?: string;
}

export interface Invoice {
  id: number;
  invoice_number: string;
  client: Client;
  issue_date: string;
  due_date: string;
  status: InvoiceStatus;
  notes: string;
  currency: CurrencyCode;
  tax_type: TaxType;
  tax_rate: string;
  subtotal: string;
  tax_amount: string;
  total_amount: string;
  amount_paid: string;
  outstanding_amount: string;
  payment_page_enabled: boolean;
  public_token: string;
  public_payment_url: string;
  payment_link_available: boolean;
  eft_snapshot: InvoiceEftSnapshot;
  eft_source_type?: InvoiceEftMode;
  eft_source_profile?: number | null;
  eft_profile_name?: string;
  eft_account_holder_name: string;
  eft_bank_name: string;
  eft_account_number: string;
  eft_account_type: string;
  eft_branch_code: string;
  payment_reference: string;
  line_items: InvoiceLineItem[];
  payments: InvoicePayment[];
  created_at: string;
  updated_at: string;
}

export interface InvoiceSummary {
  id: number;
  invoice_number: string;
  client: Client;
  issue_date: string;
  due_date: string;
  status: InvoiceStatus;
  currency: CurrencyCode;
  total_amount: string;
  subtotal: string;
  amount_paid: string;
  outstanding_amount: string;
}

export interface InvoiceListResponse {
  count: number;
  next: string | null;
  previous: string | null;
  results: InvoiceSummary[];
}

export interface PaymentLinkActivity {
  payment_page_enabled: boolean;
  public_token: string;
  public_payment_url: string;
  payment_link_available: boolean;
  public_token_regenerated_at: string | null;
  payment_page_first_opened_at: string | null;
  payment_page_last_opened_at: string | null;
  payment_page_open_count: number;
  reminder_last_sent_at: string | null;
}

export interface CollectionsInvoiceSummary {
  id: number;
  invoice_number: string;
  client_name: string;
  due_date: string;
  outstanding_amount: string;
  status: InvoiceStatus;
}

export interface DashboardSummary {
  total_invoices: number;
  unpaid_invoices: number;
  overdue_invoices: number;
  total_amount_outstanding: string;
  total_overdue_amount: string;
  due_next_7_days_invoices: number;
  paid_invoices_this_month: number;
  collected_amount_this_month: string;
  oldest_overdue_invoice: CollectionsInvoiceSummary | null;
  overdue_invoice_table: CollectionsInvoiceSummary[];
}

export interface CollectionsAgeingBucket {
  count: number;
  amount: string;
}

export interface HighRiskInvoice {
  id: number;
  invoice_number: string;
  client_name: string;
  due_date: string;
  days_overdue: number;
  outstanding_amount: string;
  reminder_sent_count: number;
  status: InvoiceStatus;
}

export interface CollectionsAnalytics {
  total_invoiced_this_month: string;
  total_collected_this_month: string;
  total_outstanding: string;
  total_overdue: string;
  average_days_to_payment: number;
  collection_rate_percentage: string;
  overdue_ageing_buckets: {
    one_to_seven_days: CollectionsAgeingBucket;
    eight_to_fourteen_days: CollectionsAgeingBucket;
    fifteen_to_thirty_days: CollectionsAgeingBucket;
    thirty_one_plus_days: CollectionsAgeingBucket;
  };
  high_risk_invoices: HighRiskInvoice[];
}

export interface PublicPaymentEftDetails {
  profile_name: string;
  account_holder_name: string;
  bank_name: string;
  account_number: string;
  account_type: string;
  branch_code: string;
}

export interface PublicInvoicePaymentPage {
  invoice_number: string;
  client_name: string;
  issue_date: string;
  due_date: string;
  status: InvoiceStatus;
  subtotal: string;
  tax: string;
  total: string;
  amount_paid: string;
  outstanding_amount: string;
  eft_details: PublicPaymentEftDetails;
  payment_reference: string;
}

export interface RecurringInvoiceLineItemTemplate {
  description: string;
  quantity: string;
  unit_price: string;
}

export interface RecurringInvoice {
  id: number;
  template_name: string;
  client?: Client;
  client_id: number;
  contractor?: Contractor | null;
  contractor_id?: number | null;
  frequency: RecurringInvoiceFrequency;
  start_date: string;
  end_date: string | null;
  next_run_date: string | null;
  status: RecurringInvoiceStatus;
  currency: CurrencyCode;
  payment_terms_days: number;
  tax_type: TaxType;
  tax_rate: string;
  notes: string;
  line_items_template: RecurringInvoiceLineItemTemplate[];
  created_at?: string;
  updated_at?: string;
}

export interface RecurringInvoiceListResponse {
  count: number;
  next: string | null;
  previous: string | null;
  results: RecurringInvoice[];
}
