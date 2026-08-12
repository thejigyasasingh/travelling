/**
 * Runtime configuration.
 *
 * Read once, at module load, so a missing variable is a boot failure rather
 * than a blank screen three clicks into a checkout. Everything here is
 * **public** — Vite inlines `import.meta.env.VITE_*` into the bundle, so a
 * secret placed here is a secret published to every visitor. The Razorpay key
 * id belongs here precisely because it is public by design; the key *secret*
 * never leaves the server.
 */

interface AppConfig {
  readonly apiBaseUrl: string
  readonly razorpayKeyId: string
  readonly razorpayCheckoutUrl: string
  readonly defaultCurrency: string
  readonly defaultLocale: string
  readonly isProduction: boolean
}

function required(name: string, value: string | undefined, fallback?: string): string {
  const resolved = value ?? fallback
  if (resolved === undefined || resolved === '') {
    throw new Error(
      `Missing ${name}. Copy .env.example to .env.local and fill it in — see the frontend README.`,
    )
  }
  return resolved
}

export const config: AppConfig = {
  // Relative by default so the app is same-origin with the API. That is not a
  // style choice: the refresh cookie is HttpOnly and scoped to /api/v1/auth,
  // and a cross-origin base URL drops it.
  apiBaseUrl: required('VITE_API_BASE_URL', import.meta.env.VITE_API_BASE_URL, '/api/v1'),
  razorpayKeyId: import.meta.env.VITE_RAZORPAY_KEY_ID ?? '',
  razorpayCheckoutUrl: 'https://checkout.razorpay.com/v1/checkout.js',
  defaultCurrency: 'INR',
  defaultLocale: 'en-IN',
  isProduction: import.meta.env.PROD,
}
