/**
 * The filter panel.
 *
 * Every control writes to the URL (see `useSearchCriteria`), so a filtered view
 * is shareable and the back button undoes one filter at a time.
 *
 * On mobile the same panel is a bottom sheet. Not a separate component: two
 * implementations of the same filters drift, and the mobile one always ends up
 * missing the filter someone added last week.
 */

import { useAmenities } from '@/application/hooks/useCatalog'
import { useSearchCriteria } from '@/application/hooks/useSearchParamsState'
import { PROPERTY_TYPES } from '@/domain/property'
import { Button } from '@/ui/Button'
import { Checkbox } from '@/ui/Field'
import { cn } from '@/ui/cn'

interface PriceStep {
  readonly label: string
  readonly min: number | undefined
  readonly max: number | undefined
}

// Minor units: ₹2,500 is 250000 paise. Both bounds are always present so the
// "any price" reset and the radio comparison stay a single shape.
const PRICE_STEPS: readonly PriceStep[] = [
  { label: 'Under ₹2,500', min: undefined, max: 250_000 },
  { label: '₹2,500 – ₹5,000', min: 250_000, max: 500_000 },
  { label: '₹5,000 – ₹10,000', min: 500_000, max: 1_000_000 },
  { label: '₹10,000+', min: 1_000_000, max: undefined },
]

export function Filters({ onDone }: { onDone?: () => void }) {
  const { criteria, update, toggleInArray, reset, activeFilterCount } = useSearchCriteria()
  const { data: amenities = [] } = useAmenities()
  const filterable = amenities.filter((a) => a.isFilterable).slice(0, 12)

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="font-semibold text-ink-900">Filters</h2>
        {activeFilterCount > 0 && (
          <button
            type="button"
            onClick={reset}
            className="text-sm font-medium text-brand-600 hover:underline"
          >
            Clear all ({activeFilterCount})
          </button>
        )}
      </div>

      <FilterGroup title="Property type">
        <div className="flex flex-wrap gap-2">
          {PROPERTY_TYPES.map((type) => {
            const active = criteria.propertyType?.includes(type.value) ?? false
            return (
              <button
                key={type.value}
                type="button"
                aria-pressed={active}
                onClick={() => toggleInArray('propertyType', type.value)}
                className={cn(
                  'rounded-full border px-3 py-1.5 text-sm transition-colors',
                  active
                    ? 'border-brand-600 bg-brand-50 text-brand-700'
                    : 'border-ink-200 text-ink-600 hover:border-ink-300',
                )}
              >
                {type.label}
              </button>
            )
          })}
        </div>
      </FilterGroup>

      <FilterGroup title="Price per night">
        <div className="space-y-2">
          {PRICE_STEPS.map((step) => {
            const active = criteria.minPrice === step.min && criteria.maxPrice === step.max
            return (
              <label key={step.label} className="flex items-center gap-3 text-sm text-ink-700">
                <input
                  type="radio"
                  name="price"
                  checked={active}
                  onChange={() =>
                    update({ minPrice: step.min, maxPrice: step.max })
                  }
                  className="size-4 text-brand-600"
                />
                {step.label}
              </label>
            )
          })}
          {(criteria.minPrice !== undefined || criteria.maxPrice !== undefined) && (
            <button
              type="button"
              onClick={() => update({ minPrice: undefined, maxPrice: undefined })}
              className="text-xs text-brand-600 hover:underline"
            >
              Any price
            </button>
          )}
        </div>
      </FilterGroup>

      <FilterGroup title="Guest rating">
        <div className="flex gap-2">
          {[4.5, 4, 3.5].map((rating) => {
            const active = criteria.minRating === rating
            return (
              <button
                key={rating}
                type="button"
                aria-pressed={active}
                onClick={() => update({ minRating: active ? undefined : rating })}
                className={cn(
                  'rounded-full border px-3 py-1.5 text-sm transition-colors',
                  active
                    ? 'border-brand-600 bg-brand-50 text-brand-700'
                    : 'border-ink-200 text-ink-600 hover:border-ink-300',
                )}
              >
                {rating}+
              </button>
            )
          })}
        </div>
      </FilterGroup>

      <FilterGroup title="Booking">
        <div className="space-y-3">
          <Checkbox
            label="Instant booking"
            description="Confirmed immediately, without waiting for the host"
            checked={criteria.instantBooking ?? false}
            onChange={(e) => update({ instantBooking: e.target.checked || undefined })}
          />
          <Checkbox
            label="Free cancellation"
            description="Flexible or moderate policy"
            checked={criteria.cancellation === 'flexible'}
            onChange={(e) => update({ cancellation: e.target.checked ? 'flexible' : undefined })}
          />
        </div>
      </FilterGroup>

      {filterable.length > 0 && (
        <FilterGroup title="Amenities">
          <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
            {filterable.map((amenity) => (
              <Checkbox
                key={amenity.code}
                label={amenity.label}
                checked={criteria.amenity?.includes(amenity.code) ?? false}
                onChange={() => toggleInArray('amenity', amenity.code)}
              />
            ))}
          </div>
        </FilterGroup>
      )}

      {onDone && (
        <Button fullWidth onClick={onDone} className="md:hidden">
          Show results
        </Button>
      )}
    </div>
  )
}

function FilterGroup({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <fieldset className="border-t border-ink-100 pt-5 first:border-0 first:pt-0">
      <legend className="mb-3 text-sm font-medium text-ink-800">{title}</legend>
      {children}
    </fieldset>
  )
}
