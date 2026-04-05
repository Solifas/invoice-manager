"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { createInvoice, fetchInvoice, getErrorMessage, updateInvoice } from "@/lib/api";
import { Invoice, InvoiceLineItem, InvoiceStatus, TaxType } from "@/lib/types";

const emptyItem = (): InvoiceLineItem => ({
  description: "",
  quantity: "1",
  unit_price: "0.00",
});

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
    eft_account_holder_name: invoice.eft_account_holder_name ?? "",
    eft_bank_name: invoice.eft_bank_name ?? "",
    eft_account_number: invoice.eft_account_number ?? "",
    eft_account_type: invoice.eft_account_type ?? "",
    eft_branch_code: invoice.eft_branch_code ?? "",
    payment_reference: invoice.payment_reference ?? "",
    line_items: (invoice.line_items ?? []).map((item) => ({
      description: item.description,
      quantity: item.quantity,
      unit_price: item.unit_price,
    })),
  };
}

export function InvoiceForm({ invoiceId }: { invoiceId?: string }) {
  const router = useRouter();
  const [formState, setFormState] = useState<Invoice>({
    id: 0,
    invoice_number: "",
    client: { name: "", email: "", address: "", phone_number: "" },
    issue_date: "",
    due_date: "",
    status: "draft",
    notes: "",
    currency: "USD",
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

  useEffect(() => {
    if (invoiceQuery.data) {
      setFormState(invoiceQuery.data);
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

  const mutation = useMutation({
    mutationFn: async () => {
      const payload = invoiceToPayload(formState);
      return invoiceId ? updateInvoice(invoiceId, payload) : createInvoice(payload);
    },
    onSuccess: (invoice) => {
      router.push(`/invoices/${invoice.id}`);
    },
  });

  const updateItem = (index: number, next: Partial<InvoiceLineItem>) => {
    setFormState((current) => ({
      ...current,
      line_items: current.line_items.map((item, itemIndex) =>
        itemIndex === index ? { ...item, ...next } : item,
      ),
    }));
  };

  if (invoiceQuery.isLoading) {
    return <div className="card state-card">Loading invoice...</div>;
  }

  if (invoiceQuery.isError) {
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
            <span className="field-label">Currency</span>
            <input
              className="input"
              value={formState.currency}
              onChange={(event) => setFormState((current) => ({ ...current, currency: event.target.value }))}
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
              Enable a shareable public payment page for this invoice and control exactly what banking details are shown.
            </p>
          </div>
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
          <label>
            <span className="field-label">Account holder</span>
            <input
              className="input"
              value={formState.eft_account_holder_name}
              onChange={(event) =>
                setFormState((current) => ({ ...current, eft_account_holder_name: event.target.value }))
              }
              required={formState.payment_page_enabled}
            />
          </label>
          <label>
            <span className="field-label">Bank name</span>
            <input
              className="input"
              value={formState.eft_bank_name}
              onChange={(event) => setFormState((current) => ({ ...current, eft_bank_name: event.target.value }))}
              required={formState.payment_page_enabled}
            />
          </label>
          <label>
            <span className="field-label">Account number</span>
            <input
              className="input"
              value={formState.eft_account_number}
              onChange={(event) => setFormState((current) => ({ ...current, eft_account_number: event.target.value }))}
              required={formState.payment_page_enabled}
            />
          </label>
          <label>
            <span className="field-label">Account type</span>
            <input
              className="input"
              value={formState.eft_account_type}
              onChange={(event) => setFormState((current) => ({ ...current, eft_account_type: event.target.value }))}
            />
          </label>
          <label>
            <span className="field-label">Branch code</span>
            <input
              className="input"
              value={formState.eft_branch_code}
              onChange={(event) => setFormState((current) => ({ ...current, eft_branch_code: event.target.value }))}
            />
          </label>
          <label>
            <span className="field-label">Payment reference</span>
            <input
              className="input"
              placeholder="Defaults to invoice number"
              value={formState.payment_reference}
              onChange={(event) => setFormState((current) => ({ ...current, payment_reference: event.target.value }))}
            />
          </label>
        </div>
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
