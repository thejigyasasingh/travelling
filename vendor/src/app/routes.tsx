import { createBrowserRouter } from 'react-router-dom'
import { RouteErrorBoundary } from './RouteErrorBoundary'
import { Shell } from './Shell'
import { OverviewPage } from '@/pages/OverviewPage'
import { PropertiesPage, PropertyDetailPage } from '@/pages/PropertiesPage'
import { CalendarPage } from '@/pages/CalendarPage'
import { BookingsPage } from '@/pages/BookingsPage'
import { ReviewsPage } from '@/pages/ReviewsPage'
import { RevenuePage } from '@/pages/RevenuePage'
import { ReportsPage } from '@/pages/ReportsPage'

/**
 * Routes.
 *
 * Not lazily split, like the admin panel and unlike the customer site. A host
 * opens this and works through several sections in one sitting; code-splitting
 * would trade a slightly faster first paint for a spinner on every switch,
 * which is the wrong side of that trade for a tool.
 */
export const router = createBrowserRouter([
  {
    element: <Shell />,
    // On the layout route, so a render error in any page is caught *inside*
    // the shell — the sidebar and the sign-out button survive, and the
    // person can navigate away instead of reaching for the back button.
    errorElement: <RouteErrorBoundary />,
    children: [
      { index: true, element: <OverviewPage /> },
      { path: 'properties', element: <PropertiesPage /> },
      { path: 'properties/:propertyId', element: <PropertyDetailPage /> },
      { path: 'calendar', element: <CalendarPage /> },
      { path: 'bookings', element: <BookingsPage /> },
      { path: 'reviews', element: <ReviewsPage /> },
      { path: 'revenue', element: <RevenuePage /> },
      { path: 'reports', element: <ReportsPage /> },
      { path: '*', element: <OverviewPage /> },
    ],
  },
])
