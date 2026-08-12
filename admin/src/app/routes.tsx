import { createBrowserRouter } from 'react-router-dom'
import { RouteErrorBoundary } from './RouteErrorBoundary'
import { Shell } from './Shell'
import { DashboardPage } from '@/pages/DashboardPage'
import {
  BookingsPage,
  NotificationsPage,
  PaymentsPage,
  PropertiesPage,
  UsersPage,
} from '@/pages/lists'
import { VendorsPage } from '@/pages/VendorsPage'
import { CouponsPage } from '@/pages/CouponsPage'
import { TicketsPage } from '@/pages/TicketsPage'
import { AnalyticsPage } from '@/pages/AnalyticsPage'

/**
 * Routes.
 *
 * Not lazily split, unlike the customer app. This is an internal tool loaded
 * once at the start of a shift and used all day; code-splitting would trade a
 * smaller first paint for a spinner every time someone switches section, which
 * is the wrong side of that trade for a tool.
 */
export const router = createBrowserRouter([
  {
    element: <Shell />,
    // On the layout route, so a render error in any page is caught *inside*
    // the shell — the sidebar and the sign-out button survive, and the
    // person can navigate away instead of reaching for the back button.
    errorElement: <RouteErrorBoundary />,
    children: [
      { index: true, element: <DashboardPage /> },
      { path: 'bookings', element: <BookingsPage /> },
      { path: 'payments', element: <PaymentsPage /> },
      { path: 'properties', element: <PropertiesPage /> },
      { path: 'vendors', element: <VendorsPage /> },
      { path: 'users', element: <UsersPage /> },
      { path: 'coupons', element: <CouponsPage /> },
      { path: 'tickets', element: <TicketsPage /> },
      { path: 'notifications', element: <NotificationsPage /> },
      { path: 'analytics', element: <AnalyticsPage /> },
      { path: '*', element: <DashboardPage /> },
    ],
  },
])
