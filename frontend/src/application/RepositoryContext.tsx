/** Dependency injection for the UI: one context holding every port. */

import { createContext, use, type ReactNode } from 'react'
import type { Repositories } from './ports'

const RepositoryContext = createContext<Repositories | null>(null)

export function RepositoryProvider({
  repositories,
  children,
}: {
  repositories: Repositories
  children: ReactNode
}) {
  return <RepositoryContext value={repositories}>{children}</RepositoryContext>
}

export function useRepositories(): Repositories {
  const value = use(RepositoryContext)
  if (!value) {
    throw new Error('useRepositories must be used inside <RepositoryProvider>')
  }
  return value
}
