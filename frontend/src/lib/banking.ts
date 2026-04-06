export const BANK_NAME_OPTIONS = [
  "ABSA",
  "African Bank",
  "Bank Zero",
  "Bidvest Bank",
  "Capitec",
  "Discovery Bank",
  "FNB",
  "Investec",
  "Mercantile Bank",
  "Nedbank",
  "Standard Bank",
  "TymeBank",
  "Other",
] as const;

export function getBankNameOptions(currentValue = "") {
  if (currentValue && !BANK_NAME_OPTIONS.includes(currentValue as (typeof BANK_NAME_OPTIONS)[number])) {
    return [currentValue, ...BANK_NAME_OPTIONS];
  }
  return [...BANK_NAME_OPTIONS];
}
