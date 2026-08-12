import { ButtonLink } from '@/ui/Button'

export default function NotFoundPage() {
  return (
    <div className="mx-auto flex max-w-md flex-col items-center px-4 py-24 text-center">
      <p className="text-6xl font-bold text-brand-600">404</p>
      <h1 className="mt-4 text-xl font-semibold text-ink-900">This page does not exist</h1>
      <p className="mt-2 text-sm text-ink-500">
        The link may be old, or the stay may no longer be listed.
      </p>
      <div className="mt-6 flex gap-3">
        <ButtonLink to="/" variant="secondary">
          Go home
        </ButtonLink>
        <ButtonLink to="/search">Search stays</ButtonLink>
      </div>
    </div>
  )
}
