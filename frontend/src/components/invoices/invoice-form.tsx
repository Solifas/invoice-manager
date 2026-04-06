"use client";

import Link from "next/link";
import { useMutation, useQuery } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import {
  createInvoice,
  fetchBankingProfiles,
  fetchInvoice,
  getErrorMessage,
  updateInvoice,
  updateInvoiceEftDetails,
} from "@/lib/api";
import { getBankNameOptions } from "@/lib/banking";
import { BankingProfile, CurrencyCode, Invoice, InvoiceEftMode, InvoiceLineItem, InvoiceStatus, TaxType } from "@/lib/types";

const emptyItem = (): InvoiceLineItem => ({
  description: "",
  quantity: "1",
  unit_price: "0.00",
});

const currencyOptions: Array<{ value: CurrencyCode; label: string }> = [
  { value: "ZAR", label: "ZAR · South African rand" },
  { value: "USD", label: "USD · US dollar" },
];

type InvoiceEftFormState = {
  mode: InvoiceEftMode;
  banking_profile_id: string;
  profile_name: string;
  account_holder_name: string;
  bank_name: string;
  account_number: string;
  account_type: string;
  branch_code: string;
  payment_reference: string;
};

const emptyEftState = (): InvoiceEftFormState => ({
  mode: "",
  banking_profile_id: "",
  profile_name: "",
  account_holder_name: "",
  bank_name: "",
  account_number: "",
  account_type: "",
  branch_code: "",
  payment_reference: "",
});

function buildEftStateFromInvoice(invoice: Invoice): InvoiceEftFormState {
  const snapshot = invoice.eft_snapshot;
  return {
    mode: snapshot.mode,
    banking_profile_id: snapshot.banking_profile_id ? String(snapshot.banking_profile_id) : "",
    profile_name: snapshot.profile_name || "",
    account_holder_name: snapshot.account_holder_name || "",
    bank_name: snapshot.bank_name || "",
    account_number: snapshot.account_number || "",
    account_type: snapshot.account_type || "",
    branch_code: snapshot.branch_code || "",
    payment_reference: invoice.payment_reference || snapshot.payment_reference || "",
  };
}

function buildEftPayload(eftState: InvoiceEftFormState) {
  if (eftState.mode === "saved_profile") {
    return {
      mode: "saved_profile" as const,
      banking_profile_id: Number(eftState.banking_profile_id),
      payment_reference: eftState.payment_reference,
    };
  }

  return {
    mode: "manual" as const,
    profile_name: eftState.profile_name,
    account_holder_name: eftState.account_holder_name,
    bank_name: eftState.bank_name,
    account_number: eftState.account_number,
    account_type: eftState.account_type,
    branch_code: eftState.branch_code,
    payment_reference: eftState.payment_reference,
  };
}

function invoiceToPayload(invoice: Invoice) {
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

export function InvoiceForm({ invoiceId }: { invoiceId?: string }) {
  const router = useRouter();
  const [eftState, setEftState] = useState<InvoiceEftFormState>(emptyEftState);
  const [eftError, setEftError] = useState("");
  const [formState, setFormState] = useState<Invoice>({
    id: 0,
    invoice_number: "",
    client: { name: "", email: "", address: "", phone_number: "" },
    issue_date: "",
    due_date: "",
    status: "draft",
    notes: "",
    currency: "ZAR",
    tax_type: "none",
    tax_rate: "0.00",
    subtotal: "0.00",
    tax_amount: "0.00",
    total_amount: "0.00",
    amount_paid: "0.00",
    outstanding_amount: "0.00",
    payment_page_enabled: false,
    public_token: "",
    public_payment_url: "",
    payment_link_available: false,
    eft_snapshot: {
      mode: "",
      banking_profile_id: null,
      profile_name: "",
      account_holder_name: "",
      bank_name: "",
      account_number: "",
      account_type: "",
      branch_code: "",
      payment_reference: "",
      has_snapshot: false,
    },
    eft_source_type: "",
    eft_source_profile: null,
    eft_profile_name: "",
    eft_account_holder_name: "",
    eft_bank_name: "",
    eft_account_number: "",
    eft_account_type: "",
    eft_branch_code: "",
    payment_reference: "",
    line_items: [emptyItem()],
    payments: [],
    created_at: "",
    updated_at: "",
  });

  const invoiceQuery = useQuery({
    queryKey: ["invoice", invoiceId],
    queryFn: () => fetchInvoice(invoiceId!),
    enabled: Boolean(invoiceId),
  });
  const bankingProfilesQuery = useQuery({
    queryKey: ["banking-profiles"],
    queryFn: fetchBankingProfiles,
  });

  useEffect(() => {
    if (invoiceQuery.data) {
      setFormState(invoiceQuery.data);
      setEftState(buildEftStateFromInvoice(invoiceQuery.data));
    }
  }, [invoiceQuery.data]);

  useEffect(() => {
    if (invoiceId) {
      return;
    }
    setFormState((current) => {
      if (current.issue_date && current.due_date) {
        return current;
      }
      const today = new Date().toISOString().slice(0, 10);
      return {
        ...current,
        issue_date: current.issue_date || today,
        due_date: current.due_date || today,
      };
    });
  }, [invoiceId]);

  useEffect(() => {
    if (invoiceId || !bankingProfilesQuery.data?.length || eftState.mode || !formState.payment_page_enabled) {
      return;
    }
    const defaultProfile = bankingProfilesQuery.data.find((profile) => profile.is_default) || bankingProfilesQuery.data[0];
    if (!defaultProfile) {
      return;
    }
    setEftState({
      mode: "saved_profile",
      banking_profile_id: String(defaultProfile.id),
      profile_name: defaultProfile.profile_name,
      account_holder_name: defaultProfile.account_holder_name,
      bank_name: defaultProfile.bank_name,
      account_number: defaultProfile.account_number,
      account_type: defaultProfile.account_type,
      branch_code: defaultProfile.branch_code,
      payment_reference: defaultProfile.default_payment_reference,
    });
  }, [bankingProfilesQuery.data, eftState.mode, formState.payment_page_enabled, invoiceId]);

  const mutation = useMutation({
    mutationFn: async () => {
      setEftError("");
      if (formState.payment_page_enabled) {
        if (!eftState.mode) {
          throw new Error("Choose whether this invoice should use a saved banking profile or manual EFT details.");
        }
        if (eftState.mode === "saved_profile" && !eftState.banking_profile_id) {
          throw new Error("Choose a saved banking profile for this invoice.");
        }
        if (
          eftState.mode === "manual" &&
          (!eftState.profile_name || !eftState.account_holder_name || !eftState.bank_name || !eftState.account_number)
        ) {
          throw new Error("Complete the required manual EFT details before enabling the public payment page.");
        }
      }
      const payload = invoiceToPayload(formState);
      const invoice = invoiceId ? await updateInvoice(invoiceId, payload) : await createInvoice(payload);
      if (formState.payment_page_enabled && eftState.mode) {
        await updateInvoiceEftDetails(String(invoice.id), buildEftPayload(eftState));
      }
      return invoice;
    },
    onSuccess: (invoice) => {
      router.push(`/invoices/${invoice.id}`);
    },
    onError: (error) => {
      setEftError(getErrorMessage(error));
    },
  });

  const selectedBankingProfile =
    bankingProfilesQuery.data?.find((profile) => String(profile.id) === eftState.banking_profile_id) || null;

  const updateEftFromProfile = (profile: BankingProfile) => {
    setEftState({
      mode: "saved_profile",
      banking_profile_id: String(profile.id),
      profile_name: profile.profile_name,
      account_holder_name: profile.account_holder_name,
      bank_name: profile.bank_name,
      account_number: profile.account_number,
      account_type: profile.account_type,
      branch_code: profile.branch_code,
      payment_reference: profile.default_payment_reference,
    });
  };

  const selectDefaultProfile = () => {
    const defaultProfile = bankingProfilesQuery.data?.find((profile) => profile.is_default) || bankingProfilesQuery.data?.[0];
    if (defaultProfile) {
      updateEftFromProfile(defaultProfile);
    } else {
      setEftState((current) => ({ ...current, mode: "saved_profile" }));
    }
  };

  const updateItem = (index: number, next: Partial<InvoiceLineItem>) => {
    setFormState((current) => ({
      ...current,
      line_items: current.line_items.map((item, itemIndex) =>
        itemIndex === index ? { ...item, ...next } : item,
      ),
    }));
  };

  if (invoiceQuery.isLoading || bankingProfilesQuery.isLoading) {
    return <div className="card state-card">Loading invoice...</div>;
  }

  if (invoiceQuery.isError || bankingProfilesQuery.isError) {
    return <div className="card state-card error">Unable to load invoice.</div>;
  }

  const previewSubtotal = formState.line_items.reduce((total, item) => {
    const quantity = Number(item.quantity) || 0;
    const unitPrice = Number(item.unit_price) || 0;
    return total + quantity * unitPrice;
  }, 0);
  const previewTax = formState.tax_type === "percentage" ? previewSubtotal * ((Number(formState.tax_rate) || 0) / 100) : 0;
  const previewTotal = previewSubtotal + previewTax;

  return (
    <form
      className="form-grid"
      onSubmit={(event) => {
        event.preventDefault();
        mutation.mutate();
      }}
    >
      <section className="form-intro">
        <div>
          <p className="eyebrow">{invoiceId ? "Edit invoice" : "Create invoice"}</p>
          <h2 className="section-title">{invoiceId ? "Refine the invoice before sending" : "Compose a clear client-ready invoice"}</h2>
          <p className="subtle-copy">
            Totals are still calculated server-side, but this layout gives you a quick working estimate while you draft.
          </p>
        </div>
        <aside className="card preview-card">
          <div className="preview-row">
            <span>Line items</span>
            <strong>{formState.line_items.length}</strong>
          </div>
          <div className="preview-row">
            <span>Subtotal</span>
            <strong>
              {formState.currency} {previewSubtotal.toFixed(2)}
            </strong>
          </div>
          <div className="preview-row">
            <span>Estimated tax</span>
            <strong>
              {formState.currency} {previewTax.toFixed(2)}
            </strong>
          </div>
          <div className="preview-row preview-total">
            <span>Estimated total</span>
            <strong>
              {formState.currency} {previewTotal.toFixed(2)}
            </strong>
          </div>
        </aside>
      </section>

      <section className="card form-section">
        <div className="section-heading">
          <div>
            <p className="eyebrow">Invoice</p>
            <h3 className="section-title">Core details</h3>
          </div>
        </div>
        <div className="field-grid">
          <label>
            <span className="field-label">Invoice number</span>
            <input
              className="input"
              value={formState.invoice_number}
              onChange={(event) => setFormState((current) => ({ ...current, invoice_number: event.target.value }))}
              required
            />
          </label>
          <label>
            <span className="field-label">Issue date</span>
            <input
              className="input"
              type="date"
              value={formState.issue_date}
              onChange={(event) => setFormState((current) => ({ ...current, issue_date: event.target.value }))}
              required
            />
          </label>
          <label>
            <span className="field-label">Due date</span>
            <input
              className="input"
              type="date"
              value={formState.due_date}
              onChange={(event) => setFormState((current) => ({ ...current, due_date: event.target.value }))}
              required
            />
          </label>
          <label>
            <span className="field-label">Status</span>
            <select
              className="input"
              value={formState.status}
              onChange={(event) => setFormState((current) => ({ ...current, status: event.target.value as InvoiceStatus }))}
            >
              {["draft", "sent", "paid", "overdue", "cancelled"].map((status) => (
                <option key={status} value={status}>
                  {status}
                </option>
              ))}
            </select>
          </label>
        </div>
      </section>

      <section className="card form-section">
        <div className="section-heading">
          <div>
            <p className="eyebrow">Pricing</p>
            <h3 className="section-title">Set the billing currency and tax rules</h3>
            <p className="subtle-copy section-copy">
              Keep invoices in either rand or dollars and decide whether tax should be added before the final total is calculated.
            </p>
          </div>
        </div>
        <div className="field-grid">
          <label>
            <span className="field-label">Currency</span>
            <select
              className="input"
              value={formState.currency}
              onChange={(event) =>
                setFormState((current) => ({ ...current, currency: event.target.value as CurrencyCode }))
              }
              required
            >
              {currencyOptions.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>
          <label>
            <span className="field-label">Tax type</span>
            <select
              className="input"
              value={formState.tax_type}
              onChange={(event) => setFormState((current) => ({ ...current, tax_type: event.target.value as TaxType }))}
            >
              <option value="none">No tax</option>
              <option value="percentage">Percentage</option>
            </select>
          </label>
          <label>
            <span className="field-label">Tax rate</span>
            <input
              className="input"
              type="number"
              min="0"
              step="0.01"
              value={formState.tax_rate}
              onChange={(event) => setFormState((current) => ({ ...current, tax_rate: event.target.value }))}
              disabled={formState.tax_type === "none"}
            />
          </label>
        </div>
      </section>

      <section className="card form-section">
        <div className="section-heading">
          <div>
            <p className="eyebrow">Payment page</p>
            <h3 className="section-title">Public EFT details</h3>
            <p className="subtle-copy section-copy">
              Choose a saved banking profile or enter manual one-off EFT details. The invoice stores its own snapshot, so future profile edits do not change past invoices.
            </p>
          </div>
          <Link className="button button-ghost compact-link-button" href="/settings/banking-details">
            Manage banking profiles
          </Link>
        </div>
        <div className="field-grid">
          <label className="toggle-field field-span">
            <span className="field-label">Enable public payment page</span>
            <input
              checked={formState.payment_page_enabled}
              onChange={(event) => setFormState((current) => ({ ...current, payment_page_enabled: event.target.checked }))}
              type="checkbox"
            />
          </label>
          {formState.payment_page_enabled ? (
            <>
              <div className="field-span segmented-field">
                <span className="field-label">EFT source</span>
                <div className="segmented-control">
                  <button
                    className={`button button-ghost segmented-control-option${eftState.mode === "saved_profile" ? " is-active" : ""}`}
                    onClick={() => {
                      if (selectedBankingProfile) {
                        updateEftFromProfile(selectedBankingProfile);
                        return;
                      }
                      selectDefaultProfile();
                    }}
                    type="button"
                  >
                    Use saved banking details
                  </button>
                  <button
                    className={`button button-ghost segmented-control-option${eftState.mode === "manual" ? " is-active" : ""}`}
                    onClick={() => setEftState((current) => ({ ...emptyEftState(), mode: "manual", payment_reference: current.payment_reference }))}
                    type="button"
                  >
                    Enter manually for this invoice
                  </button>
                </div>
              </div>

              {eftState.mode === "saved_profile" ? (
                <>
                  <label>
                    <span className="field-label">Saved banking profile</span>
                    <select
                      className="input"
                      value={eftState.banking_profile_id}
                      onChange={(event) => {
                        const profile = bankingProfilesQuery.data?.find(
                          (item) => String(item.id) === event.target.value,
                        );
                        if (profile) {
                          updateEftFromProfile(profile);
                        } else {
                          setEftState((current) => ({ ...current, banking_profile_id: "" }));
                        }
                      }}
                    >
                      <option value="">Select a banking profile</option>
                      {bankingProfilesQuery.data?.map((profile) => (
                        <option key={profile.id} value={profile.id}>
                          {profile.profile_name} · {profile.bank_name}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label>
                    <span className="field-label">Payment reference</span>
                    <input
                      className="input"
                      placeholder="Defaults to invoice number"
                      value={eftState.payment_reference}
                      onChange={(event) => setEftState((current) => ({ ...current, payment_reference: event.target.value }))}
                    />
                  </label>
                  <div className="field-span payment-source-preview">
                    <span className="field-label">Selected banking details</span>
                    <div className="recurring-schedule-preview-card">
                      <p className="recurring-schedule-preview-value">
                        {selectedBankingProfile
                          ? `${selectedBankingProfile.account_holder_name} · ${selectedBankingProfile.bank_name}`
                          : eftState.account_holder_name && eftState.bank_name
                            ? `${eftState.account_holder_name} · ${eftState.bank_name}`
                            : "Select a saved banking profile to attach to this invoice."}
                      </p>
                      <p className="subtle-copy">
                        The current profile values are copied onto the invoice when you save, so historical invoices do not change if you edit the reusable profile later.
                      </p>
                    </div>
                  </div>
                </>
              ) : null}

              {eftState.mode === "manual" ? (
                <>
                  <label>
                    <span className="field-label">Profile name</span>
                    <input
                      className="input"
                      value={eftState.profile_name}
                      onChange={(event) => setEftState((current) => ({ ...current, profile_name: event.target.value }))}
                      placeholder="Manual one-off account"
                    />
                  </label>
                  <label>
                    <span className="field-label">Account holder</span>
                    <input
                      className="input"
                      value={eftState.account_holder_name}
                      onChange={(event) =>
                        setEftState((current) => ({ ...current, account_holder_name: event.target.value }))
                      }
                    />
                  </label>
                  <label>
                    <span className="field-label">Bank name</span>
                    <select
                      className="input"
                      value={eftState.bank_name}
                      onChange={(event) => setEftState((current) => ({ ...current, bank_name: event.target.value }))}
                    >
                      <option value="">Select a bank</option>
                      {getBankNameOptions(eftState.bank_name).map((bankName) => (
                        <option key={bankName} value={bankName}>
                          {bankName}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label>
                    <span className="field-label">Account number</span>
                    <input
                      className="input"
                      value={eftState.account_number}
                      onChange={(event) =>
                        setEftState((current) => ({ ...current, account_number: event.target.value }))
                      }
                    />
                  </label>
                  <label>
                    <span className="field-label">Account type</span>
                    <input
                      className="input"
                      value={eftState.account_type}
                      onChange={(event) => setEftState((current) => ({ ...current, account_type: event.target.value }))}
                    />
                  </label>
                  <label>
                    <span className="field-label">Branch code</span>
                    <input
                      className="input"
                      value={eftState.branch_code}
                      onChange={(event) => setEftState((current) => ({ ...current, branch_code: event.target.value }))}
                    />
                  </label>
                  <label>
                    <span className="field-label">Payment reference</span>
                    <input
                      className="input"
                      placeholder="Defaults to invoice number"
                      value={eftState.payment_reference}
                      onChange={(event) => setEftState((current) => ({ ...current, payment_reference: event.target.value }))}
                    />
                  </label>
                </>
              ) : null}
            </>
          ) : (
            <div className="field-span recurring-schedule-preview">
              <span className="field-label">Payment page status</span>
              <div className="recurring-schedule-preview-card">
                <p className="recurring-schedule-preview-value">Public EFT payment page is currently disabled.</p>
                <p className="subtle-copy">
                  Turn it on when you want to attach banking details to this invoice and share the payment link.
                </p>
              </div>
            </div>
          )}
        </div>
        {eftError ? <p className="form-error">{eftError}</p> : null}
      </section>

      <section className="card form-section">
        <div className="section-heading">
          <div>
            <p className="eyebrow">Client</p>
            <h3 className="section-title">Billing contact</h3>
          </div>
        </div>
        <div className="field-grid">
          <label>
            <span className="field-label">Name</span>
            <input
              className="input"
              value={formState.client.name}
              onChange={(event) =>
                setFormState((current) => ({ ...current, client: { ...current.client, name: event.target.value } }))
              }
              required
            />
          </label>
          <label>
            <span className="field-label">Email</span>
            <input
              className="input"
              type="email"
              value={formState.client.email}
              onChange={(event) =>
                setFormState((current) => ({ ...current, client: { ...current.client, email: event.target.value } }))
              }
              required
            />
          </label>
          <label>
            <span className="field-label">Phone number</span>
            <input
              className="input"
              value={formState.client.phone_number}
              onChange={(event) =>
                setFormState((current) => ({
                  ...current,
                  client: { ...current.client, phone_number: event.target.value },
                }))
              }
              placeholder="+27123456789"
            />
          </label>
          <label className="field-span">
            <span className="field-label">Address</span>
            <textarea
              className="input textarea"
              value={formState.client.address}
              onChange={(event) =>
                setFormState((current) => ({ ...current, client: { ...current.client, address: event.target.value } }))
              }
              rows={4}
            />
          </label>
        </div>
      </section>

      <section className="card form-section">
        <div className="section-heading">
          <div>
            <p className="eyebrow">Line items</p>
            <h3 className="section-title">What you are billing for</h3>
            <p className="subtle-copy section-copy">
              Enter the quantity and the price for one unit. If your device uses comma decimals, `1,00` means `1.00`.
            </p>
          </div>
          <button
            className="button button-ghost"
            type="button"
            onClick={() =>
                setFormState((current) => ({ ...current, line_items: [...current.line_items, emptyItem()] }))
            }
          >
            Add item
          </button>
        </div>
        <div className="line-item-headings" aria-hidden="true">
          <span>Description</span>
          <span>Quantity</span>
          <span>Unit price</span>
          <span>Line total</span>
          <span />
        </div>
        <div className="line-item-list">
          {formState.line_items.map((item, index) => {
            const quantity = Number(item.quantity) || 0;
            const unitPrice = Number(item.unit_price) || 0;
            const lineTotal = quantity * unitPrice;

            return (
              <div className="line-item-row" key={`${index}-${item.description}`}>
                <label className="line-item-field line-item-description">
                  <span className="field-label line-item-mobile-label">Description</span>
                  <input
                    className="input"
                    placeholder="Brand refresh"
                    value={item.description}
                    onChange={(event) => updateItem(index, { description: event.target.value })}
                    required
                  />
                </label>
                <label className="line-item-field">
                  <span className="field-label line-item-mobile-label">Quantity</span>
                  <input
                    className="input"
                    placeholder="1"
                    min="0"
                    step="1"
                    type="number"
                    inputMode="numeric"
                    value={item.quantity}
                    onChange={(event) => updateItem(index, { quantity: event.target.value })}
                    aria-label={`Quantity for line item ${index + 1}`}
                    required
                  />
                </label>
                <label className="line-item-field">
                  <span className="field-label line-item-mobile-label">Unit price</span>
                  <input
                    className="input"
                    placeholder="800.00"
                    min="0"
                    step="0.01"
                    type="number"
                    inputMode="decimal"
                    value={item.unit_price}
                    onChange={(event) => updateItem(index, { unit_price: event.target.value })}
                    aria-label={`Unit price for line item ${index + 1}`}
                    required
                  />
                </label>
                <div className="line-total-card" aria-live="polite">
                  <span className="field-label line-item-mobile-label">Line total</span>
                  <strong>
                    {formState.currency} {lineTotal.toFixed(2)}
                  </strong>
                </div>
                <button
                  className="button button-danger"
                  type="button"
                  onClick={() =>
                    setFormState((current) => {
                      const nextItems = current.line_items.filter((_, itemIndex) => itemIndex !== index);
                      return {
                        ...current,
                        line_items: nextItems.length ? nextItems : [emptyItem()],
                      };
                    })
                  }
                >
                  Remove
                </button>
              </div>
            );
          })}
        </div>
      </section>

      <section className="card form-section">
        <div className="section-heading">
          <div>
            <p className="eyebrow">Notes</p>
            <h3 className="section-title">Client-facing message</h3>
          </div>
        </div>
        <textarea
          className="input textarea"
          rows={5}
          value={formState.notes}
          onChange={(event) => setFormState((current) => ({ ...current, notes: event.target.value }))}
        />
      </section>

      <div className="form-actions">
        <button className="button button-large" disabled={mutation.isPending} type="submit">
          {mutation.isPending ? "Saving..." : invoiceId ? "Update invoice" : "Create invoice"}
        </button>
        {mutation.isError ? <span className="form-error">{getErrorMessage(mutation.error)}</span> : null}
      </div>
    </form>
  );
}
