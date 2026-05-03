"use client";

import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { createBusinessProfile, fetchBusinessProfile, getErrorMessage, updateBusinessProfile } from "@/lib/api";
import { BusinessProfileInput, BusinessVerificationStatus } from "@/lib/types";

const emptyBusinessProfile: BusinessProfileInput = {
  business_name: "",
  business_type: "",
  registration_number: "",
  vat_number: "",
  trading_name: "",
  contact_email: "",
  contact_phone_number: "",
  business_address: "",
  verification_status: "not_started",
};

const statusLabels: Record<BusinessVerificationStatus, string> = {
  not_started: "Not started",
  pending: "Pending",
  verified: "Verified",
  rejected: "Rejected",
};

export function BusinessProfileScreen() {
  const queryClient = useQueryClient();
  const [formState, setFormState] = useState<BusinessProfileInput>(emptyBusinessProfile);
  const [successMessage, setSuccessMessage] = useState("");

  const profileQuery = useQuery({
    queryKey: ["business-profile"],
    queryFn: fetchBusinessProfile,
    retry: false,
  });

  useEffect(() => {
    if (profileQuery.data) {
      setFormState({
        business_name: profileQuery.data.business_name,
        business_type: profileQuery.data.business_type,
        registration_number: profileQuery.data.registration_number,
        vat_number: profileQuery.data.vat_number,
        trading_name: profileQuery.data.trading_name,
        contact_email: profileQuery.data.contact_email,
        contact_phone_number: profileQuery.data.contact_phone_number,
        business_address: profileQuery.data.business_address,
        verification_status: profileQuery.data.verification_status,
      });
    }
  }, [profileQuery.data]);

  const saveMutation = useMutation({
    mutationFn: async () => {
      if (profileQuery.data) {
        return updateBusinessProfile(formState);
      }
      return createBusinessProfile(formState);
    },
    onSuccess: async (profile) => {
      queryClient.setQueryData(["business-profile"], profile);
      setSuccessMessage("Business profile saved.");
      await queryClient.invalidateQueries({ queryKey: ["business-profile"] });
    },
  });

  const completeness = profileQuery.data?.completeness_percentage ?? 0;
  const verificationStatus = profileQuery.data?.verification_status ?? formState.verification_status;

  return (
    <div className="dashboard-stack">
      <section className="hero-panel dashboard-hero dashboard-hero-compact">
        <div>
          <p className="eyebrow">Settings</p>
          <h2 className="section-title">Business profile</h2>
          <p className="subtle-copy">
            Add the business details your clients recognise. Verification is not active yet, but this profile will later
            help unlock higher collections limits for South African SMEs.
          </p>
        </div>
      </section>

      <section className="summary-grid">
        <article className="card stat-card">
          <div className="stat-card-header">
            <span>Verification status</span>
            <small>Foundation only, no external KYC connected</small>
          </div>
          <strong>{statusLabels[verificationStatus]}</strong>
        </article>
        <article className="card stat-card">
          <div className="stat-card-header">
            <span>Profile completeness</span>
            <small>Required and optional onboarding fields</small>
          </div>
          <strong>{completeness}%</strong>
        </article>
      </section>

      <section className="card form-section">
        <div className="section-heading">
          <div>
            <p className="eyebrow">{profileQuery.data ? "Update" : "Create"}</p>
            <h3 className="section-title">SME onboarding details</h3>
          </div>
        </div>
        {successMessage ? <div className="state-card success">{successMessage}</div> : null}
        {profileQuery.isLoading ? <div className="state-card">Loading business profile...</div> : null}

        <form
          className="field-grid"
          onSubmit={(event) => {
            event.preventDefault();
            setSuccessMessage("");
            saveMutation.mutate();
          }}
        >
          <label>
            <span className="field-label">Business name</span>
            <input className="input" required value={formState.business_name} onChange={(event) => setFormState((current) => ({ ...current, business_name: event.target.value }))} />
          </label>
          <label>
            <span className="field-label">Business type</span>
            <select className="input" required value={formState.business_type} onChange={(event) => setFormState((current) => ({ ...current, business_type: event.target.value }))}>
              <option value="">Select type</option>
              <option value="sole_proprietor">Sole proprietor</option>
              <option value="private_company">Private company</option>
              <option value="close_corporation">Close corporation</option>
              <option value="partnership">Partnership</option>
              <option value="non_profit">Non-profit</option>
            </select>
          </label>
          <label>
            <span className="field-label">Trading name</span>
            <input className="input" value={formState.trading_name} onChange={(event) => setFormState((current) => ({ ...current, trading_name: event.target.value }))} />
          </label>
          <label>
            <span className="field-label">Registration number</span>
            <input className="input" value={formState.registration_number} onChange={(event) => setFormState((current) => ({ ...current, registration_number: event.target.value }))} />
          </label>
          <label>
            <span className="field-label">VAT number</span>
            <input className="input" value={formState.vat_number} onChange={(event) => setFormState((current) => ({ ...current, vat_number: event.target.value }))} />
          </label>
          <label>
            <span className="field-label">Verification status</span>
            <select className="input" value={formState.verification_status} onChange={(event) => setFormState((current) => ({ ...current, verification_status: event.target.value as BusinessVerificationStatus }))}>
              {Object.entries(statusLabels).map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>
          </label>
          <label>
            <span className="field-label">Contact email</span>
            <input className="input" required type="email" value={formState.contact_email} onChange={(event) => setFormState((current) => ({ ...current, contact_email: event.target.value }))} />
          </label>
          <label>
            <span className="field-label">Contact phone number</span>
            <input className="input" required value={formState.contact_phone_number} onChange={(event) => setFormState((current) => ({ ...current, contact_phone_number: event.target.value }))} />
          </label>
          <label className="field-span">
            <span className="field-label">Business address</span>
            <textarea className="input textarea" required rows={4} value={formState.business_address} onChange={(event) => setFormState((current) => ({ ...current, business_address: event.target.value }))} />
          </label>
          <div className="field-span form-actions">
            <button className="button button-large" disabled={saveMutation.isPending} type="submit">
              {saveMutation.isPending ? "Saving..." : profileQuery.data ? "Update business profile" : "Create business profile"}
            </button>
            {saveMutation.isError ? <span className="form-error">{getErrorMessage(saveMutation.error)}</span> : null}
          </div>
        </form>
      </section>
    </div>
  );
}
