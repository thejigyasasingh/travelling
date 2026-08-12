import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:riverpod_annotation/riverpod_annotation.dart';

import '../../features/auth/presentation/providers/auth_provider.dart';
import '../../features/auth/presentation/screens/login_screen.dart';
import '../../features/auth/presentation/screens/register_screen.dart';
import '../../features/booking/presentation/screens/booking_form_screen.dart';
import '../../features/booking/presentation/screens/checkout_screen.dart';
import '../../features/booking/presentation/screens/trip_detail_screen.dart';
import '../../features/booking/presentation/screens/trips_screen.dart';
import '../../features/catalog/presentation/screens/home_screen.dart';
import '../../features/catalog/presentation/screens/property_screen.dart';
import '../../features/catalog/presentation/screens/search_screen.dart';
import '../../features/account/presentation/screens/account_screen.dart';
import '../../features/wishlist/presentation/screens/wishlist_screen.dart';
import '../../shared/widgets/app_shell.dart';

part 'app_router.g.dart';

/// Route paths, as constants.
///
/// Typed accessors rather than scattered string literals: a typo in
/// `context.go('/tripz')` is a silent no-op at runtime, and this makes it a
/// compile error.
abstract final class Routes {
  static const home = '/';
  static const search = '/search';
  static const wishlist = '/wishlist';
  static const trips = '/trips';
  static const account = '/account';

  static const login = '/login';
  static const register = '/register';

  static String property(String slug) => '/stays/$slug';
  static String booking(String propertyId) => '/book/$propertyId';
  static String checkout(String bookingId) => '/checkout/$bookingId';
  static String trip(String bookingId) => '/trips/$bookingId';
}

/// The router.
///
/// The redirect is the load-bearing part. It has to distinguish three states,
/// not two: signed in, signed out, and **still restoring**. Treating "restoring"
/// as signed-out flashes the sign-in screen at a signed-in user on every cold
/// start — a bug that only appears on a real device, because in development the
/// token exchange is instant.
@Riverpod(keepAlive: true)
GoRouter appRouter(Ref ref) {
  final navigatorKey = GlobalKey<NavigatorState>();

  return GoRouter(
    navigatorKey: navigatorKey,
    initialLocation: Routes.home,
    debugLogDiagnostics: false,
    // Rebuilds the redirect when auth changes, so a session lost in the
    // background moves the user off a protected screen without a manual push.
    refreshListenable: _AuthListenable(ref),
    redirect: (context, state) {
      final auth = ref.read(authProvider);
      final location = state.matchedLocation;
      final isAuthRoute =
          location == Routes.login || location == Routes.register;

      // Still exchanging the stored refresh token. Stay put; the listenable
      // fires again the moment it resolves.
      if (auth is AuthRestoring) return null;

      final signedIn = auth is Authenticated;

      if (!signedIn && _requiresAuth(location)) {
        // `from` is carried so the user lands where they were going, not on
        // the home screen having forgotten why they signed in.
        return '${Routes.login}?from=${Uri.encodeComponent(state.uri.toString())}';
      }

      if (signedIn && isAuthRoute) {
        final from = state.uri.queryParameters['from'];
        return _safeRedirect(from) ?? Routes.home;
      }

      return null;
    },
    routes: [
      // The tabbed shell. A StatefulShellRoute keeps a separate navigator per
      // tab, so switching tabs preserves each one's scroll position and stack —
      // which is what people expect and what a single navigator cannot do.
      StatefulShellRoute.indexedStack(
        builder: (context, state, shell) => AppShell(shell: shell),
        branches: [
          StatefulShellBranch(
            routes: [
              GoRoute(
                path: Routes.home,
                builder: (context, state) => const HomeScreen(),
                routes: [
                  GoRoute(
                    path: 'stays/:slug',
                    builder: (context, state) => PropertyScreen(
                      identifier: state.pathParameters['slug']!,
                    ),
                  ),
                ],
              ),
            ],
          ),
          StatefulShellBranch(
            routes: [
              GoRoute(
                path: Routes.search,
                builder: (context, state) => const SearchScreen(),
              ),
            ],
          ),
          StatefulShellBranch(
            routes: [
              GoRoute(
                path: Routes.wishlist,
                builder: (context, state) => const WishlistScreen(),
              ),
            ],
          ),
          StatefulShellBranch(
            routes: [
              GoRoute(
                path: Routes.trips,
                builder: (context, state) => const TripsScreen(),
                routes: [
                  GoRoute(
                    path: ':bookingId',
                    builder: (context, state) => TripDetailScreen(
                      bookingId: state.pathParameters['bookingId']!,
                    ),
                  ),
                ],
              ),
            ],
          ),
          StatefulShellBranch(
            routes: [
              GoRoute(
                path: Routes.account,
                builder: (context, state) => const AccountScreen(),
              ),
            ],
          ),
        ],
      ),

      // Full-screen routes, outside the tab shell: booking and checkout are
      // focused flows, and a tab bar inviting someone to wander off mid-payment
      // is how a held room lapses.
      GoRoute(
        path: '/book/:propertyId',
        parentNavigatorKey: navigatorKey,
        builder: (context, state) => BookingFormScreen(
          propertyId: state.pathParameters['propertyId']!,
          roomTypeId: state.uri.queryParameters['room'] ?? '',
          checkIn: state.uri.queryParameters['check_in'] ?? '',
          checkOut: state.uri.queryParameters['check_out'] ?? '',
          adults: int.tryParse(state.uri.queryParameters['adults'] ?? '') ?? 2,
          children: int.tryParse(state.uri.queryParameters['children'] ?? '') ?? 0,
          rooms: int.tryParse(state.uri.queryParameters['rooms'] ?? '') ?? 1,
        ),
      ),
      GoRoute(
        path: '/checkout/:bookingId',
        parentNavigatorKey: navigatorKey,
        builder: (context, state) => CheckoutScreen(
          bookingId: state.pathParameters['bookingId']!,
        ),
      ),
      GoRoute(
        path: Routes.login,
        parentNavigatorKey: navigatorKey,
        builder: (context, state) => LoginScreen(
          redirectTo: _safeRedirect(state.uri.queryParameters['from']),
        ),
      ),
      GoRoute(
        path: Routes.register,
        parentNavigatorKey: navigatorKey,
        builder: (context, state) => const RegisterScreen(),
      ),
    ],
    errorBuilder: (context, state) => _RouteNotFound(error: state.error),
  );
}

bool _requiresAuth(String location) =>
    location.startsWith(Routes.trips) ||
    location.startsWith(Routes.account) ||
    location.startsWith('/book/') ||
    location.startsWith('/checkout/');

/// Only in-app paths are honoured after sign-in.
///
/// An open redirect is a phishing primitive even on mobile: a deep link
/// carrying `from=https://evil.example` would send a freshly authenticated user
/// straight out of the app.
String? _safeRedirect(String? raw) {
  if (raw == null || raw.isEmpty) return null;
  final decoded = Uri.decodeComponent(raw);
  if (!decoded.startsWith('/') || decoded.startsWith('//')) return null;
  return decoded;
}

/// Bridges Riverpod's auth state to GoRouter's [Listenable].
class _AuthListenable extends ChangeNotifier {
  _AuthListenable(Ref ref) {
    _subscription = ref.listen(
      authProvider,
      (_, _) => notifyListeners(),
      fireImmediately: false,
    );
  }

  late final ProviderSubscription<AuthState> _subscription;

  @override
  void dispose() {
    _subscription.close();
    super.dispose();
  }
}

class _RouteNotFound extends StatelessWidget {
  const _RouteNotFound({this.error});

  final Exception? error;

  @override
  Widget build(BuildContext context) => Scaffold(
        appBar: AppBar(title: const Text('Not found')),
        body: Center(
          child: Padding(
            padding: const EdgeInsets.all(32),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                const Icon(Icons.explore_off_rounded, size: 48),
                const SizedBox(height: 16),
                Text(
                  'We could not find that page',
                  style: Theme.of(context).textTheme.titleMedium,
                ),
                const SizedBox(height: 8),
                const Text(
                  'The link may be old, or the stay may no longer be listed.',
                  textAlign: TextAlign.center,
                ),
                const SizedBox(height: 24),
                FilledButton(
                  onPressed: () => context.go(Routes.home),
                  child: const Text('Go home'),
                ),
              ],
            ),
          ),
        ),
      );
}
