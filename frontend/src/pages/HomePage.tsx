import { Link } from 'react-router-dom'
import { SearchBar } from '@/features/search/SearchBar'
import { useSearch } from '@/application/hooks/useCatalog'
import { PropertyCard, PropertyCardSkeleton } from '@/features/property/PropertyCard'
import { PROPERTY_TYPES } from '@/domain/property'
import { ButtonLink } from '@/ui/Button'

/**
 * Home.
 *
 * One job: get the visitor into a search. Everything below the fold is a
 * shortcut into one — by type, by destination — rather than content for its own
 * sake, because nobody arrives here to read.
 */
export default function HomePage() {
  const { data, isPending } = useSearch({ sort: 'rating_desc', limit: 8 })
  const featured = data?.pages[0]?.items ?? []

  return (
    <>
      <section className="relative isolate overflow-hidden bg-brand-900">
        <div
          className="absolute inset-0 -z-10 bg-[radial-gradient(ellipse_at_top,theme(colors.brand.700),theme(colors.brand.900))]"
          aria-hidden="true"
        />
        <div className="mx-auto max-w-5xl px-4 pt-16 pb-24 sm:px-6 lg:px-8">
          <h1 className="max-w-2xl text-3xl font-bold tracking-tight text-white sm:text-4xl md:text-5xl">
            Find a place worth the journey
          </h1>
          <p className="mt-3 max-w-xl text-base text-brand-100">
            Hotels, villas, apartments, homestays and resorts across India. Clear prices, fair
            cancellation, no surprises at checkout.
          </p>
          <div className="mt-8">
            <SearchBar variant="hero" />
          </div>
        </div>
      </section>

      <section className="mx-auto max-w-7xl px-4 py-12 sm:px-6 lg:px-8">
        <h2 className="text-xl font-semibold text-ink-900">Browse by type</h2>
        <ul className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
          {PROPERTY_TYPES.map((type) => (
            <li key={type.value}>
              <Link
                to={`/search?type=${type.value}`}
                className="flex h-24 flex-col justify-end rounded-2xl border border-ink-100 bg-sand-50 p-4 transition-colors hover:border-brand-300 hover:bg-brand-50"
              >
                <span className="font-medium text-ink-800">{type.label}</span>
              </Link>
            </li>
          ))}
        </ul>
      </section>

      <section className="mx-auto max-w-7xl px-4 pb-16 sm:px-6 lg:px-8">
        <div className="flex items-end justify-between">
          <div>
            <h2 className="text-xl font-semibold text-ink-900">Top rated stays</h2>
            <p className="mt-1 text-sm text-ink-500">Rated highest by guests who actually stayed.</p>
          </div>
          <ButtonLink to="/search?sort=rating_desc" variant="ghost" size="sm">
            See all
          </ButtonLink>
        </div>

        <div className="mt-5 grid gap-5 sm:grid-cols-2 lg:grid-cols-4">
          {isPending
            ? Array.from({ length: 4 }, (_, i) => <PropertyCardSkeleton key={i} />)
            : featured.slice(0, 8).map((item) => <PropertyCard key={item.id} item={item} />)}
        </div>

        {!isPending && featured.length === 0 && (
          <p className="mt-6 rounded-2xl border border-dashed border-ink-200 p-8 text-center text-sm text-ink-500">
            No published stays yet. Once hosts list their properties they will appear here.
          </p>
        )}
      </section>

      <section className="border-t border-ink-100 bg-ink-50">
        <div className="mx-auto grid max-w-7xl gap-8 px-4 py-14 sm:px-6 md:grid-cols-3 lg:px-8">
          <Promise
            title="The price you see is the price you pay"
            body="Taxes and fees are included in every price on this site, from the search card to the invoice."
          />
          <Promise
            title="Cancellation you can read"
            body="Every stay states its policy in plain words before you pay, and the refund is calculated from what you were actually charged."
          />
          <Promise
            title="Confirmed means confirmed"
            body="Your rooms are held while you pay, and a confirmation with a GST invoice follows immediately."
          />
        </div>
      </section>
    </>
  )
}

function Promise({ title, body }: { title: string; body: string }) {
  return (
    <div>
      <h3 className="font-semibold text-ink-900">{title}</h3>
      <p className="mt-1.5 text-sm text-ink-600">{body}</p>
    </div>
  )
}
