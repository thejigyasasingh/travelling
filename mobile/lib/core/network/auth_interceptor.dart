import 'dart:async';

import 'package:dio/dio.dart';

import '../storage/token_store.dart';

/// Attaches the access token, and renews it exactly once when it expires.
///
/// **The single-flight refresh is the load-bearing part.** A screen typically
/// fires several requests at once — the property, its availability, the
/// wishlist. If the access token has expired they all get 401 together, and a
/// naive interceptor would fire one refresh per request. The backend *rotates*
/// refresh tokens and treats reuse as theft: it revokes the whole family and
/// signs the user out of every device. So concurrent refreshes do not merely
/// waste requests — they log the user out.
///
/// Hence: one `Completer`, shared. Whoever arrives first performs the refresh;
/// everyone else awaits the same future and then retries once.
///
/// The refresh call deliberately uses a **separate Dio instance**. Sending it
/// through the same client would run it back through this interceptor, and a
/// 401 on the refresh itself would recurse.
class AuthInterceptor extends Interceptor {
  AuthInterceptor({
    required TokenStorage tokenStore,
    required Dio refreshClient,
    required Future<void> Function() onSessionLost,
  })  : _tokens = tokenStore,
        _refreshClient = refreshClient,
        _onSessionLost = onSessionLost;

  final TokenStorage _tokens;
  final Dio _refreshClient;
  final Future<void> Function() _onSessionLost;

  Completer<bool>? _refreshInFlight;

  /// Endpoints that must never carry a token or trigger a refresh: they are how
  /// a token is obtained in the first place.
  static const _anonymousPaths = {
    '/auth/login',
    '/auth/register',
    '/auth/refresh',
    '/auth/google',
    '/auth/otp/request',
    '/auth/otp/verify',
    '/auth/password/forgot',
    '/auth/password/reset',
    '/auth/email/verify',
  };

  static bool _isAnonymous(RequestOptions options) =>
      _anonymousPaths.any((p) => options.path.endsWith(p));

  @override
  Future<void> onRequest(
    RequestOptions options,
    RequestInterceptorHandler handler,
  ) async {
    if (_isAnonymous(options)) return handler.next(options);

    // Refresh *before* sending when the token is about to expire, so the common
    // case never spends a round trip being told what we already knew.
    if (_tokens.isAccessTokenExpiring) {
      await _refreshOnce();
    }

    final token = _tokens.accessToken;
    if (token != null) {
      options.headers['Authorization'] = 'Bearer $token';
    }
    handler.next(options);
  }

  @override
  Future<void> onError(
    DioException err,
    ErrorInterceptorHandler handler,
  ) async {
    final response = err.response;
    final options = err.requestOptions;

    final shouldTry = response?.statusCode == 401 &&
        !_isAnonymous(options) &&
        options.extra['rw_retried'] != true;

    if (!shouldTry) return handler.next(err);

    final refreshed = await _refreshOnce();
    if (!refreshed) {
      await _onSessionLost();
      return handler.next(err);
    }

    try {
      // Marked so a second 401 on the replay falls through instead of looping.
      options.extra['rw_retried'] = true;
      options.headers['Authorization'] = 'Bearer ${_tokens.accessToken}';
      final retried = await _refreshClient.fetch<dynamic>(options);
      return handler.resolve(retried);
    } on DioException catch (retryError) {
      return handler.next(retryError);
    }
  }

  /// Refresh, or join the refresh already running.
  Future<bool> _refreshOnce() {
    final existing = _refreshInFlight;
    if (existing != null) return existing.future;

    final completer = Completer<bool>();
    _refreshInFlight = completer;

    unawaited(
      _performRefresh().then((ok) {
        _refreshInFlight = null;
        completer.complete(ok);
      }).catchError((Object _) {
        _refreshInFlight = null;
        completer.complete(false);
      }),
    );

    return completer.future;
  }

  Future<bool> _performRefresh() async {
    final refreshToken = await _tokens.readRefreshToken();
    if (refreshToken == null) return false;

    try {
      final response = await _refreshClient.post<Map<String, dynamic>>(
        '/auth/refresh',
        data: {'refresh_token': refreshToken},
      );

      // The endpoint answers with the whole auth response — `{tokens, user}` —
      // not a bare token. Reading `access_token` off the top level yields null,
      // and the failure is silent: every later request carries `Bearer null`
      // while the app still believes it is signed in.
      final tokens = response.data?['tokens'] as Map<String, dynamic>?;
      final access = tokens?['access_token'] as String?;
      final refresh = tokens?['refresh_token'] as String?;
      if (access == null || refresh == null) return false;

      await _tokens.save(
        accessToken: access,
        // Rotated: the server issues a new refresh token every time and
        // invalidates the old one. Storing the old one would present a reused
        // token on the next refresh, which reads as theft.
        refreshToken: refresh,
        expiresInSeconds: (tokens?['expires_in'] as num?)?.toInt() ?? 900,
      );
      return true;
    } on DioException {
      return false;
    }
  }
}
