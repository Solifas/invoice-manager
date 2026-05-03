"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import {
  createBankingProfile,
  deleteBankingProfile,
  fetchBankingProfiles,
  getErrorMessage,
  setDefaultBankingProfile,
  updateBankingProfile,
} from "@/lib/api";
import { getBankNameOptions } from "@/lib/banking";
import { BankingProfile, BankingProfileInput } from "@/lib/types";

const emptyProfileForm: BankingProfileInput = {
  profile_name: "",
  account_holder_name: "",
  bank_name: "",
  account_number: "",
  account_type: "",
  branch_code: "",
  default_payment_reference: "",
};

function normalizeProfiles(current: BankingProfile[] | { results?: BankingProfile[] } | undefined) {
  if (Array.isArray(current)) {
    return current;
  }
  if (current && Array.isArray(current.results)) {
    return current.results;
  }
  return [];
}

export function BankingDetailsScreen() {
  const queryClient = useQueryClient();
  const [editingId, setEditingId] = useState<string | null>(null);
  const [formState, setFormState] = useState<BankingProfileInput>(emptyProfileForm);
  const [successMessage, setSuccessMessage] = useState("");

  const profilesQuery = useQuery({
    queryKey: ["banking-profiles"],
    queryFn: fetchBankingProfiles,
  });

  const saveMutation = useMutation({
    mutationFn: async () => {
      if (editingId) {
        return updateBankingProfile(editingId, formState);
      }
      return createBankingProfile({ ...formState, is_default: profilesQuery.data?.length === 0 });
    },
    onSuccess: async (savedProfile) => {
      queryClient.setQueryData<BankingProfile[] | { results?: BankingProfile[] }>(["banking-profiles"], (current) => {
        const profiles = normalizeProfiles(current);
        if (editingId) {
          return profiles.map((profile) => (profile.id === savedProfile.id ? savedProfile : profile));
        }
        return [...profiles, savedProfile].sort((left, right) => left.profile_name.localeCompare(right.profile_name));
      });
      setEditingId(null);
      setFormState(emptyProfileForm);
      setSuccessMessage(editingId ? "Banking profile updated." : "Banking profile saved.");
      await queryClient.invalidateQueries({ queryKey: ["banking-profiles"] });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => deleteBankingProfile(id),
    onSuccess: async (_, id) => {
      queryClient.setQueryData<BankingProfile[] | { results?: BankingProfile[] }>(["banking-profiles"], (current) =>
        normalizeProfiles(current).filter((profile) => String(profile.id) !== id),
      );
      setSuccessMessage("Banking profile removed.");
      await queryClient.invalidateQueries({ queryKey: ["banking-profiles"] });
    },
  });

  const defaultMutation = useMutation({
    mutationFn: (id: string) => setDefaultBankingProfile(id),
    onSuccess: async (defaultProfile) => {
      queryClient.setQueryData<BankingProfile[] | { results?: BankingProfile[] }>(["banking-profiles"], (current) =>
        normalizeProfiles(current).map((profile) => ({
          ...profile,
          is_default: profile.id === defaultProfile.id,
        })),
      );
      setSuccessMessage("Default banking profile updated.");
      await queryClient.invalidateQueries({ queryKey: ["banking-profiles"] });
    },
  });

  return (
    <div className="dashboard-stack">
      <section className="hero-panel dashboard-hero dashboard-hero-compact">
        <div>
          <p className="eyebrow">Settings</p>
          <h2 className="section-title">Reusable banking profiles</h2>
          <p className="subtle-copy">
            Create reusable EFT profiles for the accounts you want to expose on invoice payment pages. Each invoice still stores its own immutable snapshot.
          </p>
        </div>
      </section>

      <section className="card panel">
        <div className="panel-heading">
          <div>
            <p className="eyebrow">Saved profiles</p>
            <h3 className="section-title">Banking details library</h3>
          </div>
        </div>
        {successMessage ? <div className="state-card success">{successMessage}</div> : null}

        {profilesQuery.isLoading ? (
          <div className="state-card">Loading banking profiles...</div>
        ) : profilesQuery.isError ? (
          <div className="state-card error">Unable to load banking profiles.</div>
        ) : profilesQuery.data?.length ? (
          <div className="dashboard-recurring-list">
            {profilesQuery.data.map((profile) => (
              <article className="recurring-item-card dashboard-recurring-item" key={profile.id}>
                <div className="recurring-item-main">
                  <div className="invoice-link">
                    <span>{profile.profile_name}</span>
                    <small>
                      {profile.account_holder_name} · {profile.bank_name}
                    </small>
                  </div>
                  <div className="recurring-item-meta">
                    <div>
                      <span className="field-label">Account number</span>
                      <p>{profile.account_number}</p>
                    </div>
                    <div>
                      <span className="field-label">Branch code</span>
                      <p>{profile.branch_code || "Not provided"}</p>
                    </div>
                    <div>
                      <span className="field-label">Default</span>
                      <span className={`schedule-status-badge ${profile.is_default ? "schedule-status-active" : "schedule-status-paused"}`}>
                        {profile.is_default ? "default" : "secondary"}
                      </span>
                    </div>
                  </div>
                </div>
                <div className="recurring-item-actions">
                  <button
                    className="button button-ghost"
                    onClick={() => {
                      setSuccessMessage("");
                      setEditingId(String(profile.id));
                      setFormState({
                        profile_name: profile.profile_name,
                        account_holder_name: profile.account_holder_name,
                        bank_name: profile.bank_name,
                        account_number: profile.account_number,
                        account_type: profile.account_type,
                        branch_code: profile.branch_code,
                        default_payment_reference: profile.default_payment_reference,
                      });
                    }}
                    type="button"
                  >
                    Edit
                  </button>
                  {!profile.is_default ? (
                    <button
                      className="button button-secondary"
                      onClick={() => defaultMutation.mutate(String(profile.id))}
                      type="button"
                    >
                      Set default
                    </button>
                  ) : null}
                  <button
                    className="button button-danger"
                    onClick={() => deleteMutation.mutate(String(profile.id))}
                    type="button"
                  >
                    Remove
                  </button>
                </div>
              </article>
            ))}
          </div>
        ) : (
          <div className="state-card">No banking profiles saved yet.</div>
        )}
      </section>

      <section className="card form-section">
        <div className="section-heading">
          <div>
            <p className="eyebrow">{editingId ? "Edit profile" : "New profile"}</p>
            <h3 className="section-title">{editingId ? "Update banking details" : "Add banking details"}</h3>
          </div>
          {editingId ? (
            <button
              className="button button-ghost"
              onClick={() => {
                setSuccessMessage("");
                setEditingId(null);
                setFormState(emptyProfileForm);
              }}
              type="button"
            >
              Cancel edit
            </button>
          ) : null}
        </div>

        <form
          className="field-grid"
          onSubmit={(event) => {
            event.preventDefault();
            setSuccessMessage("");
            saveMutation.mutate();
          }}
        >
          <label>
            <span className="field-label">Profile name</span>
            <input className="input" value={formState.profile_name} onChange={(event) => setFormState((current) => ({ ...current, profile_name: event.target.value }))} required />
          </label>
          <label>
            <span className="field-label">Account holder</span>
            <input className="input" value={formState.account_holder_name} onChange={(event) => setFormState((current) => ({ ...current, account_holder_name: event.target.value }))} required />
          </label>
          <label>
            <span className="field-label">Bank name</span>
            <select
              className="input"
              value={formState.bank_name}
              onChange={(event) => setFormState((current) => ({ ...current, bank_name: event.target.value }))}
              required
            >
              <option value="">Select a bank</option>
              {getBankNameOptions(formState.bank_name).map((bankName) => (
                <option key={bankName} value={bankName}>
                  {bankName}
                </option>
              ))}
            </select>
          </label>
          <label>
            <span className="field-label">Account number</span>
            <input className="input" value={formState.account_number} onChange={(event) => setFormState((current) => ({ ...current, account_number: event.target.value }))} required />
          </label>
          <label>
            <span className="field-label">Account type</span>
            <input className="input" value={formState.account_type || ""} onChange={(event) => setFormState((current) => ({ ...current, account_type: event.target.value }))} />
          </label>
          <label>
            <span className="field-label">Branch code</span>
            <input className="input" value={formState.branch_code || ""} onChange={(event) => setFormState((current) => ({ ...current, branch_code: event.target.value }))} />
          </label>
          <label className="field-span">
            <span className="field-label">Default payment reference</span>
            <input
              className="input"
              placeholder="Defaults to invoice number if left blank"
              value={formState.default_payment_reference || ""}
              onChange={(event) => setFormState((current) => ({ ...current, default_payment_reference: event.target.value }))}
            />
          </label>
          <div className="field-span form-actions">
            <button className="button button-large" disabled={saveMutation.isPending} type="submit">
              {saveMutation.isPending ? "Saving..." : editingId ? "Update profile" : "Save profile"}
            </button>
            {saveMutation.isError ? <span className="form-error">{getErrorMessage(saveMutation.error)}</span> : null}
            {defaultMutation.isError ? <span className="form-error">{getErrorMessage(defaultMutation.error)}</span> : null}
            {deleteMutation.isError ? <span className="form-error">{getErrorMessage(deleteMutation.error)}</span> : null}
          </div>
        </form>
      </section>
    </div>
  );
}
