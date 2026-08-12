/// <reference types="vite/client" />

/**
 * The environment variables this app reads. Declared rather than left as
 * `Record<string, string>`, so a typo in `import.meta.env.VITE_API_BSAE_URL`
 * is a compile error instead of `undefined` at runtime.
 */
interface ImportMetaEnv {
  readonly VITE_API_BASE_URL?: string
  readonly VITE_PROXY_TARGET?: string
  readonly VITE_RAZORPAY_KEY_ID?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
