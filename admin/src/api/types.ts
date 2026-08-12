/**
 * The admin API, as it actually responds.
 *
 * Verified against a running server, not read off a schema. The distinction has
 * already cost this project twice.
 */

export interface PageMeta {
  total: number
  page: number
  size: number
  pages: number
}

export interface Paged<T> {
  items: T[]
  meta: PageMeta
}

export interface Kpi {
  key: string
  label: string
  value: number
  /** `null` means no prior data — not "no change". */
  change_percent: number | null
  unit: string
}

export interface TimePoint {
  day: string
  value: number
}

export interface TopProperty {
  property_id: string
  name: string
  city: string
  bookings: number
  revenue_minor: number
  currency: string
}

export interface Dashboard {
  kpis: Kpi[]
  bookings_by_day: TimePoint[]
  revenue_by_day: TimePoint[]
  booking_status_mix: Record<string, number>
  top_properties: TopProperty[]
  action_queue: Record<string, number>
  generated_at: string
}

export interface RevenueBreakdown {
  gross_minor: number
  refunded_minor: number
  net_minor: number
  gateway_fees_minor: number
  platform_commission_minor: number
  vendor_payable_minor: number
  tax_collected_minor: number
  discounts_minor: number
  currency: string
  from_date: string
  to_date: string
}

export interface Analytics {
  revenue: RevenueBreakdown
  bookings_by_day: TimePoint[]
  revenue_by_day: TimePoint[]
  by_city: { city: string; bookings: number; revenue_minor: number }[]
  by_property_type: Record<string, number>
  cancellation_rate: number
  average_booking_value_minor: number
  average_lead_time_days: number
  occupancy_percent: number
  coupon_cost_minor: number
  top_properties: TopProperty[]
}

export interface AdminUser {
  id: string
  email: string
  full_name: string | null
  phone: string | null
  status: string
  roles: string[]
  email_verified: boolean
  created_at: string | null
  last_login_at: string | null
  booking_count: number
  lifetime_value_minor: number
  currency: string
}

export interface AdminProperty {
  id: string
  name: string
  slug: string
  city: string
  property_type: string
  status: string
  vendor_id: string
  vendor_name: string | null
  room_types: number
  review_average: number
  review_count: number
  created_at: string | null
  published_at: string | null
}

export interface AdminBooking {
  id: string
  reference: string
  status: string
  guest_name: string
  guest_email: string
  property_id: string
  property_name: string
  check_in: string
  check_out: string
  nights: number
  total_minor: number
  currency: string
  created_at: string | null
  has_open_ticket: boolean
}

export interface AdminPayment {
  id: string
  booking_reference: string
  status: string
  method: string
  amount_minor: number
  refunded_minor: number
  /** `sum(ledger)` — what the platform actually holds after fees and refunds. */
  net_minor: number
  currency: string
  created_at: string | null
  captured_at: string | null
}

export interface AdminVendor {
  id: string
  legal_name: string
  display_name: string
  contact_email: string
  status: string
  commission_bps: number
  property_count: number
  published_count: number
  gross_bookings_minor: number
  currency: string
  created_at: string | null
  approved_at: string | null
}

export interface VendorDetail extends AdminVendor {
  contact_phone: string
  gstin: string | null
  pan: string | null
  bank_account_last4: string | null
  bank_ifsc: string | null
  rejection_reason: string | null
  suspension_reason: string | null
  can_publish: boolean
  can_receive_payouts: boolean
}

export interface Coupon {
  id: string
  code: string
  description: string
  discount_type: 'percent' | 'flat'
  /** Basis points for a percentage, minor units for a flat amount. */
  value: number
  status: string
  starts_at: string
  ends_at: string
  min_booking_minor: number
  max_discount_minor: number | null
  total_limit: number | null
  per_user_limit: number
  first_booking_only: boolean
  redeemed_count: number
  /** `null` means unlimited, which is different from zero. */
  remaining: number | null
  property_ids: string[]
}

export interface CouponUsage {
  redemptions: number
  released: number
  discount_minor: number
}

export interface TicketMessage {
  id: string
  author_name: string
  body: string
  /** Never shown to the requester. The server filters these out for them. */
  is_internal: boolean
  sent_at: string
}

export interface Ticket {
  id: string
  reference: string
  subject: string
  category: string
  priority: string
  status: string
  requester_name: string
  requester_email: string
  booking_id: string | null
  assigned_to: string | null
  opened_at: string
  first_responded_at: string | null
  resolved_at: string | null
  resolution: string | null
  response_due_at: string
  is_breaching: boolean
  messages: TicketMessage[]
}

export interface TicketPage {
  items: Ticket[]
  total: number
  page: number
  size: number
}

export interface CouponPage {
  items: Coupon[]
  total: number
  page: number
  size: number
}

export interface NotificationRow {
  id: string
  channel: string
  template: string
  recipient: string
  subject: string | null
  preview: string | null
  status: string
  error: string | null
  attempts: number
  created_at: string | null
  sent_at: string | null
}

export interface CurrentUser {
  id: string
  email: string
  full_name: string | null
  roles: string[]
  permissions: string[]
}
