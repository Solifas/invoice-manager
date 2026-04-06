"use client";

import Link from "next/link";
import type { Route } from "next";
import { usePathname, useRouter } from "next/navigation";
import { ReactNode, useEffect, useState } from "react";

import { useAuth } from "@/components/auth/auth-provider";

export function AppShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const { isAuthenticated, isLoading, logout, user } = useAuth();
  const [isLoggingOut, setIsLoggingOut] = useState(false);
  const isPublicPaymentRoute = pathname.startsWith("/pay/");
  const isAuthRoute =
    pathname.startsWith("/login") ||
    pathname.startsWith("/register") ||
    pathname.startsWith("/forgot-password") ||
    pathname.startsWith("/reset-password");

  useEffect(() => {
    if (isLoading) {
      return;
    }

    if (isPublicPaymentRoute) {
      return;
    }

    if (isAuthRoute && isAuthenticated) {
      window.location.replace("/");
      return;
    }

    if (!isAuthRoute && !isAuthenticated) {
      window.location.replace(`/login?next=${encodeURIComponent(pathname)}`);
    }
  }, [isAuthRoute, isAuthenticated, isLoading, isPublicPaymentRoute, pathname]);

  if (isPublicPaymentRoute) {
    return <main className="public-shell">{children}</main>;
  }

  if (isAuthRoute) {
    if (isLoading || isAuthenticated) {
      return <main className="auth-shell auth-shell-loading">Checking your session...</main>;
    }
    return <main className="public-shell">{children}</main>;
  }

  if (isLoading || !isAuthenticated) {
    return <main className="app-loading-shell">Loading your workspace...</main>;
  }

  const navItems = [
    {
      href: "/" as Route,
      label: "Dashboard",
      isActive: pathname === "/" || pathname === "/dashboard",
    },
    {
      href: "/recurring-invoices" as Route,
      label: "Recurring",
      isActive: pathname.startsWith("/recurring-invoices"),
    },
    {
      href: "/settings/banking-details" as Route,
      label: "Banking",
      isActive: pathname.startsWith("/settings/"),
    },
    {
      href: "/invoices/new" as Route,
      label: "New invoice",
      isActive: pathname.startsWith("/invoices/"),
      isPrimary: true,
    },
  ];

  return (
    <div className="app-frame">
      <div className="app-backdrop" />
      <div className="shell">
        <header className="topbar">
          <div className="topbar-main">
            <div className="brand-block">
              <div className="brand-mark">IM</div>
              <div>
                <p className="eyebrow">Invoice Manager</p>
                <h1>Billing that stays clear.</h1>
                <p className="subtle-copy topbar-copy">
                  Track invoices, reminders, and recurring billing from one compact workspace.
                </p>
              </div>
            </div>
            <div className="session-banner topbar-session-banner">
              <span>Signed in as {user?.first_name || user?.email}</span>
              <small>{user?.email}</small>
            </div>
          </div>
          <div className="topbar-nav-row">
            <nav className="topbar-actions topbar-nav" aria-label="Primary navigation">
              {navItems.map((item) => (
                <Link
                  key={item.href}
                  className={`button ${item.isPrimary ? "button-primary-nav" : "button-ghost"} button-nav${item.isActive ? " is-active" : ""}`}
                  href={item.href}
                  aria-current={item.isActive ? "page" : undefined}
                >
                  {item.label}
                </Link>
              ))}
            </nav>
            <button
              className="button button-ghost button-nav"
              disabled={isLoggingOut}
              onClick={async () => {
                setIsLoggingOut(true);
                try {
                  await logout();
                  router.replace("/login");
                } finally {
                  setIsLoggingOut(false);
                }
              }}
              type="button"
            >
              {isLoggingOut ? "Logging out..." : "Logout"}
            </button>
          </div>
        </header>
        <main>{children}</main>
      </div>
    </div>
  );
}
