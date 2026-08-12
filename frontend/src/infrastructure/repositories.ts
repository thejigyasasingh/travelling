/**
 * The composition root.
 *
 * One object, assembled once, injected through a React context. Components ask
 * the context for what they need and never import a repository directly — which
 * is what lets a test render a page with three fake methods and no network.
 *
 * `wishlist` is the one entry that switches at runtime: server-backed once
 * there is a session to attach a list to, device-local before that. The choice
 * is made per call rather than at construction, because it changes the moment
 * someone signs in and a repository captured at module load would not notice.
 */

import type { Repositories, WishlistRepository } from '@/application/ports'
import { tokenStore } from '@/infrastructure/http/tokenStore'
import { authRepository } from './api/auth'
import { bookingRepository } from './api/bookings'
import { catalogRepository } from './api/catalog'
import { paymentRepository } from './api/payments'
import { reviewRepository } from './api/reviews'
import { localWishlistRepository, wishlistRepository } from './api/wishlist'

/**
 * Signed in → the server. Signed out → this device.
 *
 * Delegating per call rather than choosing once: the answer changes at
 * sign-in, and a repository resolved at module load would keep writing to
 * localStorage for the rest of the session.
 */
const sessionAwareWishlist: WishlistRepository = {
  list: () => pick().list(),
  add: (entry) => pick().add(entry),
  remove: (propertyId) => pick().remove(propertyId),
  clear: () => pick().clear(),
}

function pick(): WishlistRepository {
  return tokenStore.get() ? wishlistRepository : localWishlistRepository
}

export const repositories: Repositories = {
  catalog: catalogRepository,
  bookings: bookingRepository,
  payments: paymentRepository,
  auth: authRepository,
  reviews: reviewRepository,
  wishlist: sessionAwareWishlist,
}
