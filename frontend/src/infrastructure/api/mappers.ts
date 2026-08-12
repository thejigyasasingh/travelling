/**
 * DTO → domain.
 *
 * The whole boundary lives here. Two rules it follows:
 *
 * * **Optional-on-the-wire becomes explicit-in-the-domain.** `hold_expires_in?`
 *   becomes `holdExpiresIn: number | null`, so a component never has to
 *   distinguish "absent" from "null" — a distinction that means nothing to a UI
 *   and produces `undefined` rendering bugs.
 * * **No defaulting that invents data.** A missing price stays `null` and
 *   renders as "—". A `?? 0` here would show "₹0" for "we do not know", which
 *   is worse than an em dash.
 */

import type { Booking, BookingStatus, Invoice, RefundPreview } from '@/domain/booking'
import type { CheckoutSession, Payment, PaymentResult, PaymentStatus } from '@/domain/payment'
import type {
  Amenity,
  Property,
  PropertyImage,
  Quote,
  RoomType,
  SearchResultItem,
  Suggestion,
} from '@/domain/property'
import type { OtpChallenge, Session, User } from '@/domain/user'
import type * as dto from './dto'

export function toImage(d: dto.ImageDto): PropertyImage {
  return {
    id: d.id,
    url: d.url,
    position: d.position,
    isCover: d.is_cover,
    altText: d.alt_text ?? null,
    caption: d.caption ?? null,
  }
}

export function toRoomType(d: dto.RoomTypeDto): RoomType {
  return {
    id: d.id,
    name: d.name,
    description: d.description,
    bedType: d.bed_type,
    maxAdults: d.max_adults,
    maxChildren: d.max_children,
    totalUnits: d.total_units,
    sizeSqft: d.size_sqft,
    amenityCodes: d.amenity_codes,
    baseRateMinor: d.base_rate_minor,
    currency: d.currency,
    minNights: d.min_nights,
    unitsAvailable: d.units_available ?? null,
    quoteTotalMinor: d.quote_total_minor ?? null,
  }
}

export function toProperty(d: dto.PropertyDto): Property {
  return {
    id: d.id,
    slug: d.slug,
    name: d.name,
    propertyType: d.property_type,
    description: d.description,
    address: d.address,
    city: d.city,
    state: d.state,
    countryCode: d.country_code,
    latitude: d.latitude,
    longitude: d.longitude,
    locationIsApproximate: d.location_is_approximate,
    amenityCodes: d.amenity_codes,
    images: [...d.images].sort((a, b) => a.position - b.position).map(toImage),
    roomTypes: d.room_types.map(toRoomType),
    cancellationPolicy: d.cancellation_policy,
    checkInFrom: d.check_in_from,
    checkOutBy: d.check_out_by,
    houseRules: d.house_rules,
    instantBooking: d.instant_booking,
    reviewAverage: d.review_average,
    reviewCount: d.review_count,
    currency: d.currency,
    vendorId: d.vendor_id,
  }
}

export function toSearchItem(d: dto.SearchItemDto): SearchResultItem {
  return {
    id: d.id,
    slug: d.slug,
    name: d.name,
    propertyType: d.property_type,
    city: d.city,
    countryCode: d.country_code,
    latitude: d.latitude,
    longitude: d.longitude,
    distanceM: d.distance_m,
    coverImageUrl: d.cover_image_url,
    reviewAverage: d.review_average,
    reviewCount: d.review_count,
    amenityCodes: d.amenity_codes,
    instantBooking: d.instant_booking,
    cancellationPolicy: d.cancellation_policy,
    maxOccupancy: d.max_occupancy,
    fromPriceMinor: d.from_price_minor,
    totalPriceMinor: d.total_price_minor,
    currency: d.currency,
    isAvailable: d.is_available,
  }
}

export function toSuggestion(d: dto.SuggestionDto): Suggestion {
  return { kind: d.kind, id: d.id, label: d.label, sublabel: d.sublabel ?? null, slug: d.slug }
}

export function toAmenity(d: dto.AmenityDto): Amenity {
  return {
    code: d.code,
    label: d.label,
    category: d.category,
    icon: d.icon ?? null,
    isFilterable: d.is_filterable ?? true,
  }
}

export function toQuote(d: dto.QuoteDto): Quote {
  return {
    roomTypeId: d.room_type_id,
    nights: d.nights.map((n) => ({
      date: n.date,
      amountMinor: n.amount_minor,
      source: n.source,
    })),
    accommodationMinor: d.accommodation_minor,
    extraGuestMinor: d.extra_guest_minor,
    cleaningFeeMinor: d.cleaning_fee_minor,
    taxMinor: d.tax_minor,
    totalMinor: d.total_minor,
    averageNightlyMinor: d.average_nightly_minor,
    currency: d.currency,
    isAvailable: d.is_available,
    unavailableDates: (d.unavailable_dates ?? []),
  }
}

export function toBooking(d: dto.BookingDto): Booking {
  return {
    id: d.id,
    reference: d.reference,
    status: d.status as BookingStatus,
    propertyId: d.property_id,
    propertyName: d.property_name,
    propertyAddress: d.property_address ?? null,
    roomTypeId: d.room_type_id,
    roomTypeName: d.room_type_name,
    checkIn: d.check_in,
    checkOut: d.check_out,
    nights: d.nights,
    adults: d.adults,
    children: d.children,
    infants: d.infants,
    rooms: d.rooms,
    guestName: d.guest_name,
    guestEmail: d.guest_email,
    guestPhone: d.guest_phone,
    specialRequests: d.special_requests,
    accommodationMinor: d.accommodation_minor,
    extraGuestMinor: d.extra_guest_minor,
    cleaningFeeMinor: d.cleaning_fee_minor,
    taxMinor: d.tax_minor,
    platformFeeMinor: d.platform_fee_minor,
    totalMinor: d.total_minor,
    currency: d.currency,
    cancellationPolicy: d.cancellation_policy,
    createdAt: d.created_at,
    confirmedAt: d.confirmed_at,
    cancelledAt: d.cancelled_at,
    cancelledBy: d.cancelled_by,
    cancellationReason: d.cancellation_reason,
    invoiceNumber: d.invoice_number,
    holdExpiresIn: d.hold_expires_in ?? null,
    nightlyRates: (d.nightly_rates ?? []).map((r) => ({
      date: r.date,
      amountMinor: r.amount_minor,
    })),
    refund: d.refund
      ? {
          status: d.refund.status,
          amountMinor: d.refund.amount_minor,
          currency: d.refund.currency,
          reason: d.refund.reason ?? null,
          requestedAt: d.refund.requested_at ?? null,
          completedAt: d.refund.completed_at ?? null,
        }
      : null,
  }
}

export function toRefundPreview(d: dto.RefundPreviewDto): RefundPreview {
  return {
    policy: d.policy,
    hoursBeforeCheckIn: d.hours_before_check_in,
    appliedPercent: d.applied_percent,
    accommodationMinor: d.accommodation_minor,
    extraGuestMinor: d.extra_guest_minor,
    cleaningFeeMinor: d.cleaning_fee_minor,
    taxMinor: d.tax_minor,
    platformFeeMinor: d.platform_fee_minor,
    totalMinor: d.total_minor,
    vendorRetainsMinor: d.vendor_retains_minor,
    reason: d.reason,
    currency: d.currency,
    cancellable: d.cancellable,
  }
}

export function toInvoice(d: dto.InvoiceDto): Invoice {
  return {
    number: d.number,
    issuedAt: d.issued_at,
    financialYear: d.financial_year,
    bookingReference: d.booking_reference,
    supplierName: d.supplier_name,
    supplierAddress: d.supplier_address,
    supplierGstin: d.supplier_gstin,
    guestName: d.guest_name,
    guestEmail: d.guest_email,
    propertyName: d.property_name,
    checkIn: d.check_in,
    checkOut: d.check_out,
    nights: d.nights,
    rooms: d.rooms,
    lines: d.lines.map((l) => ({
      description: l.description,
      hsnSac: l.hsn_sac ?? null,
      quantity: l.quantity,
      unitPriceMinor: l.unit_price_minor,
      amountMinor: l.amount_minor,
      taxRate: l.tax_rate,
    })),
    subtotalMinor: d.subtotal_minor,
    cgstMinor: d.cgst_minor,
    sgstMinor: d.sgst_minor,
    igstMinor: d.igst_minor,
    taxTotalMinor: d.tax_total_minor,
    totalMinor: d.total_minor,
    totalInWords: d.total_in_words,
    placeOfSupply: d.place_of_supply,
    currency: d.currency,
  }
}

export function toCheckoutSession(d: dto.CheckoutSessionDto): CheckoutSession {
  return {
    paymentId: d.payment_id,
    gatewayOrderId: d.gateway_order_id,
    keyId: d.key_id,
    amountMinor: d.amount_minor,
    currency: d.currency,
    bookingReference: d.booking_reference,
    prefillName: d.prefill_name,
    prefillEmail: d.prefill_email,
    prefillContact: d.prefill_contact,
    propertyName: d.property_name,
    expiresIn: d.expires_in ?? null,
    attemptNumber: d.attempt_number ?? 1,
  }
}

export function toPaymentResult(d: dto.PaymentResultDto): PaymentResult {
  return {
    paymentId: d.payment_id,
    status: d.status,
    bookingId: d.booking_id,
    bookingReference: d.booking_reference,
    amountMinor: d.amount_minor,
    currency: d.currency,
    method: d.method,
    invoiceNumber: d.invoice_number ?? null,
    bookingStatus: d.booking_status ?? null,
  }
}

export function toPayment(d: dto.PaymentDto): Payment {
  return {
    id: d.id,
    status: d.status as PaymentStatus,
    bookingId: d.booking_id,
    bookingReference: d.booking_reference,
    amountMinor: d.amount_minor,
    currency: d.currency,
    method: d.method,
    instrument: d.instrument ?? null,
    createdAt: d.created_at ?? null,
    capturedAt: d.captured_at ?? null,
    failureReason: d.failure_reason ?? null,
    refundedMinor: d.refunded_minor,
    refundableMinor: d.refundable_minor,
    netMinor: d.net_minor,
    refunds: d.refunds.map((r) => ({
      id: r.id,
      status: r.status,
      amountMinor: r.amount_minor,
      currency: r.currency,
      reason: r.reason,
      requestedAt: r.requested_at,
      completedAt: r.completed_at ?? null,
    })),
    ledger: d.ledger.map((e) => ({
      kind: e.kind,
      amountMinor: e.amount_minor,
      currency: e.currency,
      signedMinor: e.signed_minor,
      occurredAt: e.occurred_at,
      note: e.note ?? null,
    })),
  }
}

export function toUser(d: dto.UserDto): User {
  return {
    id: d.id,
    email: d.email,
    fullName: d.full_name,
    phone: d.phone,
    avatarUrl: d.avatar_url,
    status: d.status,
    roles: d.roles,
    permissions: d.permissions,
    emailVerified: d.email_verified,
    phoneVerified: d.phone_verified,
    hasPassword: d.has_password,
    locale: d.locale,
    timezone: d.timezone,
    vendorId: d.vendor_id,
    lastLoginAt: d.last_login_at,
  }
}

export function toSession(d: dto.SessionDto): Session {
  return {
    id: d.id,
    deviceLabel: d.device_label,
    userAgent: d.user_agent,
    createdAt: d.created_at,
    lastUsedAt: d.last_used_at,
    expiresAt: d.expires_at,
    isCurrent: d.is_current,
  }
}

export function toOtpChallenge(d: dto.OtpChallengeDto): OtpChallenge {
  return {
    challengeId: d.challenge_id,
    expiresIn: d.expires_in,
    resendAfter: d.resend_after ?? 30,
  }
}
