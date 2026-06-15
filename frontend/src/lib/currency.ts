/**
 * Currency helpers shared by Settings (the picker) and anywhere costs render.
 *
 * The vault stores a single ISO 4217 code (see SystemConfig.currency); we format
 * amounts with `Intl.NumberFormat` so the right symbol and digit grouping follow
 * the code without us hand-maintaining a symbol table.
 */

export interface CurrencyOption {
  code: string;
  label: string;
}

// Common self-hosting currencies. Not exhaustive — Intl handles any valid code,
// this is just the picker shortlist.
export const CURRENCY_OPTIONS: CurrencyOption[] = [
  { code: "USD", label: "USD — US Dollar ($)" },
  { code: "EUR", label: "EUR — Euro (€)" },
  { code: "GBP", label: "GBP — British Pound (£)" },
  { code: "CAD", label: "CAD — Canadian Dollar ($)" },
  { code: "AUD", label: "AUD — Australian Dollar ($)" },
  { code: "JPY", label: "JPY — Japanese Yen (¥)" },
  { code: "CNY", label: "CNY — Chinese Yuan (¥)" },
  { code: "INR", label: "INR — Indian Rupee (₹)" },
  { code: "CHF", label: "CHF — Swiss Franc" },
  { code: "SEK", label: "SEK — Swedish Krona (kr)" },
  { code: "NOK", label: "NOK — Norwegian Krone (kr)" },
  { code: "DKK", label: "DKK — Danish Krone (kr)" },
  { code: "PLN", label: "PLN — Polish Złoty (zł)" },
  { code: "BRL", label: "BRL — Brazilian Real (R$)" },
  { code: "MXN", label: "MXN — Mexican Peso ($)" },
];

/**
 * Format a numeric cost in the given currency. Returns an em dash for null so
 * cards/charts show "—" rather than a misleading "$0.00".
 */
export function formatCurrency(
  value: number | null | undefined,
  code: string,
): string {
  if (value == null) return "—";
  try {
    return new Intl.NumberFormat(undefined, {
      style: "currency",
      currency: code || "USD",
    }).format(value);
  } catch {
    // Unknown/invalid code — fall back to the bare number with the code suffix.
    return `${value.toFixed(2)} ${code}`;
  }
}
