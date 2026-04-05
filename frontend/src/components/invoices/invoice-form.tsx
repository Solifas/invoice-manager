"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { createInvoice, fetchInvoice, updateInvoice } from "@/lib/api";
import { Invoice, InvoiceLineItem, InvoiceStatus, TaxType } from "@/lib/types";

const emptyItem = (): InvoiceLineItem => ({
  description: "",
  quantity: "1.00",
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
    line_items: invoice.line_items.map((item) => ({
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
    client: { name: "", email: "", address: "" },
    issue_date: new Date().toISOString().slice(0, 10),
    due_date: new Date().toISOString().slice(0, 10),
    status: "draft",
    notes: "",
    currency: "USD",
    tax_type: "none",
    tax_rate: "0.00",
    subtotal: "0.00",
    tax_amount: "0.00",
    total_amount: "0.00",
    line_items: [emptyItem()],
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
        <div className="line-item-list">
          {formState.line_items.map((item, index) => (
            <div className="line-item-row" key={`${index}-${item.description}`}>
              <input
                className="input line-description"
                placeholder="Description"
                value={item.description}
                onChange={(event) => updateItem(index, { description: event.target.value })}
                required
              />
              <input
                className="input"
                placeholder="Qty"
                min="0"
                step="0.01"
                type="number"
                value={item.quantity}
                onChange={(event) => updateItem(index, { quantity: event.target.value })}
                required
              />
              <input
                className="input"
                placeholder="Unit price"
                min="0"
                step="0.01"
                type="number"
                value={item.unit_price}
                onChange={(event) => updateItem(index, { unit_price: event.target.value })}
                required
              />
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
          ))}
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
        {mutation.isError ? <span className="form-error">Save failed. Check validation and try again.</span> : null}
      </div>
    </form>
  );
}
