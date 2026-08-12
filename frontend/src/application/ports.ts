/**
 * Ports: what the UI needs, stated without saying how.
 *
 * Every hook in `application/hooks` depends on one of these interfaces, never
 * on `fetch` or on a DTO shape. That is what makes the seam real:
 *
 * * a test supplies an object literal, with no MSW and no network;
 * * the wishlist runs on `localStorage` today and on the API when it exists,
 *   with no change above this line;
 * * a DTO field rename is a change in one mapper, not in forty components.
 *
 * The types crossing this boundary are **domain types**, never API DTOs.
 */

import type { IsoDate } from '@/core/dates'
import type {
  Amenity,
  Property,
  Quote,
  SearchResultItem,
  Suggestion,
} from '@/domain/property'
import type { Booking, Invoice, RefundPreview } from '@/domain/booking'
import type { CheckoutSession, Payment, PaymentResult } from '@/domain/payment'
import type { OtpChallenge, Session, User } from '@/domain/user'
import type { Review, ReviewDraft, ReviewSummary } from '@/domain/review'
import type { WishlistEntry } from '@/domain/wishlist'

export interface Page<T> {
  readonly items: readonly T[]
  readonly nextCursor: string | null
  readonly totalEstimate?: number | null
}

// ── search & catalogue ────────────────────────────────────────────────────

export interface SearchCriteria {
  readonly q?: string
  readonly cityId?: string
  readonly lat?: number
  readonly lng?: number
  readonly radiusM?: number
  readonly checkIn?: IsoDate
  readonly checkOut?: IsoDate
  readonly adults?: number
  readonly children?: number
  readonly infants?: number
  readonly rooms?: number
  readonly propertyType?: readonly string[]
  readonly amenity?: readonly string[]
  readonly minPrice?: number
  readonly maxPrice?: number
  readonly minRating?: number
  readonly instantBooking?: boolean
  readonly cancellation?: string
  readonly sort?: SortOption
  readonly limit?: number
  readonly cursor?: string
}

/**
 * A partial update to the criteria, where `undefined` means "clear this".
 * `Partial<T>` is not enough under `exactOptionalPropertyTypes`: it makes a key
 * optional but still forbids explicitly passing `undefined`, which is exactly
 * how a filter gets removed.
 */
export type CriteriaPatch = {
  [K in keyof SearchCriteria]?: SearchCriteria[K] | undefined
}

/**
 * Sort orders, exactly as the API's `SearchSort` spells them — `rating_desc`,
 * not `rating`. An unrecognised value is a 422, and before the server validated
 * these it hung the connection instead: the home page's "top rated" strip was
 * silently empty for that reason.
 */
export type SortOption =
  | 'relevance'
  | 'price_asc'
  | 'price_desc'
  | 'rating_desc'
  | 'distance_asc'
  | 'newest'

export interface SearchPage extends Page<SearchResultItem> {
  readonly appliedRadiusM: number | null
}

export interface CatalogRepository {
  search(criteria: SearchCriteria, signal?: AbortSignal): Promise<SearchPage>
  suggest(query: string, signal?: AbortSignal): Promise<readonly Suggestion[]>
  /** Accepts an id or a slug — the URL carries the slug, deep links carry ids. */
  property(identifier: string, signal?: AbortSignal): Promise<Property>
  availability(
    propertyId: string,
    range: { from: IsoDate; to: IsoDate },
    signal?: AbortSignal,
  ): Promise<readonly { date: IsoDate; isAvailable: boolean; rateMinor: number | null }[]>
  quote(
    propertyId: string,
    input: {
      roomTypeId?: string
      checkIn: IsoDate
      checkOut: IsoDate
      adults: number
      children?: number
      infants?: number
      rooms?: number
    },
    signal?: AbortSignal,
  ): Promise<Quote>
  amenities(signal?: AbortSignal): Promise<readonly Amenity[]>
}

// ── bookings ──────────────────────────────────────────────────────────────

export interface CreateBookingInput {
  readonly propertyId: string
  readonly roomTypeId: string
  readonly checkIn: IsoDate
  readonly checkOut: IsoDate
  readonly adults: number
  readonly children: number
  readonly infants: number
  readonly rooms: number
  readonly guestName: string
  readonly guestEmail: string
  readonly guestPhone: string
  readonly specialRequests?: string
  /**
   * The total the guest was shown. The server re-prices and rejects a
   * mismatch with 409 rather than silently charging a different amount.
   */
  readonly quotedTotalMinor: number
}

export interface BookingRepository {
  /**
   * `idempotencyKey` is required, not optional. A double-clicked "Reserve" is
   * two rooms held and one of them abandoned; the key is what makes the second
   * click return the first booking.
   */
  create(input: CreateBookingInput, idempotencyKey: string): Promise<Booking>
  get(identifier: string, signal?: AbortSignal): Promise<Booking>
  list(
    filter: { status?: string; upcoming?: boolean; limit?: number; cursor?: string },
    signal?: AbortSignal,
  ): Promise<Page<Booking>>
  refundPreview(bookingId: string, signal?: AbortSignal): Promise<RefundPreview>
  cancel(bookingId: string, reason?: string): Promise<Booking>
  invoice(bookingId: string, signal?: AbortSignal): Promise<Invoice>
}

// ── payments ──────────────────────────────────────────────────────────────

export interface PaymentRepository {
  createOrder(bookingId: string): Promise<CheckoutSession>
  verify(input: {
    razorpayOrderId: string
    razorpayPaymentId: string
    razorpaySignature: string
  }): Promise<PaymentResult>
  retry(bookingId: string): Promise<PaymentResult>
  list(filter: { limit?: number; cursor?: string }, signal?: AbortSignal): Promise<Page<Payment>>
  get(paymentId: string, signal?: AbortSignal): Promise<Payment>
}

// ── auth ──────────────────────────────────────────────────────────────────

export interface AuthResult {
  readonly user: User
  readonly accessToken: string
  readonly expiresIn: number
  readonly isNewUser: boolean
}

/**
 * Registration does **not** sign you in. The endpoint answers 202 with the same
 * message whether or not the address was already registered — saying otherwise
 * would make it a membership oracle for a leaked email list. The difference
 * goes to the inbox, and the user signs in after verifying.
 */
export interface RegistrationResult {
  readonly message: string
  readonly detail: string | null
}

export interface AuthRepository {
  register(input: {
    email: string
    password: string
    fullName?: string
  }): Promise<RegistrationResult>
  login(input: { email: string; password: string; deviceLabel?: string }): Promise<AuthResult>
  loginWithGoogle(input: { idToken: string; nonce?: string }): Promise<AuthResult>
  requestOtp(input: { phone: string; purpose?: 'login' | 'link_phone' }): Promise<OtpChallenge>
  verifyOtp(input: { challengeId: string; code: string }): Promise<AuthResult>
  logout(allDevices?: boolean): Promise<void>
  me(signal?: AbortSignal): Promise<User>
  forgotPassword(email: string): Promise<void>
  resetPassword(input: { token: string; newPassword: string }): Promise<void>
  changePassword(input: { currentPassword: string; newPassword: string }): Promise<void>
  verifyEmail(token: string): Promise<void>
  resendVerification(): Promise<void>
  sessions(signal?: AbortSignal): Promise<readonly Session[]>
  revokeSession(sessionId: string): Promise<void>
}

// ── reviews & wishlist ────────────────────────────────────────────────────

export interface ReviewRepository {
  forProperty(
    propertyId: string,
    filter: { limit?: number; cursor?: string; sort?: string },
    signal?: AbortSignal,
  ): Promise<Page<Review> & { summary: ReviewSummary }>
  mine(signal?: AbortSignal): Promise<readonly Review[]>
  submit(draft: ReviewDraft): Promise<Review>
  /** Within 48 hours, and only until the host replies. Both windows are the
   *  server's to enforce; this just carries the request. */
  edit(reviewId: string, draft: ReviewDraft): Promise<Review>
}

export interface WishlistRepository {
  list(): Promise<readonly WishlistEntry[]>
  add(entry: WishlistEntry): Promise<void>
  remove(propertyId: string): Promise<void>
  clear(): Promise<void>
}

/** Everything the app needs from the outside world, in one object. */
export interface Repositories {
  readonly catalog: CatalogRepository
  readonly bookings: BookingRepository
  readonly payments: PaymentRepository
  readonly auth: AuthRepository
  readonly reviews: ReviewRepository
  readonly wishlist: WishlistRepository
}
