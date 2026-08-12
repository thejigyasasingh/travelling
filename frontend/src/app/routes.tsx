/**
 * Routes.
 *
 * Everything below the two entry pages is lazily loaded. The split is chosen by
 * journey, not by file size: a first-time visitor lands on Home and searches,
 * and should not download the checkout flow, the invoice renderer or the
 * account screens to do it.
 */

import { lazy } from 'react'
import { createBrowserRouter, Navigate } from 'react-router-dom'
import { Layout } from './Layout'
import { RequireAuth } from './RequireAuth'
import { RouteErrorBoundary } from './RouteErrorBoundary'
import HomePage from '@/pages/HomePage'
import SearchPage from '@/pages/SearchPage'

const PropertyPage = lazy(() => import('@/pages/PropertyPage'))
const BookingPage = lazy(() => import('@/pages/BookingPage'))
const CheckoutPage = lazy(() => import('@/pages/CheckoutPage'))
const BookingConfirmationPage = lazy(() => import('@/pages/BookingConfirmationPage'))
const WishlistPage = lazy(() => import('@/pages/WishlistPage'))
const TripsPage = lazy(() => import('@/pages/TripsPage'))
const TripDetailPage = lazy(() => import('@/pages/TripDetailPage'))
const LoginPage = lazy(() => import('@/pages/LoginPage'))
const RegisterPage = lazy(() => import('@/pages/RegisterPage'))
const ForgotPasswordPage = lazy(() => import('@/pages/ForgotPasswordPage'))
const ResetPasswordPage = lazy(() => import('@/pages/ResetPasswordPage'))
const VerifyEmailPage = lazy(() => import('@/pages/VerifyEmailPage'))
const ProfilePage = lazy(() => import('@/pages/ProfilePage'))
const SettingsPage = lazy(() => import('@/pages/SettingsPage'))
const ReviewsPage = lazy(() => import('@/pages/ReviewsPage'))
const WriteReviewPage = lazy(() => import('@/pages/WriteReviewPage'))
const NotFoundPage = lazy(() => import('@/pages/NotFoundPage'))

export const router = createBrowserRouter([
  {
    element: <Layout />,
    errorElement: <RouteErrorBoundary />,
    children: [
      { index: true, element: <HomePage /> },
      { path: 'search', element: <SearchPage /> },
      // Slug-based, because a URL a guest sends a friend should say where it
      // goes. The endpoint accepts an id too, so old links keep working.
      { path: 'stays/:slug', element: <PropertyPage /> },
      { path: 'stays/:slug/reviews', element: <ReviewsPage /> },

      // Booking → checkout → confirmation. Auth-gated: a booking belongs to
      // someone, and collecting guest details before sign-in only to lose them
      // at the gate is the worst version of this flow.
      {
        element: <RequireAuth />,
        children: [
          { path: 'book/:propertyId', element: <BookingPage /> },
          { path: 'checkout/:bookingId', element: <CheckoutPage /> },
          { path: 'bookings/:bookingId/confirmed', element: <BookingConfirmationPage /> },
          { path: 'trips', element: <TripsPage /> },
          { path: 'trips/:bookingId', element: <TripDetailPage /> },
          { path: 'trips/:bookingId/review', element: <WriteReviewPage /> },
          { path: 'profile', element: <ProfilePage /> },
          { path: 'settings', element: <SettingsPage /> },
        ],
      },

      // The wishlist works signed out — it is on this device today, and asking
      // someone to sign in before they can save a stay loses the save.
      { path: 'wishlist', element: <WishlistPage /> },

      { path: 'login', element: <LoginPage /> },
      { path: 'register', element: <RegisterPage /> },
      { path: 'forgot-password', element: <ForgotPasswordPage /> },
      { path: 'reset-password', element: <ResetPasswordPage /> },
      { path: 'verify-email', element: <VerifyEmailPage /> },

      { path: 'property/:slug', element: <Navigate to="/stays/:slug" replace /> },
      { path: '*', element: <NotFoundPage /> },
    ],
  },
])
