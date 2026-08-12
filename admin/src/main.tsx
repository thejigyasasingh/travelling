import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { RouterProvider } from 'react-router-dom'
import { AuthProvider, NotStaffScreen, SignInScreen, isStaff, useAuth } from '@/app/AuthGate'
import { router } from '@/app/routes'
import { ApiError } from '@/core/http'
import './index.css'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      // A 403 is not retryable: retrying will not grant a permission, and three
      // attempts turn one clear refusal into three seconds of spinner.
      retry: (failureCount, error) =>
        error instanceof ApiError ? error.isRetryable && failureCount < 2 : failureCount < 1,
      refetchOnWindowFocus: true,
    },
    mutations: { retry: false },
  },
})

function App() {
  const { user, status, signOut } = useAuth()

  if (status === 'restoring') {
    return (
      <div className="grid min-h-dvh place-items-center text-sm text-ink-500">Loading…</div>
    )
  }
  if (!user) return <SignInScreen />
  // Defence in depth: every endpoint checks its own permission server-side.
  // This just avoids showing a tool that would 403 on every panel.
  if (!isStaff(user)) return <NotStaffScreen onSignOut={() => void signOut()} />

  return <RouterProvider router={router} />
}

const root = document.getElementById('root')
if (!root) throw new Error('#root is missing from index.html')

createRoot(root).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <App />
      </AuthProvider>
    </QueryClientProvider>
  </StrictMode>,
)
