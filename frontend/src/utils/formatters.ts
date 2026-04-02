/**
 * Date and number formatting utilities for Swedish locale.
 */

export function formatDate(dateStr: string | null | undefined): string {
  if (!dateStr) return '—';
  try {
    return new Date(dateStr).toLocaleDateString('sv-SE');
  } catch {
    return dateStr;
  }
}

export function formatDateTime(dateStr: string | null | undefined): string {
  if (!dateStr) return '—';
  try {
    return new Date(dateStr).toLocaleString('sv-SE');
  } catch {
    return dateStr;
  }
}

export function formatCurrency(
  amount: number | null | undefined,
  currency = 'SEK',
): string {
  if (amount == null) return '—';

  // Intl.NumberFormat throws RangeError on invalid ISO 4217 currency codes.
  // Validate: must be exactly 3 uppercase letters. Fall back to SEK otherwise.
  const safeCurrency = /^[A-Z]{3}$/.test(currency) ? currency : 'SEK';

  try {
    return new Intl.NumberFormat('sv-SE', {
      style: 'currency',
      currency: safeCurrency,
      minimumFractionDigits: 2,
    }).format(amount);
  } catch {
    // Final safety net — format without currency symbol
    return `${amount.toFixed(2)} ${safeCurrency}`;
  }
}

export function formatNumber(value: number | null | undefined): string {
  if (value == null) return '—';
  return new Intl.NumberFormat('sv-SE', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(value);
}
