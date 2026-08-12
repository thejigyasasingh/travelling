import 'dart:convert';
import 'dart:typed_data';

import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:roaming_wandering/core/network/auth_interceptor.dart';
import 'package:roaming_wandering/core/storage/token_store.dart';

/// The single-flight refresh.
///
/// This is why the file exists. A screen fires several requests at once; if the
/// access token has expired they all get 401 together. The backend **rotates**
/// refresh tokens and treats reuse as theft — it revokes the whole family and
/// signs the user out of every device. So concurrent refreshes do not merely
/// waste requests, they log the user out.
///
/// The failure is invisible in development, where the token is always fresh,
/// and catastrophic in production. Hence a test.
/// An in-memory stand-in for the Keychain, so these tests need no platform
/// channel. Implementing the interface — rather than mocking the class — means
/// a change to the contract breaks this file loudly.
class FakeTokenStore implements TokenStorage {
  FakeTokenStore({this.access, this.refresh, this.expiring = false});

  String? access;
  String? refresh;
  bool expiring;
  int saveCount = 0;
  bool cleared = false;

  @override
  String? get accessToken => access;

  @override
  bool get isAccessTokenExpiring => expiring;

  @override
  Future<String?> readRefreshToken() async => refresh;

  @override
  Future<void> save({
    required String accessToken,
    required String refreshToken,
    required int expiresInSeconds,
  }) async {
    saveCount++;
    access = accessToken;
    refresh = refreshToken;
    expiring = false;
  }

  @override
  Future<void> clear() async {
    cleared = true;
    access = null;
    refresh = null;
  }

  @override
  Future<void> load() async {}
}

void main() {
  late FakeTokenStore tokens;
  late Dio refreshDio;
  late Dio dio;
  late int refreshCalls;
  late bool sessionLost;

  /// The real refresh response shape: the full auth response, `{tokens, user}`
  /// — **not** a bare token. Verified against a running server. A fixture that
  /// invents a flatter shape lets a genuine bug pass here and fail in the field.
  Map<String, dynamic> refreshBody() => {
        'tokens': {
          'access_token': 'fresh-access',
          'refresh_token': 'rotated-refresh',
          'expires_in': 900,
          'refresh_expires_in': 2592000,
        },
        'user': {'id': 'u1', 'email': 'guest@example.com'},
      };

  setUp(() {
    tokens = FakeTokenStore(access: 'stale-access', refresh: 'stored-refresh');
    refreshCalls = 0;
    sessionLost = false;

    refreshDio = Dio(BaseOptions(baseUrl: 'https://api.test/v1'));
    dio = Dio(BaseOptions(baseUrl: 'https://api.test/v1'));

    // The refresh client answers refresh calls and replays retried requests.
    refreshDio.httpClientAdapter = _StubAdapter((options) {
      if (options.path.endsWith('/auth/refresh')) {
        refreshCalls++;
        return _json(refreshBody());
      }
      // A replay: succeeds only if it now carries the fresh token.
      final header = options.headers['Authorization'];
      return header == 'Bearer fresh-access'
          ? _json({'ok': true})
          : _json({'error': 'stale'}, status: 401);
    });

    dio.httpClientAdapter = _StubAdapter((options) {
      // Anything presenting the stale token is rejected, exactly as the server
      // would.
      final header = options.headers['Authorization'];
      return header == 'Bearer fresh-access'
          ? _json({'ok': true})
          : _json({'error': 'expired'}, status: 401);
    });

    dio.interceptors.add(
      AuthInterceptor(
        tokenStore: tokens,
        refreshClient: refreshDio,
        onSessionLost: () async => sessionLost = true,
      ),
    );
  });

  test('attaches the access token', () async {
    tokens.access = 'fresh-access';
    final response = await dio.get<Map<String, dynamic>>('/auth/me');
    expect(response.data, {'ok': true});
  });

  test('refreshes once on a 401 and replays the request', () async {
    final response = await dio.get<Map<String, dynamic>>('/auth/me');

    expect(refreshCalls, 1);
    expect(tokens.access, 'fresh-access');
    // Rotated: storing the old refresh token would present a reused one next
    // time, which the server reads as theft.
    expect(tokens.refresh, 'rotated-refresh');
    expect(response.data, {'ok': true});
  });

  test('refreshes ONCE for many concurrent 401s', () async {
    await Future.wait([
      dio.get<Map<String, dynamic>>('/bookings'),
      dio.get<Map<String, dynamic>>('/payments'),
      dio.get<Map<String, dynamic>>('/auth/me'),
      dio.get<Map<String, dynamic>>('/wishlist'),
    ]);

    // The whole point: four 401s, one refresh. More than one looks like token
    // reuse to the server and signs the user out everywhere.
    expect(refreshCalls, 1);
  });

  test('reports the session lost when the refresh fails', () async {
    refreshDio.httpClientAdapter =
        _StubAdapter((_) => _json({'error': 'nope'}, status: 401));

    await expectLater(
      dio.get<Map<String, dynamic>>('/auth/me'),
      throwsA(isA<DioException>()),
    );
    expect(sessionLost, isTrue);
  });

  test('treats a refresh response without tokens as a failed refresh', () async {
    // The bug this guards: reading `access_token` off the top level of the
    // response yields null, and every later request carries `Bearer null` while
    // the app still believes it is signed in.
    refreshDio.httpClientAdapter = _StubAdapter(
      (options) => options.path.endsWith('/auth/refresh')
          ? _json({'access_token': 'flat-and-wrong', 'expires_in': 900})
          : _json({'ok': true}),
    );

    await expectLater(
      dio.get<Map<String, dynamic>>('/auth/me'),
      throwsA(isA<DioException>()),
    );
    expect(sessionLost, isTrue);
  });

  test('never refreshes for an anonymous endpoint', () async {
    await expectLater(
      dio.post<Map<String, dynamic>>('/auth/login', data: {}),
      throwsA(isA<DioException>()),
    );
    // Login is how a token is obtained; refreshing on its 401 would be circular.
    expect(refreshCalls, 0);
  });

  test('refreshes proactively when the token is about to expire', () async {
    tokens.expiring = true;
    await dio.get<Map<String, dynamic>>('/auth/me');

    // Refreshed before sending, so the common case never spends a round trip
    // being told what we already knew.
    expect(refreshCalls, 1);
  });

  test('does not loop when the replay also 401s', () async {
    refreshDio.httpClientAdapter = _StubAdapter((options) {
      if (options.path.endsWith('/auth/refresh')) {
        refreshCalls++;
        return _json(refreshBody());
      }
      return _json({'error': 'still bad'}, status: 401);
    });

    await expectLater(
      dio.get<Map<String, dynamic>>('/auth/me'),
      throwsA(isA<DioException>()),
    );
    // One refresh, one replay, then it stops. An unbounded retry would hammer
    // the auth endpoint until the app was killed.
    expect(refreshCalls, 1);
  });
}

// ── plumbing ──────────────────────────────────────────────────────────────

ResponseBody _json(Map<String, dynamic> body, {int status = 200}) =>
    ResponseBody.fromString(
      jsonEncode(body),
      status,
      headers: {
        Headers.contentTypeHeader: [Headers.jsonContentType],
      },
    );

/// A Dio adapter that answers from a function instead of a socket.
class _StubAdapter implements HttpClientAdapter {
  _StubAdapter(this.handler);

  final ResponseBody Function(RequestOptions options) handler;

  @override
  void close({bool force = false}) {}

  @override
  Future<ResponseBody> fetch(
    RequestOptions options,
    Stream<Uint8List>? requestStream,
    Future<void>? cancelFuture,
  ) async =>
      handler(options);
}

