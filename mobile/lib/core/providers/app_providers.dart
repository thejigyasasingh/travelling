import 'package:dio/dio.dart';
import 'package:riverpod_annotation/riverpod_annotation.dart';

import '../config/app_config.dart';
import '../network/api_client.dart';
import '../network/connectivity.dart';
import '../network/result.dart';
import '../storage/cache_store.dart';
import '../storage/token_store.dart';

part 'app_providers.g.dart';

/// The composition root.
///
/// Everything expensive is a `keepAlive` provider built once. Riverpod is doing
/// the work a hand-written service locator would, with two differences that
/// matter: the graph is checked at compile time, and a test overrides one node
/// without touching the rest.
///
/// The three stores are overridden in `main()` with instances that have already
/// finished their async setup, so no screen ever waits on a `FutureProvider`
/// for the cache to open.

@Riverpod(keepAlive: true)
AppConfig appConfig(Ref ref) => AppConfig.fromEnvironment();

@Riverpod(keepAlive: true)
TokenStore tokenStore(Ref ref) =>
    throw UnimplementedError('overridden in main()');

@Riverpod(keepAlive: true)
CacheStore cacheStore(Ref ref) =>
    throw UnimplementedError('overridden in main()');

@Riverpod(keepAlive: true)
ConnectivityService connectivity(Ref ref) => ConnectivityService();

/// Emits when connectivity returns, so a screen showing an offline state can
/// retry itself rather than waiting for a pull-to-refresh.
@Riverpod(keepAlive: true)
Stream<bool> connectivityStatus(Ref ref) =>
    ref.watch(connectivityProvider).onStatusChange;

/// The signal that a session could not be renewed. The router watches it and
/// sends the user to sign-in; keeping it separate from the auth notifier avoids
/// a cycle, since the interceptor that raises it is built *below* auth.
@Riverpod(keepAlive: true)
class SessionLost extends _$SessionLost {
  @override
  bool build() => false;

  void raise() => state = true;
  void clear() => state = false;
}

@Riverpod(keepAlive: true)
ApiClient apiClient(Ref ref) {
  final client = ApiClient(
    config: ref.watch(appConfigProvider),
    tokenStore: ref.watch(tokenStoreProvider),
    onSessionLost: () async => ref.read(sessionLostProvider.notifier).raise(),
  );

  // Wire the Dio-aware error mapper into the Result helper, which deliberately
  // does not import Dio itself.
  mapDioErrorRef = mapDioError;

  ref.onDispose(client.dio.close);
  return client;
}

@Riverpod(keepAlive: true)
Dio dio(Ref ref) => ref.watch(apiClientProvider).dio;
