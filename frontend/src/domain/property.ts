/** Properties, as the UI understands them. */

import type { IsoDate } from '@/core/dates'

export type PropertyType = 'hotel' | 'villa' | 'apartment' | 'homestay' | 'resort'

export const PROPERTY_TYPES: ReadonlyArray<{ value: PropertyType; label: string }> = [
  { value: 'hotel', label: 'Hotels' },
  { value: 'villa', label: 'Villas' },
  { value: 'apartment', label: 'Apartments' },
  { value: 'homestay', label: 'Homestays' },
  { value: 'resort', label: 'Resorts' },
]

export type CancellationPolicy = 'flexible' | 'moderate' | 'strict' | 'non_refundable'

export interface PropertyImage {
  readonly id: string
  readonly url: string
  readonly position: number
  readonly isCover: boolean
  readonly altText: string | null
  readonly caption: string | null
}

export interface RoomType {
  readonly id: string
  readonly name: string
  readonly description: string | null
  readonly bedType: string
  readonly maxAdults: number
  readonly maxChildren: number
  readonly totalUnits: number
  readonly sizeSqft: number | null
  readonly amenityCodes: readonly string[]
  readonly baseRateMinor: number
  readonly currency: string
  readonly minNights: number
  /** Present only when the request carried dates. `null` means "not asked". */
  readonly unitsAvailable: number | null
  readonly quoteTotalMinor: number | null
}

export interface Property {
  readonly id: string
  readonly slug: string
  readonly name: string
  readonly propertyType: string
  readonly description: string
  readonly address: string
  readonly city: string
  readonly state: string | null
  readonly countryCode: string
  readonly latitude: number | null
  readonly longitude: number | null
  /**
   * The map pin is fuzzed until a booking is confirmed. Not a bug to "fix":
   * publishing an exact address lets anyone locate a home whose owner is
   * demonstrably away on known dates.
   */
  readonly locationIsApproximate: boolean
  readonly amenityCodes: readonly string[]
  readonly images: readonly PropertyImage[]
  readonly roomTypes: readonly RoomType[]
  readonly cancellationPolicy: string
  readonly checkInFrom: string
  readonly checkOutBy: string
  readonly houseRules: readonly string[]
  readonly instantBooking: boolean
  readonly reviewAverage: number
  readonly reviewCount: number
  readonly currency: string
  readonly vendorId: string
}

export interface SearchResultItem {
  readonly id: string
  readonly slug: string
  readonly name: string
  readonly propertyType: string
  readonly city: string
  readonly countryCode: string
  readonly latitude: number | null
  readonly longitude: number | null
  readonly distanceM: number | null
  readonly coverImageUrl: string | null
  readonly reviewAverage: number
  readonly reviewCount: number
  readonly amenityCodes: readonly string[]
  readonly instantBooking: boolean
  readonly cancellationPolicy: string
  readonly maxOccupancy: number
  readonly fromPriceMinor: number | null
  /** The price for the searched dates. Absent when no dates were given. */
  readonly totalPriceMinor: number | null
  readonly currency: string
  readonly isAvailable: boolean
}

export interface Suggestion {
  readonly kind: 'city' | 'property'
  readonly id: string
  readonly label: string
  readonly sublabel: string | null
  readonly slug: string
}

export interface Amenity {
  readonly code: string
  readonly label: string
  readonly category: string
  readonly icon: string | null
  readonly isFilterable: boolean
}

export interface QuoteNight {
  readonly date: IsoDate
  readonly amountMinor: number
  readonly source: string
}

export interface Quote {
  readonly roomTypeId: string
  readonly nights: readonly QuoteNight[]
  readonly accommodationMinor: number
  readonly extraGuestMinor: number
  readonly cleaningFeeMinor: number
  readonly taxMinor: number
  readonly totalMinor: number
  readonly averageNightlyMinor: number
  readonly currency: string
  readonly isAvailable: boolean
  readonly unavailableDates: readonly IsoDate[]
}

export function coverImage(property: Property): PropertyImage | undefined {
  return property.images.find((i) => i.isCover) ?? property.images[0]
}

export function propertyTypeLabel(value: string): string {
  return PROPERTY_TYPES.find((t) => t.value === value)?.label.replace(/s$/, '') ?? value
}
