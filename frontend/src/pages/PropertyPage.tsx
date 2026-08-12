import { Link, useParams, useSearchParams } from 'react-router-dom'
import { useProperty } from '@/application/hooks/useCatalog'
import { usePropertyReviews } from '@/application/hooks/useReviews'
import { criteriaFromParams } from '@/application/hooks/useSearchParamsState'
import { Gallery } from '@/features/property/Gallery'
import { BookingWidget } from '@/features/property/BookingWidget'
import { WishlistButton } from '@/features/wishlist/WishlistButton'
import { ReviewList, ReviewSummaryPanel } from '@/features/reviews/ReviewList'
import { cancellationPolicy, REFUND_FOOTNOTE } from '@/domain/policies'
import { propertyTypeLabel } from '@/domain/property'
import { formatMinor } from '@/core/money'
import { Rating } from '@/ui/Rating'
import { Badge, ErrorState, LoadingBlock } from '@/ui/feedback'
import { ButtonLink } from '@/ui/Button'

/**
 * Property details.
 *
 * The booking widget is sticky beside the content on desktop and a fixed bar on
 * mobile — the price and the "Reserve" button must never be more than a glance
 * away, on any screen.
 */
export default function PropertyPage() {
  const { slug } = useParams<{ slug: string }>()
  const [params] = useSearchParams()
  const criteria = criteriaFromParams(params)

  const { data: property, isPending, isError, error, refetch } = useProperty(slug)
  const { data: reviews } = usePropertyReviews(property?.id)

  if (isPending) return <LoadingBlock label="Loading this stay" />
  if (isError) {
    return (
      <div className="mx-auto max-w-2xl px-4 py-16">
        <ErrorState error={error} onRetry={() => void refetch()} title="We could not load this stay" />
      </div>
    )
  }

  const policy = cancellationPolicy(property.cancellationPolicy)
  const cheapest = property.roomTypes.reduce<number | null>(
    (min, room) => (min === null || room.baseRateMinor < min ? room.baseRateMinor : min),
    null,
  )

  return (
    <div className="mx-auto max-w-7xl px-4 py-6 sm:px-6 lg:px-8">
      <nav aria-label="Breadcrumb" className="mb-4 text-sm text-ink-500">
        <Link to="/search" className="hover:text-brand-600">
          Stays
        </Link>
        <span className="mx-1.5">/</span>
        <Link to={`/search?q=${encodeURIComponent(property.city)}`} className="hover:text-brand-600">
          {property.city}
        </Link>
        <span className="mx-1.5">/</span>
        <span className="text-ink-700">{property.name}</span>
      </nav>

      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-ink-900 sm:text-3xl">
            {property.name}
          </h1>
          <div className="mt-1.5 flex flex-wrap items-center gap-x-3 gap-y-1 text-sm text-ink-600">
            <Rating value={property.reviewAverage} count={property.reviewCount} showLabel />
            <span>·</span>
            <span>{propertyTypeLabel(property.propertyType)}</span>
            <span>·</span>
            <span>
              {property.city}
              {property.state ? `, ${property.state}` : ''}
            </span>
          </div>
        </div>
        <WishlistButton item={property} />
      </div>

      <div className="mt-5">
        <Gallery images={property.images} name={property.name} />
      </div>

      <div className="mt-8 grid gap-10 lg:grid-cols-[1fr_380px]">
        <div className="min-w-0 space-y-10">
          <section aria-labelledby="about">
            <h2 id="about" className="text-lg font-semibold text-ink-900">
              About this place
            </h2>
            <p className="mt-3 whitespace-pre-line text-ink-700">{property.description}</p>
          </section>

          {property.roomTypes.length > 0 && (
            <section aria-labelledby="rooms">
              <h2 id="rooms" className="text-lg font-semibold text-ink-900">
                Rooms
              </h2>
              <ul className="mt-3 divide-y divide-ink-100 rounded-2xl border border-ink-100">
                {property.roomTypes.map((room) => (
                  <li key={room.id} className="flex flex-wrap items-center justify-between gap-3 p-4">
                    <div className="min-w-0">
                      <h3 className="font-medium text-ink-900">{room.name}</h3>
                      <p className="mt-0.5 text-sm text-ink-500">
                        {room.bedType} · sleeps {room.maxAdults + room.maxChildren}
                        {room.sizeSqft ? ` · ${room.sizeSqft} sq ft` : ''}
                        {room.minNights > 1 ? ` · ${room.minNights}-night minimum` : ''}
                      </p>
                      {room.description && (
                        <p className="mt-1 text-sm text-ink-600">{room.description}</p>
                      )}
                    </div>
                    <div className="text-right">
                      <div className="font-semibold text-ink-900">
                        {formatMinor(room.baseRateMinor, room.currency, { compact: true })}
                      </div>
                      <div className="text-xs text-ink-500">per night</div>
                      {room.unitsAvailable !== null && room.unitsAvailable <= 3 && (
                        <Badge tone="pending" className="mt-1">
                          {room.unitsAvailable === 0
                            ? 'Sold out'
                            : `Only ${room.unitsAvailable} left`}
                        </Badge>
                      )}
                    </div>
                  </li>
                ))}
              </ul>
            </section>
          )}

          {property.amenityCodes.length > 0 && (
            <section aria-labelledby="amenities">
              <h2 id="amenities" className="text-lg font-semibold text-ink-900">
                What this place offers
              </h2>
              <ul className="mt-3 grid grid-cols-2 gap-2 sm:grid-cols-3">
                {property.amenityCodes.map((code) => (
                  <li key={code} className="flex items-center gap-2 text-sm text-ink-700">
                    <span className="text-brand-600" aria-hidden="true">
                      ✓
                    </span>
                    {code.replace(/_/g, ' ')}
                  </li>
                ))}
              </ul>
            </section>
          )}

          <section aria-labelledby="location">
            <h2 id="location" className="text-lg font-semibold text-ink-900">
              Where you will be
            </h2>
            <p className="mt-2 text-ink-700">{property.address}</p>
            {property.locationIsApproximate && (
              <p className="mt-2 rounded-lg bg-ink-50 px-3 py-2 text-sm text-ink-600">
                The exact address is shared once your booking is confirmed. Until then the
                location is shown approximately — publishing a precise address would tell anyone
                where an unoccupied home is.
              </p>
            )}
          </section>

          <section aria-labelledby="rules">
            <h2 id="rules" className="text-lg font-semibold text-ink-900">
              Things to know
            </h2>
            <dl className="mt-3 grid gap-4 sm:grid-cols-2">
              <div>
                <dt className="text-sm font-medium text-ink-800">Check in / out</dt>
                <dd className="mt-1 text-sm text-ink-600">
                  From {property.checkInFrom} · until {property.checkOutBy}
                </dd>
              </div>
              <div>
                <dt className="text-sm font-medium text-ink-800">
                  Cancellation — {policy.label}
                </dt>
                <dd className="mt-1 text-sm text-ink-600">{policy.detail}</dd>
                <dd className="mt-1 text-xs text-ink-500">{REFUND_FOOTNOTE}</dd>
              </div>
              {property.houseRules.length > 0 && (
                <div className="sm:col-span-2">
                  <dt className="text-sm font-medium text-ink-800">House rules</dt>
                  <dd className="mt-1">
                    <ul className="list-inside list-disc text-sm text-ink-600">
                      {property.houseRules.map((rule) => (
                        <li key={rule}>{rule}</li>
                      ))}
                    </ul>
                  </dd>
                </div>
              )}
            </dl>
          </section>

          <section aria-labelledby="reviews">
            <div className="flex items-center justify-between">
              <h2 id="reviews" className="text-lg font-semibold text-ink-900">
                Reviews
              </h2>
              {property.reviewCount > 0 && (
                <Link
                  to={`/stays/${property.slug}/reviews`}
                  className="text-sm font-medium text-brand-600 hover:underline"
                >
                  See all {property.reviewCount}
                </Link>
              )}
            </div>
            <div className="mt-3">
              <ReviewSummaryPanel
                average={property.reviewAverage}
                count={property.reviewCount}
                summary={reviews?.summary}
              />
              <ReviewList reviews={reviews?.items ?? []} limit={3} />
            </div>
          </section>
        </div>

        {/* Desktop: sticky. Mobile: the fixed bar below takes over. */}
        <aside className="hidden lg:block">
          <div className="sticky top-24">
            <BookingWidget
              property={property}
              initial={{
                ...(criteria.checkIn ? { checkIn: criteria.checkIn } : {}),
                ...(criteria.checkOut ? { checkOut: criteria.checkOut } : {}),
                ...(criteria.adults ? { adults: criteria.adults } : {}),
                ...(criteria.children ? { children: criteria.children } : {}),
                ...(criteria.rooms ? { rooms: criteria.rooms } : {}),
              }}
            />
          </div>
        </aside>
      </div>

      {/* Mobile booking bar. `pb-safe` keeps it clear of the home indicator. */}
      <div className="fixed inset-x-0 bottom-14 z-30 border-t border-ink-100 bg-white/95 px-4 py-3 backdrop-blur lg:hidden no-print">
        <div className="flex items-center justify-between gap-3">
          <div>
            {cheapest !== null ? (
              <>
                <span className="text-xs text-ink-500">from </span>
                <span className="font-semibold text-ink-900">
                  {formatMinor(cheapest, property.currency, { compact: true })}
                </span>
                <span className="text-xs text-ink-500"> / night</span>
              </>
            ) : (
              <span className="text-sm text-ink-500">Price on request</span>
            )}
          </div>
          <ButtonLink to="#booking" onClick={(e) => {
            e.preventDefault()
            document.getElementById('mobile-booking')?.scrollIntoView({ behavior: 'smooth' })
          }}>
            Check availability
          </ButtonLink>
        </div>
      </div>

      <div id="mobile-booking" className="mt-10 lg:hidden">
        <BookingWidget
          property={property}
          initial={{
            ...(criteria.checkIn ? { checkIn: criteria.checkIn } : {}),
            ...(criteria.checkOut ? { checkOut: criteria.checkOut } : {}),
            ...(criteria.adults ? { adults: criteria.adults } : {}),
            ...(criteria.children ? { children: criteria.children } : {}),
            ...(criteria.rooms ? { rooms: criteria.rooms } : {}),
          }}
        />
        <div className="h-24" aria-hidden="true" />
      </div>
    </div>
  )
}
