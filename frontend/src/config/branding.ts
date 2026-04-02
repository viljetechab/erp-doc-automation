/**
 * Branding configuration — single source of truth for all UI text and visual identity.
 *
 * To white-label for a specific client:
 *   1. Override any value below (or inject via Vite's define / env vars)
 *   2. Replace /public/logo.svg with the client's logo (200×48 px recommended)
 *   3. Adjust the CSS variables in index.css (--color-accent, --color-accent-hover)
 */

export const BRAND = {
  /** Short app name shown in titles and the sidebar */
  appName: import.meta.env.VITE_APP_NAME ?? 'OrderFlow Pro',

  /** Full descriptive name used in page <title> */
  appFullName: import.meta.env.VITE_APP_FULL_NAME ?? 'OrderFlow Pro — Order Pipeline',

  /** Tagline shown on the login screen */
  appTagline:
    import.meta.env.VITE_APP_TAGLINE ??
    'PDF order intake, AI extraction, and ERP export',

  /** Company name that owns / operates this instance */
  companyName: import.meta.env.VITE_COMPANY_NAME ?? 'OrderFlow Pro',

  /** Alt text for the logo image */
  logoAlt: import.meta.env.VITE_APP_NAME ?? 'OrderFlow Pro',

  /** Path to the logo file (relative to /public) */
  logoPath: '/logo.svg',

  /** Login page CTA button copy */
  loginButtonText: 'Sign in with Microsoft',

  /** Login page subtitle */
  loginSubtitle: 'Use your Microsoft work or school account to continue',

  /** Generic term for the ERP system (replaces "Monitor ERP" in UI) */
  erpSystemName: import.meta.env.VITE_ERP_SYSTEM_NAME ?? 'ERP System',

  /** Label for the customer CSV import */
  customerListLabel: import.meta.env.VITE_CUSTOMER_LIST_LABEL ?? 'Customer List CSV',

  /** Label for the article CSV/XLSX import */
  articleListLabel: import.meta.env.VITE_ARTICLE_LIST_LABEL ?? 'Article Catalogue',

  /** Support / contact email shown in error states */
  supportEmail: import.meta.env.VITE_SUPPORT_EMAIL ?? 'support@orderflowpro.example',
} as const;

export type Brand = typeof BRAND;
