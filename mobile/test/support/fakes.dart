/// Test doubles shared by the repository suites.
///
/// Two of them, and both are deliberately thin. The point of a repository test
/// is the *policy* — what gets cached, for how long, and what happens when the
/// network is gone — so the doubles exist only to make that policy reachable
/// without a device, a Keychain or a socket.
library;

import 'dart:convert';
import 'dart:typed_data';

import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:hive_ce/hive.dart';
import 'package:roaming_wandering/core/error/failure.dart';
import 'package:roaming_wandering/core/network/api_client.dart';
import 'package:roaming_wandering/core/network/result.dart';
import 'package:roaming_wandering/core/storage/cache_store.dart';

/// A [Box] backed by a map.
///
/// Hive's real box wants an initialised directory and, on Flutter, a path
/// provider. `CacheStore` only ever calls four methods on it, so those four are
/// what this implements — `extends Fake` makes any fifth call fail loudly
/// rather than silently returning null, which is exactly what should happen if
/// the store grows a dependency this double does not model.
class InMemoryBox extends Fake implements Box<String> {
  final Map<String, String> entries = {};

  /// Counted so a test can assert the cache was *not* written, which is the
  /// interesting half of several policies.
  int writes = 0;

  @override
  String? get(dynamic key, {String? defaultValue}) =>
      entries[key as String] ?? defaultValue;

  @override
  Future<void> put(dynamic key, String value) async {
    writes++;
    entries[key as String] = value;
  }

  @override
  Future<void> delete(dynamic key) async => entries.remove(key);

  @override
  Future<int> clear() async {
    final count = entries.length;
    entries.clear();
    return count;
  }

  /// Backdate an entry so a freshness window can be tested without sleeping.
  ///
  /// Reaches into the envelope `CacheStore.write` produces rather than
  /// re-encoding it here: if the envelope shape changes, this throws instead of
  /// quietly making every staleness test vacuous.
  void age(String key, Duration by) {
    final envelope = jsonDecode(entries[key]!) as Map<String, dynamic>;
    envelope['at'] = (envelope['at'] as int) - by.inMilliseconds;
    entries[key] = jsonEncode(envelope);
  }
}

/// Builds a [CacheStore] over an [InMemoryBox], returning both.
({CacheStore cache, InMemoryBox box}) inMemoryCache() {
  final box = InMemoryBox();
  return (cache: CacheStore(box), box: box);
}

// ══════════════════════════════════════════════════════════════════════════
// HTTP
// ══════════════════════════════════════════════════════════════════════════

/// Answers requests from a handler, at the adapter seam.
///
/// Below the interceptors rather than above them, so a test exercises the real
/// Dio pipeline: header merging, query serialisation, JSON decoding, and Dio's
/// own exception types — which is what `mapDioError` reads. Stubbing `Dio`
/// itself would skip all of that and test the mock instead.
class StubAdapter implements HttpClientAdapter {
  StubAdapter(this.handler);

  final Future<ResponseBody> Function(RequestOptions options) handler;

  /// Every request that reached the wire, for asserting on headers and bodies.
  final List<RequestOptions> requests = [];

  @override
  Future<ResponseBody> fetch(
    RequestOptions options,
    Stream<Uint8List>? requestStream,
    Future<void>? cancelFuture,
  ) {
    requests.add(options);
    return handler(options);
  }

  @override
  void close({bool force = false}) {}
}

ResponseBody jsonResponse(Object body, {int status = 200}) => ResponseBody.fromString(
      jsonEncode(body),
      status,
      headers: {
        Headers.contentTypeHeader: [Headers.jsonContentType],
      },
    );

/// A Dio wired to a stub adapter, with the error mapper installed.
///
/// `mapDioErrorRef` is assigned at app startup in `app_providers.dart`; a test
/// that skips it gets `Failure.unexpected` for everything, and every assertion
/// about offline behaviour passes for the wrong reason. Setting it here means
/// no suite can forget.
({Dio dio, StubAdapter adapter}) stubbedDio(
  Future<ResponseBody> Function(RequestOptions options) handler,
) {
  mapDioErrorRef = mapDioError;
  final adapter = StubAdapter(handler);
  final dio = Dio(BaseOptions(baseUrl: 'https://api.test/v1'))
    ..httpClientAdapter = adapter;
  return (dio: dio, adapter: adapter);
}

/// A Dio whose every request fails the way a phone in a tunnel does.
({Dio dio, StubAdapter adapter}) offlineDio() => stubbedDio(
      (options) => Future.error(
        DioException.connectionError(
          requestOptions: options,
          reason: 'no route to host',
        ),
      ),
    );

/// Unwraps a successful [Result], failing the test with the failure's message
/// rather than a bare null dereference when it is an error.
T expectOk<T>(Result<T> result) {
  final failure = result.failureOrNull;
  expect(failure, isNull, reason: 'expected Ok, got ${failure?.message}');
  return result.valueOrNull as T;
}
