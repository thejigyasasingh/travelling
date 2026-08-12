import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { fileURLToPath, URL } from 'node:url'

/**
 * A third app, separate from both the customer site and the admin panel.
 *
 * Not merged into admin, even though the two look alike: staff see every
 * vendor's revenue and a vendor must see only their own, and the safest way to
 * keep that true is for the vendor build to contain no admin route at all. A
 * role check inside one shared bundle is one `if` away from leaking a
 * competitor's numbers.
 */
export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: { alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) } },
  server: {
    port: 5175,
    proxy: {
      '/api': {
        target: process.env.VITE_PROXY_TARGET ?? 'http://localhost:8000',
        changeOrigin: false,
      },
    },
  },
  build: { sourcemap: true },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./tests/setup.ts'],
    include: ['tests/**/*.test.{ts,tsx}'],
    coverage: {
      provider: 'v8',
      // `text` for the terminal, `lcov` for CI to upload, `json-summary` so a
      // workflow step can read the number without parsing a report.
      reporter: ['text-summary', 'lcov', 'json-summary'],
      include: ['src/**/*.{ts,tsx}'],
      exclude: [
        'src/main.tsx',            // the mount point; nothing to assert
        'src/vite-env.d.ts',
        'src/**/*.d.ts',
        // Route tables and the composition root are wiring, not logic. A test
        // that rendered them would be asserting that imports resolve.
        'src/app/routes.tsx',
        'src/infrastructure/repositories.ts',
      ],
      // No threshold. These suites cover the logic that has behaviour —
      // formatting, mapping, page states — and a percentage gate on a UI
      // codebase mostly measures how much JSX has been written.
      // The number is reported on every run so a drop is visible.
    },
  },
})
