"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { FormEvent, useMemo, useState } from "react";

import { forgotPassword, getErrorMessage, loginUser, registerUser, resetPassword } from "@/lib/api";
import { useAuth } from "@/components/auth/auth-provider";

function AuthLayout({
  eyebrow,
  title,
  subtitle,
  children,
}: {
  eyebrow: string;
  title: string;
  subtitle: string;
  children: React.ReactNode;
}) {
  return (
    <section className="auth-shell">
      <div className="auth-card">
        <p className="eyebrow">{eyebrow}</p>
        <h1 className="auth-title">{title}</h1>
        <p className="subtle-copy auth-subtitle">{subtitle}</p>
        {children}
      </div>
    </section>
  );
}

export function LoginForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { setAuthenticatedUser } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const successMessage = searchParams.get("reset") === "success" ? "Password reset complete. Please sign in." : "";

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setIsSubmitting(true);
    setError("");

    try {
      const user = await loginUser({ email, password });
      setAuthenticatedUser(user);
      const nextPath = searchParams.get("next");
      window.location.assign(nextPath && nextPath.startsWith("/") ? nextPath : "/");
    } catch (submissionError) {
      setError(getErrorMessage(submissionError));
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <AuthLayout
      eyebrow="Sign in"
      title="Welcome back"
      subtitle="Use your email address and password to access invoices, reminders, and recurring schedules."
    >
      <form className="auth-form" onSubmit={handleSubmit}>
        {successMessage ? <div className="state-card success">{successMessage}</div> : null}
        {error ? <div className="state-card error">{error}</div> : null}
        <label className="field-group">
          <span>Email</span>
          <input className="input" type="email" value={email} onChange={(event) => setEmail(event.target.value)} required />
        </label>
        <label className="field-group">
          <span>Password</span>
          <input
            className="input"
            type="password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            required
          />
        </label>
        <button className="button" disabled={isSubmitting} type="submit">
          {isSubmitting ? "Signing in..." : "Log in"}
        </button>
      </form>
      <div className="auth-links">
        <Link href="/forgot-password">Forgot password?</Link>
        <Link href="/register">Create an account</Link>
      </div>
    </AuthLayout>
  );
}

export function RegisterForm() {
  const router = useRouter();
  const { setAuthenticatedUser } = useAuth();
  const [formState, setFormState] = useState({
    email: "",
    first_name: "",
    last_name: "",
    password: "",
    confirm_password: "",
  });
  const [error, setError] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setIsSubmitting(true);
    setError("");

    try {
      const user = await registerUser(formState);
      setAuthenticatedUser(user);
      router.replace("/");
    } catch (submissionError) {
      setError(getErrorMessage(submissionError));
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <AuthLayout
      eyebrow="Register"
      title="Create your workspace access"
      subtitle="Set up an account so you can manage invoices, reminders, and recurring billing securely."
    >
      <form className="auth-form" onSubmit={handleSubmit}>
        {error ? <div className="state-card error">{error}</div> : null}
        <label className="field-group">
          <span>Email</span>
          <input
            className="input"
            type="email"
            value={formState.email}
            onChange={(event) => setFormState((state) => ({ ...state, email: event.target.value }))}
            required
          />
        </label>
        <div className="auth-grid">
          <label className="field-group">
            <span>First name</span>
            <input
              className="input"
              value={formState.first_name}
              onChange={(event) => setFormState((state) => ({ ...state, first_name: event.target.value }))}
            />
          </label>
          <label className="field-group">
            <span>Last name</span>
            <input
              className="input"
              value={formState.last_name}
              onChange={(event) => setFormState((state) => ({ ...state, last_name: event.target.value }))}
            />
          </label>
        </div>
        <label className="field-group">
          <span>Password</span>
          <input
            className="input"
            type="password"
            value={formState.password}
            onChange={(event) => setFormState((state) => ({ ...state, password: event.target.value }))}
            required
          />
        </label>
        <label className="field-group">
          <span>Confirm password</span>
          <input
            className="input"
            type="password"
            value={formState.confirm_password}
            onChange={(event) => setFormState((state) => ({ ...state, confirm_password: event.target.value }))}
            required
          />
        </label>
        <button className="button" disabled={isSubmitting} type="submit">
          {isSubmitting ? "Creating account..." : "Register"}
        </button>
      </form>
      <div className="auth-links">
        <Link href="/login">Already have an account?</Link>
      </div>
    </AuthLayout>
  );
}

export function ForgotPasswordForm() {
  const [email, setEmail] = useState("");
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setIsSubmitting(true);
    setError("");

    try {
      const response = await forgotPassword({ email });
      setSuccess(response.detail);
    } catch (submissionError) {
      setError(getErrorMessage(submissionError));
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <AuthLayout
      eyebrow="Reset access"
      title="Forgot your password?"
      subtitle="Enter your email address and, if an account exists, you’ll receive a secure reset link."
    >
      <form className="auth-form" onSubmit={handleSubmit}>
        {success ? <div className="state-card success">{success}</div> : null}
        {error ? <div className="state-card error">{error}</div> : null}
        <label className="field-group">
          <span>Email</span>
          <input className="input" type="email" value={email} onChange={(event) => setEmail(event.target.value)} required />
        </label>
        <button className="button" disabled={isSubmitting} type="submit">
          {isSubmitting ? "Sending..." : "Send reset link"}
        </button>
      </form>
      <div className="auth-links">
        <Link href="/login">Back to login</Link>
      </div>
    </AuthLayout>
  );
}

export function ResetPasswordForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const uid = searchParams.get("uid") || "";
  const token = searchParams.get("token") || "";
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const hasToken = useMemo(() => Boolean(uid && token), [token, uid]);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setIsSubmitting(true);
    setError("");

    try {
      await resetPassword({ uid, token, password, confirm_password: confirmPassword });
      window.location.assign("/login?reset=success");
    } catch (submissionError) {
      setError(getErrorMessage(submissionError));
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <AuthLayout
      eyebrow="Choose a new password"
      title="Set a new password"
      subtitle="Use a strong password you haven’t used before. Reset links are time-limited for security."
    >
      {!hasToken ? <div className="state-card error">This password reset link is invalid or has expired.</div> : null}
      {error ? <div className="state-card error">{error}</div> : null}
      <form className="auth-form" onSubmit={handleSubmit}>
        <label className="field-group">
          <span>New password</span>
          <input
            className="input"
            disabled={!hasToken}
            type="password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            required
          />
        </label>
        <label className="field-group">
          <span>Confirm password</span>
          <input
            className="input"
            disabled={!hasToken}
            type="password"
            value={confirmPassword}
            onChange={(event) => setConfirmPassword(event.target.value)}
            required
          />
        </label>
        <button className="button" disabled={isSubmitting || !hasToken} type="submit">
          {isSubmitting ? "Resetting..." : "Reset password"}
        </button>
      </form>
      <div className="auth-links">
        <Link href="/login">Back to login</Link>
      </div>
    </AuthLayout>
  );
}
