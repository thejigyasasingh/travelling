import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { QueryClientProvider } from '@tanstack/react-query'
import { RouterProvider } from 'react-router-dom'
import { RepositoryProvider } from '@/application/RepositoryContext'
import { AuthProvider } from '@/app/AuthProvider'
import { createQueryClient } from '@/app/queryClient'
import { router } from '@/app/routes'
import { repositories } from '@/infrastructure/repositories'
import './index.css'

const queryClient = createQueryClient()

const root = document.getElementById('root')
if (!root) throw new Error('#root is missing from index.html')

createRoot(root).render(
  <StrictMode>
    {/* Repositories outermost: AuthProvider needs them to restore the session. */}
    <RepositoryProvider repositories={repositories}>
      <QueryClientProvider client={queryClient}>
        <AuthProvider>
          <RouterProvider router={router} />
        </AuthProvider>
      </QueryClientProvider>
    </RepositoryProvider>
  </StrictMode>,
)
