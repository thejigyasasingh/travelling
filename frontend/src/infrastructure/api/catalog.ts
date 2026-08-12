/** `CatalogRepository` over the search and property endpoints. */

import type { CatalogRepository, SearchCriteria, SearchPage } from '@/application/ports'
import { http } from '@/infrastructure/http/client'
import type * as dto from './dto'
import { toAmenity, toProperty, toQuote, toSearchItem, toSuggestion } from './mappers'

export const catalogRepository: CatalogRepository = {
  async search(criteria: SearchCriteria, signal?: AbortSignal): Promise<SearchPage> {
    const data = await http.get<dto.SearchResponseDto>('/search', {
      query: {
        q: criteria.q,
        city_id: criteria.cityId,
        lat: criteria.lat,
        lng: criteria.lng,
        radius_m: criteria.radiusM,
        check_in: criteria.checkIn,
        check_out: criteria.checkOut,
        adults: criteria.adults,
        children: criteria.children,
        infants: criteria.infants,
        rooms: criteria.rooms,
        property_type: criteria.propertyType,
        amenity: criteria.amenity,
        min_price: criteria.minPrice,
        max_price: criteria.maxPrice,
        min_rating: criteria.minRating,
        instant_booking: criteria.instantBooking,
        cancellation: criteria.cancellation,
        sort: criteria.sort,
        limit: criteria.limit,
        cursor: criteria.cursor,
      },
      signal,
    })
    return {
      items: data.items.map(toSearchItem),
      nextCursor: data.next_cursor ?? null,
      totalEstimate: data.total_estimate ?? null,
      appliedRadiusM: data.applied_radius_m ?? null,
    }
  },

  async suggest(query, signal) {
    const data = await http.get<dto.SuggestionDto[]>('/search/suggest', {
      query: { q: query },
      signal,
    })
    return data.map(toSuggestion)
  },

  async property(identifier, signal) {
    return toProperty(
      await http.get<dto.PropertyDto>(`/properties/${encodeURIComponent(identifier)}`, { signal }),
    )
  },

  async availability(propertyId, range, signal) {
    const data = await http.get<dto.CalendarResponseDto>(
      `/properties/${encodeURIComponent(propertyId)}/availability`,
      { query: { from_date: range.from, to_date: range.to }, signal },
    )
    return data.days.map((day) => ({
      date: day.date,
      // A day is bookable only if it is neither blocked nor sold out. The two
      // are separate flags on the wire and collapsing them here keeps every
      // caller from re-deriving the same boolean slightly differently.
      isAvailable:
        day.is_blocked !== true && (day.units_available === null || (day.units_available ?? 1) > 0),
      rateMinor: day.rate_minor ?? null,
    }))
  },

  async quote(propertyId, input, signal) {
    return toQuote(
      await http.post<dto.QuoteDto>(
        `/properties/${encodeURIComponent(propertyId)}/quote`,
        {
          room_type_id: input.roomTypeId,
          check_in: input.checkIn,
          check_out: input.checkOut,
          adults: input.adults,
          children: input.children ?? 0,
          infants: input.infants ?? 0,
          rooms: input.rooms ?? 1,
        },
        { signal },
      ),
    )
  },

  async amenities(signal) {
    const data = await http.get<dto.AmenityDto[]>('/amenities', { signal })
    return data.map(toAmenity)
  },
}
