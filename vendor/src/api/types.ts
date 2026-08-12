/**
 * The server's shapes, hand-written.
 *
 * Not generated from the OpenAPI document, for the same reason the other two
 * clients are not: generated types describe what the server *says* it returns,
 * and the value of writing them by hand is that a mismatch surfaces as a
 * compile error in the file that consumes it rather than as `undefined` on a
 * page. The live-contract test is what keeps them honest — it asks the running
 * server for each of these and fails on a missing field.
 *
 * Money is integer minor units — paise — everywhere it appears. Nothing here
 * carries a float amount, and nothing should ever start.
 */

/** Offset paging, used by every bounded vendor table. The guest-facing lists
 *  are cursor-paged because they are unbounded; a host's own properties and
 *  bookings are not, and page numbers are what a host asks for. */
export interface Page<T> {
  items: T[]
  total: number
  page: number
  size: number
}

// ── the vendor themselves ─────────────────────────────────────────────────

export type VendorStatus = 'pending' | 'under_review' | 'approved' | 'rejected' | 'suspended'

export interface VendorProfile {
  id: string
  legal_name: string
  display_name: string
  contact_email: string
  contact_phone: string
  status: VendorStatus
  gstin: string | null
  /** Masked by the server. The portal has no screen that could show more. */
  pan: string | null
  /** Last four digits only. The full account number never leaves the server. */
  bank_account_last4: string | null
  bank_ifsc: string | null
  commission_bps: number
  approved_at: string | null
  rejection_reason: string | null
  suspension_reason: string | null
  /** The server's answer, not a status comparison the client invents. Two
   *  clients deriving "can they publish?" from `status` is two places to get
   *  it wrong when a sixth status appears. */
  can_publish: boolean
  can_receive_payouts: boolean
}

// ── dashboard and money ───────────────────────────────────────────────────

export interface VendorDashboard {
  live_listings: number
  in_review: number
  awaiting_approval: number
  arrivals_this_week: number
  in_stay: number
  gross_30d_minor: number
  commission_30d_minor: number
  net_30d_minor: number
  reviews_awaiting: number
}

export interface Earnings {
  gross_minor: number
  commission_minor: number
  /** Collected for the government, not earned. Shown so a host can reconcile
   *  their GST filing, and excluded from what they are paid. */
  tax_collected_minor: number
  refunded_minor: number
  net_payable_minor: number
  bookings: number
  nights_sold: number
  average_booking_minor: number
  average_nightly_minor: number
  currency: string
  from_date: string
  to_date: string
}

export interface Occupancy {
  nights_booked: number
  nights_available: number
  /** Across *managed* nights, not across the calendar — the inventory table is
   *  sparse. Every screen that shows this number says so, because a host
   *  comparing it to a hotel's RevPAR is comparing two different things. */
  occupancy_percent: number
}

export interface PropertyPerformance {
  property_id: string
  name: string
  city: string
  status: string
  bookings: number
  gross_minor: number
  nights_sold: number
  review_average: number
  review_count: number
}

export interface MonthlyStatement {
  month: string
  bookings: number
  gross_minor: number
  commission_minor: number
  tax_minor: number
  net_minor: number
}

export interface RevenuePoint {
  day: string
  revenue_minor: number
  bookings: number
}

export interface Reports {
  earnings: Earnings
  occupancy: Occupancy
  by_property: PropertyPerformance[]
  monthly: MonthlyStatement[]
  revenue_by_day: RevenuePoint[]
}

// ── properties and rooms ──────────────────────────────────────────────────

export type PropertyStatus =
  | 'draft'
  | 'pending_review'
  | 'published'
  | 'unpublished'
  | 'rejected'
  | 'suspended'

export interface PropertyImage {
  id: string
  url: string
  caption: string | null
  is_cover: boolean
  position: number
}

export interface RoomType {
  id: string
  name: string
  description: string | null
  bed_type: string | null
  max_adults: number
  max_children: number
  total_units: number
  size_sqft: number | null
  amenity_codes: string[]
  base_rate_minor: number
  currency: string
  min_nights: number
  /** Only meaningful when the caller asked about specific dates. Null on the
   *  management screens, which is why nothing here treats 0 as "sold out". */
  units_available: number | null
}

/**
 * A property, as the server returns it.
 *
 * The same `PropertyResponse` the public site receives, which is deliberate:
 * a host editing a listing should see the object a guest sees, not a
 * host-flavoured projection that can drift from it.
 */
export interface VendorProperty {
  id: string
  slug: string
  name: string
  property_type: string
  status: PropertyStatus
  description: string | null
  address: string | null
  city: string
  state: string
  country_code: string
  latitude: number | null
  longitude: number | null
  location_is_approximate: boolean
  amenity_codes: string[]
  images: PropertyImage[]
  room_types: RoomType[]
  cancellation_policy: string
  check_in_from: string | null
  check_out_by: string | null
  house_rules: string | null
  instant_booking: boolean
  review_average: number
  review_count: number
  currency: string
  vendor_id: string
  published_at: string | null
  /** What the server will refuse to publish without. Rendered verbatim rather
   *  than re-derived here — a client-side checklist drifts from the validation
   *  that actually runs, and the host is the one who finds out. */
  missing_for_publication: string[]
  rejection_reason: string | null
}

export interface ListingChecklist {
  ready: boolean
  missing: string[]
  min_description_chars: number
}

// ── pricing and availability ──────────────────────────────────────────────

/**
 * One night, for one room type.
 *
 * `is_default` marks a night with no stored row — the room's defaults apply.
 * The calendar shows those differently from nights that were set deliberately,
 * because "₹6,000 because I chose it" and "₹6,000 because nobody has touched
 * December" are different facts to a host planning a season.
 */
export interface CalendarDay {
  date: string
  units_total: number
  units_booked: number
  units_available: number
  is_blocked: boolean
  rate_minor: number
  rate_source: string
  min_nights: number
  is_default: boolean
}

export interface Calendar {
  room_type_id: string
  room_type_name: string
  currency: string
  from_date: string
  to_date: string
  days: CalendarDay[]
}

export interface SetRatesRequest {
  from_date: string
  to_date: string
  rate_minor?: number | null
  min_nights?: number | null
  /** Days of the week this applies to, as the server numbers them. Absent
   *  means every day in the range. */
  weekdays?: number[] | null
}

export interface SetAvailabilityRequest {
  from_date: string
  to_date: string
  units_total?: number | null
  is_blocked?: boolean | null
}

// ── bookings ──────────────────────────────────────────────────────────────

export type BookingStatus =
  | 'pending_payment'
  | 'pending_approval'
  | 'confirmed'
  | 'in_stay'
  | 'completed'
  | 'cancelled'
  | 'expired'
  /** Declined by the host. Distinct from `cancelled`, which is a stay that was
   *  agreed and then called off — the guest is told a different thing. */
  | 'rejected'
  | 'no_show'

export interface VendorBooking {
  id: string
  reference: string
  status: BookingStatus
  property_id: string
  property_name: string
  room_type_id: string
  room_type_name: string
  check_in: string
  check_out: string
  nights: number
  adults: number
  children: number
  infants: number
  rooms: number
  guest_name: string
  guest_email: string | null
  guest_phone: string | null
  special_requests: string | null
  accommodation_minor: number
  cleaning_fee_minor: number
  tax_minor: number
  /** The platform's commission, already deducted from what the host is paid.
   *  Shown on the booking rather than only in reports, so the number on the
   *  statement is traceable to the stay that produced it. */
  platform_fee_minor: number
  total_minor: number
  currency: string
  cancellation_policy: string
  created_at: string
  confirmed_at: string | null
  cancelled_at: string | null
  cancellation_reason: string | null
  invoice_number: string | null
}

export interface BookingList {
  items: VendorBooking[]
  total: number
  next_cursor: string | null
}

export interface Arrival {
  booking_id: string
  reference: string
  guest_name: string
  guest_phone: string | null
  property_name: string
  room_type_name: string
  check_in: string
  check_out: string
  guests: number
  status: BookingStatus
  total_minor: number
  currency: string
}

// ── reviews ───────────────────────────────────────────────────────────────

export type ModerationState = 'published' | 'flagged' | 'removed'

export interface Review {
  id: string
  property_id: string
  rating: number
  title: string | null
  body: string
  categories: Record<string, number>
  author_name: string
  published_at: string
  edited_at: string | null
  host_reply: string | null
  host_replied_at: string | null
  moderation: ModerationState
}

export interface ReviewList extends Page<Review> {
  average: number
  distribution: Record<string, number>
}

export interface ReviewSummary {
  total: number
  average: number
  awaiting_reply: number
  /** One and two stars. The number a host should look at first. */
  critical: number
}
