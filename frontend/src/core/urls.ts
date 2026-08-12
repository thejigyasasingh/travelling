/**
 * URL safety.
 *
 * `safeNext` guards the post-login redirect. An open redirect on a login page
 * is a phishing primitive: `?next=https://evil.example` sends a freshly
 * authenticated user off-site, with our domain in the referrer and their trust
 * already established. Only same-site paths are honoured.
 */

export function safeNext(value: string | null | undefined, fallback = '/'): string {
  if (!value) return fallback
  // `//evil.example` is protocol-relative and a browser treats it as absolute,
  // so checking for a leading slash alone is not enough.
  if (!value.startsWith('/') || value.startsWith('//')) return fallback
  // `/\evil.example` is normalised to a host by some browsers.
  if (value.startsWith('/\\')) return fallback
  return value
}
