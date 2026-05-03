const CURRENCY_PREFERENCE_KEY = "invoice-manager.default-currency";
const COOKIE_MAX_AGE_SECONDS = 60 * 60 * 24 * 365;

export function getStoredCurrencyPreference() {
  if (typeof document === "undefined") {
    return "";
  }

  const cookieValue = document.cookie
    .split("; ")
    .find((cookie) => cookie.startsWith(`${CURRENCY_PREFERENCE_KEY}=`))
    ?.split("=")[1];

  if (cookieValue) {
    return decodeURIComponent(cookieValue).toUpperCase();
  }

  if (typeof window === "undefined") {
    return "";
  }

  return (window.localStorage.getItem(CURRENCY_PREFERENCE_KEY) || "").toUpperCase();
}

export function storeCurrencyPreference(code: string) {
  if (typeof document === "undefined") {
    return;
  }

  const normalized = code.toUpperCase();
  document.cookie = `${CURRENCY_PREFERENCE_KEY}=${encodeURIComponent(normalized)}; path=/; max-age=${COOKIE_MAX_AGE_SECONDS}; samesite=lax`;

  if (typeof window !== "undefined") {
    window.localStorage.setItem(CURRENCY_PREFERENCE_KEY, normalized);
  }
}
