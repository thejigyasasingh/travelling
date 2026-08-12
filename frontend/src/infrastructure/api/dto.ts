/**
 * The wire format, exactly as the API sends it.
 *
 * `snake_case`, mirroring each module's `interface/schemas.py` in the backend.
 * These
 * types stop at this folder: everything above uses the domain types, so a field
 * rename on the server is a change in one mapper rather than a search-and-
 * replace through the components.
 */

export interface ImageDto {
  id: string
  url: string
  position: number
  is_cover: boolean
  alt_text?: string | null
  caption?: string | null
}

export interface RoomTypeDto {
  id: string
  name: string
  description: string | null
  bed_type: string
  max_adults: number
  max_children: number
  total_units: number
  size_sqft: number | null
  amenity_codes: string[]
  base_rate_minor: number
  currency: string
  min_nights: number
  units_available?: number | null
  quote_total_minor?: number | null
}

export interface PropertyDto {
  id: string
  slug: string
  name: string
  property_type: string
  status: string
  description: string
  address: string
  city: string
  state: string | null
  country_code: string
  latitude: number | null
  longitude: number | null
  location_is_approximate: boolean
  amenity_codes: string[]
  images: ImageDto[]
  room_types: RoomTypeDto[]
  cancellation_policy: string
  check_in_from: string
  check_out_by: string
  house_rules: string[]
  instant_booking: boolean
  review_average: number
  review_count: number
  currency: string
  vendor_id: string
}

export interface SearchItemDto {
  id: string
  slug: string
  name: string
  property_type: string
  city: string
  country_code: string
  latitude: number | null
  longitude: number | null
  distance_m: number | null
  cover_image_url: string | null
  review_average: number
  review_count: number
  amenity_codes: string[]
  instant_booking: boolean
  cancellation_policy: string
  max_occupancy: number
  from_price_minor: number | null
  total_price_minor: number | null
  currency: string
  is_available: boolean
}

export interface SearchResponseDto {
  items: SearchItemDto[]
  next_cursor?: string | null
  total_estimate?: number | null
  applied_radius_m?: number | null
}

export interface SuggestionDto {
  kind: 'city' | 'property'
  id: string
  label: string
  sublabel?: string | null
  slug: string
}

export interface AmenityDto {
  code: string
  label: string
  category: string
  icon?: string | null
  is_filterable?: boolean
}

export interface QuoteDto {
  room_type_id: string
  nights: { date: string; amount_minor: number; source: string }[]
  accommodation_minor: number
  extra_guest_minor: number
  cleaning_fee_minor: number
  tax_minor: number
  total_minor: number
  average_nightly_minor: number
  currency: string
  is_available: boolean
  unavailable_dates?: string[]
}

export interface CalendarDayDto {
  date: string
  is_available?: boolean
  is_blocked?: boolean
  units_available?: number | null
  rate_minor?: number | null
  min_nights?: number | null
}

export interface CalendarResponseDto {
  room_type_id: string
  room_type_name: string
  currency: string
  from_date: string
  to_date: string
  days: CalendarDayDto[]
}

export interface BookingRefundDto {
  status: string
  amount_minor: number
  currency: string
  reason?: string | null
  requested_at?: string | null
  completed_at?: string | null
}

export interface BookingDto {
  id: string
  reference: string
  status: string
  property_id: string
  property_name: string
  property_address?: string | null
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
  guest_email: string
  guest_phone: string
  special_requests: string | null
  accommodation_minor: number
  extra_guest_minor: number
  cleaning_fee_minor: number
  tax_minor: number
  platform_fee_minor: number
  total_minor: number
  currency: string
  cancellation_policy: string
  created_at: string | null
  confirmed_at: string | null
  cancelled_at: string | null
  cancelled_by: string | null
  cancellation_reason: string | null
  invoice_number: string | null
  hold_expires_in?: number | null
  nightly_rates?: { date: string; amount_minor: number }[]
  refund?: BookingRefundDto | null
}

export interface BookingListDto {
  items: BookingDto[]
  next_cursor?: string | null
  total?: number | null
}

export interface RefundPreviewDto {
  policy: string
  hours_before_check_in: number
  applied_percent: string
  accommodation_minor: number
  extra_guest_minor: number
  cleaning_fee_minor: number
  tax_minor: number
  platform_fee_minor: number
  total_minor: number
  vendor_retains_minor: number
  reason: string
  currency: string
  cancellable: boolean
}

export interface InvoiceDto {
  number: string
  issued_at: string
  financial_year: string
  booking_reference: string
  supplier_name: string
  supplier_address: string
  supplier_gstin: string | null
  guest_name: string
  guest_email: string
  property_name: string
  check_in: string
  check_out: string
  nights: number
  rooms: number
  lines: {
    description: string
    hsn_sac?: string | null
    quantity: number
    unit_price_minor: number
    amount_minor: number
    tax_rate: string
  }[]
  subtotal_minor: number
  cgst_minor: number
  sgst_minor: number
  igst_minor: number
  tax_total_minor: number
  total_minor: number
  total_in_words: string
  place_of_supply: string
  currency: string
}

export interface CheckoutSessionDto {
  payment_id: string
  gateway_order_id: string
  key_id: string
  amount_minor: number
  currency: string
  booking_reference: string
  prefill_name: string
  prefill_email: string
  prefill_contact: string
  property_name: string
  expires_in?: number | null
  attempt_number?: number
}

export interface PaymentResultDto {
  payment_id: string
  status: string
  booking_id: string
  booking_reference: string
  amount_minor: number
  currency: string
  method: string
  invoice_number?: string | null
  booking_status?: string | null
}

export interface PaymentDto {
  id: string
  status: string
  booking_id: string
  booking_reference: string
  amount_minor: number
  currency: string
  method: string
  instrument?: string | null
  created_at?: string | null
  captured_at?: string | null
  failure_reason?: string | null
  refunded_minor: number
  refundable_minor: number
  net_minor: number
  refunds: {
    id: string
    status: string
    amount_minor: number
    currency: string
    reason: string
    requested_at: string
    completed_at?: string | null
  }[]
  ledger: {
    kind: string
    amount_minor: number
    currency: string
    signed_minor: number
    occurred_at: string
    note?: string | null
  }[]
}

export interface PaymentListDto {
  items: PaymentDto[]
  next_cursor?: string | null
}

export interface UserDto {
  id: string
  email: string
  full_name: string | null
  phone: string | null
  avatar_url: string | null
  status: string
  roles: string[]
  permissions: string[]
  email_verified: boolean
  phone_verified: boolean
  has_password: boolean
  locale: string
  timezone: string
  vendor_id: string | null
  last_login_at: string | null
}

export interface TokenDto {
  access_token: string
  refresh_token: string
  token_type?: string
  expires_in: number
  refresh_expires_in: number
}

export interface AuthResponseDto {
  tokens: TokenDto
  user: UserDto
  is_new_user?: boolean
}

export interface SessionDto {
  id: string
  device_label: string | null
  user_agent: string | null
  created_at: string
  last_used_at: string | null
  expires_at: string
  is_current: boolean
}

export interface OtpChallengeDto {
  challenge_id: string
  expires_in: number
  resend_after?: number
}
