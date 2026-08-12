import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { fileURLToPath, URL } from 'node:url'

// The dev proxy sends /api to the backend on the same origin as the app.
// Same-origin matters: the refresh token lives in an HttpOnly cookie scoped to
// /api/v1/auth, and a cross-origin dev setup would silently drop it, so login
// would work and session restore would not — for reasons invisible in the code.
export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) },
  },
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: process.env.VITE_PROXY_TARGET ?? 'http://localhost:8000',
        changeOrigin: false,
      },
    },
  },
  build: {
    // Source maps in production: a stack trace from a real user is worth more
    // than hiding minified code from someone who can read the network tab.
    sourcemap: true,
    rollupOptions: {
      output: {
        // Router and query land in their own chunks so a page-level code split
        // does not re-download them on every lazy route.
        manualChunks(id: string) {
          if (id.includes('node_modules/react') || id.includes('node_modules/scheduler')) {
            return 'react'
          }
          if (id.includes('@tanstack')) return 'query'
          return undefined
        },
      },
    },
  },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./tests/setup.ts'],
    include: ['tests/**/*.test.{ts,tsx}', 'src/**/*.test.{ts,tsx}'],
    coverage: {
      provider: 'v8',
      // `text-summary` for the terminal, `lcov` for CI to upload,
      // `json-summary` so a workflow step can read the number without parsing.
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
      // codebase mostly measures how much JSX has been written. The number is
      // reported on every run so a drop is visible.
    },
  },
})
