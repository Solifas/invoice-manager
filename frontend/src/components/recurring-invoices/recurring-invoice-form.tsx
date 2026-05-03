"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import {
  createContractor,
  createRecurringInvoice,
  fetchClients,
  fetchContractors,
  fetchCurrencies,
  fetchRecurringInvoice,
  getErrorMessage,
  updateContractor,
  updateRecurringInvoice,
} from "@/lib/api";
import { SearchableCurrencySelect } from "@/components/shared/searchable-currency-select";
import { getStoredCurrencyPreference, storeCurrencyPreference } from "@/lib/currency-preferences";
import {
  ContractorInput,
  RecurringInvoice,
  RecurringInvoiceLineItemTemplate,
  RecurringInvoiceStatus,
  TaxType,
} from "@/lib/types";

const emptyItem = (): RecurringInvoiceLineItemTemplate => ({
  description: "",
  quantity: "1",
  unit_price: "0.00",
});

const emptyContractor = (): ContractorInput => ({
  name: "",
  email: "",
  contact_number: "",
  address: "",
});

function getClientContactLabel(client: { name: string; email: string; phone_number: string }) {
  if (client.phone_number) {
    return `${client.email} · ${client.phone_number}`;
  }
  return client.email;
}

const todayDateString = () => new Date().toISOString().slice(0, 10);

function addMonthsToIsoDate(value: string, months: number) {
  const [year, month, day] = value.split("-").map(Number);
  const monthIndex = month - 1 + months;
  const nextYear = year + Math.floor(monthIndex / 12);
  const nextMonth = (monthIndex % 12) + 1;
  const lastDay = new Date(Date.UTC(nextYear, nextMonth, 0)).getUTCDate();
  const nextDay = Math.min(day, lastDay);
  return new Date(Date.UTC(nextYear, nextMonth - 1, nextDay)).toISOString().slice(0, 10);
}

function getRecurringNextRunPreview(startDate: string, frequency: RecurringInvoice["frequency"]) {
  if (!startDate) {
    return "";
  }

  const referenceDate = todayDateString();
  let nextRunDate = startDate;

  while (nextRunDate < referenceDate) {
    if (frequency === "weekly") {
      const current = new Date(`${nextRunDate}T00:00:00Z`);
      current.setUTCDate(current.getUTCDate() + 7);
      nextRunDate = current.toISOString().slice(0, 10);
      continue;
    }

    if (frequency === "monthly") {
      nextRunDate = addMonthsToIsoDate(nextRunDate, 1);
      continue;
    }

    nextRunDate = addMonthsToIsoDate(nextRunDate, 3);
  }

  return nextRunDate;
}

const defaultState: RecurringInvoice = {
  id: 0,
  client_id: 0,
  contractor_id: null,
  template_name: "",
  frequency: "monthly",
  start_date: "",
  end_date: null,
  next_run_date: "",
  status: "active",
  currency: "ZAR",
  payment_terms_days: 14,
  tax_type: "none",
  tax_rate: "0.00",
  notes: "",
  line_items_template: [emptyItem()],
};

function toPayload(recurringInvoice: RecurringInvoice) {
  return {
    template_name: recurringInvoice.template_name,
    client_id: recurringInvoice.client_id,
    contractor_id: recurringInvoice.contractor_id || null,
    frequency: recurringInvoice.frequency,
    start_date: recurringInvoice.start_date,
    end_date: recurringInvoice.end_date || null,
    status: recurringInvoice.status,
    currency: recurringInvoice.currency,
    payment_terms_days: recurringInvoice.payment_terms_days,
    tax_type: recurringInvoice.tax_type,
    tax_rate: recurringInvoice.tax_rate,
    notes: recurringInvoice.notes,
    line_items_template: recurringInvoice.line_items_template,
  };
}

export function RecurringInvoiceForm({ recurringInvoiceId }: { recurringInvoiceId?: string }) {
  const router = useRouter();
  const queryClient = useQueryClient();
  const [formState, setFormState] = useState<RecurringInvoice>(defaultState);
  const [clientContactInput, setClientContactInput] = useState("");
  const [clientInputError, setClientInputError] = useState("");
  const [contractorDialogMode, setContractorDialogMode] = useState<"create" | "edit" | null>(null);
  const [contractorForm, setContractorForm] = useState<ContractorInput>(emptyContractor);

  const clientsQuery = useQuery({
    queryKey: ["clients"],
    queryFn: fetchClients,
  });
  const contractorsQuery = useQuery({
    queryKey: ["contractors"],
    queryFn: fetchContractors,
  });
  const recurringQuery = useQuery({
    queryKey: ["recurring-invoice", recurringInvoiceId],
    queryFn: () => fetchRecurringInvoice(recurringInvoiceId!),
    enabled: Boolean(recurringInvoiceId),
  });
  const currenciesQuery = useQuery({
    queryKey: ["currencies"],
    queryFn: fetchCurrencies,
  });

  useEffect(() => {
    if (recurringQuery.data) {
      setFormState({
        ...recurringQuery.data,
        client_id: recurringQuery.data.client?.id || recurringQuery.data.client_id,
        contractor_id: recurringQuery.data.contractor?.id || recurringQuery.data.contractor_id || null,
      });
      if (recurringQuery.data.client) {
        setClientContactInput(getClientContactLabel(recurringQuery.data.client));
      }
    }
  }, [recurringQuery.data]);

  useEffect(() => {
    if (recurringInvoiceId) {
      return;
    }
    setFormState((current) => {
      if (current.start_date && current.next_run_date) {
        return current;
      }
      const today = new Date().toISOString().slice(0, 10);
      return {
        ...current,
        start_date: current.start_date || today,
        next_run_date: current.next_run_date || today,
      };
    });
  }, [recurringInvoiceId]);

  useEffect(() => {
    if (recurringInvoiceId || !currenciesQuery.data?.length) {
      return;
    }

    const preferredCurrency = getStoredCurrencyPreference();
    if (!preferredCurrency) {
      return;
    }

    const supported = currenciesQuery.data.some((option) => option.code === preferredCurrency);
    if (!supported) {
      return;
    }

    setFormState((current) => {
      if (current.currency === preferredCurrency) {
        return current;
      }

      return { ...current, currency: preferredCurrency };
    });
  }, [currenciesQuery.data, recurringInvoiceId]);

  useEffect(() => {
    if (recurringInvoiceId || !clientsQuery.data?.length || formState.client_id) {
      return;
    }
    const defaultClient = clientsQuery.data[0];
    setFormState((current) => ({
      ...current,
      client_id: current.client_id || defaultClient.id || 0,
    }));
    setClientContactInput(getClientContactLabel(defaultClient));
  }, [clientsQuery.data, formState.client_id, recurringInvoiceId]);

  useEffect(() => {
    if (!clientsQuery.data?.length) {
      return;
    }
    const matchedClient = clientsQuery.data.find((client) => client.id === formState.client_id);
    if (matchedClient) {
      setClientContactInput((current) => current || getClientContactLabel(matchedClient));
    }
  }, [clientsQuery.data, formState.client_id]);

  const mutation = useMutation({
    mutationFn: () =>
      recurringInvoiceId
        ? updateRecurringInvoice(recurringInvoiceId, toPayload(formState))
        : createRecurringInvoice(toPayload(formState)),
    onSuccess: () => router.push("/recurring-invoices"),
  });

  const contractorMutation = useMutation({
    mutationFn: () => {
      const payload = {
        ...contractorForm,
        name: contractorForm.name.trim(),
        email: contractorForm.email.trim(),
        contact_number: contractorForm.contact_number.trim(),
        address: contractorForm.address.trim(),
      };

      if (contractorDialogMode === "edit" && formState.contractor_id) {
        return updateContractor(formState.contractor_id, payload);
      }

      return createContractor(payload);
    },
    onSuccess: async (contractor) => {
      await queryClient.invalidateQueries({ queryKey: ["contractors"] });
      setFormState((current) => ({ ...current, contractor_id: contractor.id }));
      setContractorDialogMode(null);
      setContractorForm(emptyContractor());
    },
  });

  const updateItem = (index: number, next: Partial<RecurringInvoiceLineItemTemplate>) => {
    setFormState((current) => ({
      ...current,
      line_items_template: current.line_items_template.map((item, itemIndex) =>
        itemIndex === index ? { ...item, ...next } : item,
      ),
    }));
  };

  const nextRunPreview = getRecurringNextRunPreview(formState.start_date, formState.frequency);
  const selectedClient = clientsQuery.data?.find((client) => client.id === formState.client_id);
  const selectedContractor = contractorsQuery.data?.find((contractor) => contractor.id === formState.contractor_id);
  const estimatedTemplateTotal = formState.line_items_template.reduce((total, item) => {
    const quantity = Number(item.quantity) || 0;
    const unitPrice = Number(item.unit_price) || 0;
    return total + quantity * unitPrice;
  }, 0);
  const handleCurrencyChange = (code: string) => {
    storeCurrencyPreference(code);
    setFormState((current) => ({ ...current, currency: code }));
  };

  const openCreateContractorDialog = () => {
    setContractorForm(emptyContractor());
    setContractorDialogMode("create");
  };

  const openEditContractorDialog = () => {
    if (!selectedContractor) {
      return;
    }

    setContractorForm({
      name: selectedContractor.name,
      email: selectedContractor.email,
      contact_number: selectedContractor.contact_number,
      address: selectedContractor.address,
    });
    setContractorDialogMode("edit");
  };

  if (recurringQuery.isLoading || clientsQuery.isLoading || contractorsQuery.isLoading || currenciesQuery.isLoading) {
    return <div className="card state-card">Loading recurring invoice...</div>;
  }

  if (recurringQuery.isError || clientsQuery.isError || contractorsQuery.isError || currenciesQuery.isError) {
    return <div className="card state-card error">Unable to load recurring invoice.</div>;
  }

  return (
    <>
      <form
        className="form-grid"
        onSubmit={(event) => {
          event.preventDefault();
          if (!formState.client_id) {
            setClientInputError("Enter a saved client email or phone number.");
            return;
          }
          setClientInputError("");
          mutation.mutate();
        }}
      >
      <section className="form-intro">
        <div>
          <p className="eyebrow">{recurringInvoiceId ? "Edit recurring invoice" : "Create recurring invoice"}</p>
          <h2 className="section-title">Build a recurring schedule that behaves predictably</h2>
          <p className="subtle-copy">
            Recurring templates should define who gets billed, how often invoices are issued, and what each generated invoice contains. Scheduler dates are derived automatically from your start date and frequency.
          </p>
        </div>
        <aside className="card preview-card recurring-preview-card">
          <div className="preview-row">
            <span>Client</span>
            <strong>{selectedClient ? getClientContactLabel(selectedClient) : "Choose a client"}</strong>
          </div>
          <div className="preview-row">
            <span>Contractor</span>
            <strong>{selectedContractor?.name || "No contractor assigned"}</strong>
          </div>
          <div className="preview-row">
            <span>Frequency</span>
            <strong>{formState.frequency}</strong>
          </div>
          <div className="preview-row">
            <span>Next run</span>
            <strong>{formState.status === "cancelled" ? "Stopped" : nextRunPreview || "Choose a start date"}</strong>
          </div>
          <div className="preview-row preview-total">
            <span>Template total</span>
            <strong>
              {formState.currency} {estimatedTemplateTotal.toFixed(2)}
            </strong>
          </div>
          <div className="form-intro-actions">
            <Link className="button button-ghost compact-link-button" href="/recurring-invoices">
              Back to recurring invoices
            </Link>
          </div>
        </aside>
      </section>

      <section className="card form-section">
        <div className="section-heading">
          <div>
            <p className="eyebrow">Template basics</p>
            <h3 className="section-title">Who gets billed and under what template name?</h3>
          </div>
        </div>
        <div className="field-grid">
          <label>
            <span className="field-label">Template name</span>
            <input
              className="input"
              onChange={(event) => setFormState((current) => ({ ...current, template_name: event.target.value }))}
              value={formState.template_name}
            />
          </label>
          <label>
            <span className="field-label">Client</span>
            <input
              className="input"
              list="recurring-client-contact-options"
              onChange={(event) => {
                const nextValue = event.target.value;
                setClientContactInput(nextValue);
                const matchedClient = clientsQuery.data?.find(
                  (client) =>
                    getClientContactLabel(client) === nextValue ||
                    client.email === nextValue ||
                    client.phone_number === nextValue,
                );
                setFormState((current) => ({
                  ...current,
                  client_id: matchedClient?.id || 0,
                }));
                setClientInputError(matchedClient || nextValue === "" ? "" : "Choose a saved client from the suggested contact details.");
              }}
              placeholder="Type client email or phone number"
              required
              value={clientContactInput}
            />
            <datalist id="recurring-client-contact-options">
              {clientsQuery.data?.map((client) => (
                <option key={client.id} value={getClientContactLabel(client)} />
              ))}
            </datalist>
            {clientInputError ? <span className="form-error">{clientInputError}</span> : null}
          </label>
          <div className="field-control-stack">
            <label>
              <span className="field-label">Contractor</span>
              <select
                className="input"
                onChange={(event) =>
                  setFormState((current) => ({
                    ...current,
                    contractor_id: event.target.value ? Number(event.target.value) : null,
                  }))
                }
                value={formState.contractor_id || ""}
              >
                <option value="">No contractor assigned</option>
                {contractorsQuery.data?.map((contractor) => (
                  <option key={contractor.id} value={contractor.id}>
                    {contractor.name}
                  </option>
                ))}
              </select>
            </label>
            <div className="inline-control-row">
              <button className="button button-ghost compact-link-button" onClick={openCreateContractorDialog} type="button">
                Add contractor
              </button>
              <button
                className="button button-ghost compact-link-button"
                disabled={!selectedContractor}
                onClick={openEditContractorDialog}
                type="button"
              >
                Edit selected
              </button>
            </div>
            <p className="field-help">Assign the contractor responsible for this recurring work, or leave it blank.</p>
          </div>
        </div>
      </section>

      <section className="card form-section">
        <div className="section-heading">
          <div>
            <p className="eyebrow">Schedule</p>
            <h3 className="section-title">Set the cadence and let the system calculate the next run</h3>
          </div>
        </div>
        <div className="field-grid">
          <label>
            <span className="field-label">Frequency</span>
            <select
              className="input"
              onChange={(event) => setFormState((current) => ({ ...current, frequency: event.target.value as RecurringInvoice["frequency"] }))}
              value={formState.frequency}
            >
              <option value="weekly">Weekly</option>
              <option value="monthly">Monthly</option>
              <option value="quarterly">Quarterly</option>
            </select>
          </label>
          <label>
            <span className="field-label">Start date</span>
            <input
              className="input"
              onChange={(event) => setFormState((current) => ({ ...current, start_date: event.target.value }))}
              type="date"
              value={formState.start_date}
            />
          </label>
          <label>
            <span className="field-label">End date</span>
            <input
              className="input"
              onChange={(event) => setFormState((current) => ({ ...current, end_date: event.target.value || null }))}
              type="date"
              value={formState.end_date || ""}
            />
          </label>
          <label>
            <span className="field-label">Status</span>
            <select
              className="input"
              onChange={(event) => setFormState((current) => ({ ...current, status: event.target.value as RecurringInvoiceStatus }))}
              value={formState.status}
            >
              <option value="active">Active</option>
              <option value="paused">Paused</option>
              <option value="cancelled">Cancelled</option>
            </select>
          </label>
          <div className="field-span recurring-schedule-preview">
            <span className="field-label">Schedule preview</span>
            <div className="recurring-schedule-preview-card">
              <p className="recurring-schedule-preview-value">
                {formState.status === "cancelled"
                  ? "This recurring schedule is stopped."
                  : nextRunPreview
                    ? `Next invoice will generate on ${nextRunPreview}.`
                    : "Select a start date to preview the next invoice date."}
              </p>
              <p className="subtle-copy">
                The backend now calculates `next_run_date` from your chosen start date and frequency, so this field is no longer edited manually.
              </p>
            </div>
          </div>
        </div>
      </section>

      <section className="card form-section">
        <div className="section-heading">
          <div>
            <p className="eyebrow">Pricing</p>
            <h3 className="section-title">Choose the currency, payment terms, and tax behavior</h3>
            <p className="subtle-copy section-copy">
              These defaults flow into each generated invoice, so keep them aligned with how this client is usually billed.
            </p>
          </div>
        </div>
        <div className="field-grid">
          <SearchableCurrencySelect
            label="Currency"
            onChange={handleCurrencyChange}
            options={currenciesQuery.data || []}
            value={formState.currency}
          />
          <label>
            <span className="field-label">Payment terms (days)</span>
            <input
              className="input"
              min="0"
              onChange={(event) => setFormState((current) => ({ ...current, payment_terms_days: Number(event.target.value) }))}
              type="number"
              value={formState.payment_terms_days}
            />
          </label>
          <label>
            <span className="field-label">Tax type</span>
            <select
              className="input"
              onChange={(event) => setFormState((current) => ({ ...current, tax_type: event.target.value as TaxType }))}
              value={formState.tax_type}
            >
              <option value="none">No tax</option>
              <option value="percentage">Percentage</option>
            </select>
          </label>
          <label>
            <span className="field-label">Tax rate</span>
            <input
              className="input"
              min="0"
              onChange={(event) => setFormState((current) => ({ ...current, tax_rate: event.target.value }))}
              step="0.01"
              type="number"
              value={formState.tax_rate}
              disabled={formState.tax_type === "none"}
            />
          </label>
          <label className="field-span">
            <span className="field-label">Notes</span>
            <textarea
              className="input textarea"
              onChange={(event) => setFormState((current) => ({ ...current, notes: event.target.value }))}
              rows={4}
              value={formState.notes}
            />
          </label>
        </div>
      </section>

      <section className="card form-section">
        <div className="section-heading">
          <div>
            <p className="eyebrow">Template line items</p>
            <h3 className="section-title">What should each generated invoice include?</h3>
          </div>
          <button
            className="button button-ghost"
            onClick={() =>
              setFormState((current) => ({
                ...current,
                line_items_template: [...current.line_items_template, emptyItem()],
              }))
            }
            type="button"
          >
            Add item
          </button>
        </div>
        <div className="line-item-headings recurring-line-item-headings" aria-hidden="true">
          <span>Description</span>
          <span>Quantity</span>
          <span>Unit price</span>
          <span>Line total</span>
          <span />
        </div>
        <div className="line-item-list">
          {formState.line_items_template.map((item, index) => (
            <div className="line-item-row recurring-line-item-row" key={`recurring-line-item-${index}`}>
              <label className="line-item-field line-item-description">
                <span className="field-label line-item-mobile-label">Description</span>
                <input
                  className="input"
                  onChange={(event) => updateItem(index, { description: event.target.value })}
                  value={item.description}
                />
              </label>
              <label className="line-item-field">
                <span className="field-label line-item-mobile-label">Quantity</span>
                <input
                  className="input"
                  onChange={(event) => updateItem(index, { quantity: event.target.value })}
                  min="0"
                  step="1"
                  type="number"
                  inputMode="numeric"
                  value={item.quantity}
                />
              </label>
              <label className="line-item-field">
                <span className="field-label line-item-mobile-label">Unit price</span>
                <input
                  className="input"
                  onChange={(event) => updateItem(index, { unit_price: event.target.value })}
                  step="0.01"
                  type="number"
                  value={item.unit_price}
                />
              </label>
              <div className="line-total-card">
                <span className="field-label line-item-mobile-label">Line total</span>
                <strong>
                  {formState.currency} {((Number(item.quantity) || 0) * (Number(item.unit_price) || 0)).toFixed(2)}
                </strong>
              </div>
              <button
                className="button button-danger"
                onClick={() =>
                  setFormState((current) => ({
                    ...current,
                    line_items_template: (() => {
                      const nextItems = current.line_items_template.filter((_, itemIndex) => itemIndex !== index);
                      return nextItems.length ? nextItems : [emptyItem()];
                    })(),
                  }))
                }
                type="button"
              >
                Remove
              </button>
            </div>
          ))}
        </div>
      </section>

      <div className="form-actions">
        <button className="button button-large" disabled={mutation.isPending} type="submit">
          {mutation.isPending ? "Saving..." : recurringInvoiceId ? "Update recurring invoice" : "Create recurring invoice"}
        </button>
        {mutation.isError ? <span className="form-error">{getErrorMessage(mutation.error)}</span> : null}
      </div>

      </form>

      {contractorDialogMode ? (
        <div
          className="modal-backdrop"
          onMouseDown={(event) => {
            if (event.target === event.currentTarget && !contractorMutation.isPending) {
              setContractorDialogMode(null);
            }
          }}
        >
          <section
            aria-labelledby="contractor-dialog-title"
            aria-modal="true"
            className="modal-card contractor-modal-card"
            role="dialog"
          >
            <div className="modal-header">
              <div>
                <p className="eyebrow">Contractor details</p>
                <h3 className="section-title" id="contractor-dialog-title">
                  {contractorDialogMode === "edit" ? "Update contractor" : "Add contractor"}
                </h3>
                <p className="subtle-copy">Saved contractors become available in recurring invoice templates.</p>
              </div>
              <button
                aria-label="Close contractor dialog"
                className="button button-ghost compact-link-button"
                disabled={contractorMutation.isPending}
                onClick={() => setContractorDialogMode(null)}
                type="button"
              >
                Close
              </button>
            </div>

            <div className="field-grid modal-field-grid">
              <label>
                <span className="field-label">Name</span>
                <input
                  className="input"
                  onChange={(event) => setContractorForm((current) => ({ ...current, name: event.target.value }))}
                  placeholder="e.g. Nora Dev"
                  required
                  value={contractorForm.name}
                />
              </label>
              <label>
                <span className="field-label">Email</span>
                <input
                  className="input"
                  onChange={(event) => setContractorForm((current) => ({ ...current, email: event.target.value }))}
                  placeholder="name@example.com"
                  type="email"
                  value={contractorForm.email}
                />
              </label>
              <label>
                <span className="field-label">Phone number</span>
                <input
                  className="input"
                  onChange={(event) =>
                    setContractorForm((current) => ({ ...current, contact_number: event.target.value }))
                  }
                  placeholder="+27..."
                  value={contractorForm.contact_number}
                />
              </label>
              <label className="field-span">
                <span className="field-label">Address</span>
                <textarea
                  className="input textarea"
                  onChange={(event) => setContractorForm((current) => ({ ...current, address: event.target.value }))}
                  placeholder="Street address or billing address"
                  rows={3}
                  value={contractorForm.address}
                />
              </label>
            </div>

            {contractorMutation.isError ? (
              <p className="form-error contractor-modal-error">{getErrorMessage(contractorMutation.error)}</p>
            ) : null}

            <div className="modal-actions">
              <button
                className="button button-ghost"
                disabled={contractorMutation.isPending}
                onClick={() => setContractorDialogMode(null)}
                type="button"
              >
                Cancel
              </button>
              <button
                className="button"
                disabled={contractorMutation.isPending || !contractorForm.name.trim()}
                onClick={() => contractorMutation.mutate()}
                type="button"
              >
                {contractorMutation.isPending ? "Saving..." : "Save contractor"}
              </button>
            </div>
          </section>
        </div>
      ) : null}
    </>
  );
}
