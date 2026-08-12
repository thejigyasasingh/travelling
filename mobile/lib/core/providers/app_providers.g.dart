// GENERATED CODE - DO NOT MODIFY BY HAND

part of 'app_providers.dart';

// **************************************************************************
// RiverpodGenerator
// **************************************************************************

// GENERATED CODE - DO NOT MODIFY BY HAND
// ignore_for_file: type=lint, type=warning
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

@ProviderFor(appConfig)
final appConfigProvider = AppConfigProvider._();

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

final class AppConfigProvider
    extends $FunctionalProvider<AppConfig, AppConfig, AppConfig>
    with $Provider<AppConfig> {
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
  AppConfigProvider._()
    : super(
        from: null,
        argument: null,
        retry: null,
        name: r'appConfigProvider',
        isAutoDispose: false,
        dependencies: null,
        $allTransitiveDependencies: null,
      );

  @override
  String debugGetCreateSourceHash() => _$appConfigHash();

  @$internal
  @override
  $ProviderElement<AppConfig> $createElement($ProviderPointer pointer) =>
      $ProviderElement(pointer);

  @override
  AppConfig create(Ref ref) {
    return appConfig(ref);
  }

  /// {@macro riverpod.override_with_value}
  Override overrideWithValue(AppConfig value) {
    return $ProviderOverride(
      origin: this,
      providerOverride: $SyncValueProvider<AppConfig>(value),
    );
  }
}

String _$appConfigHash() => r'87f9d20a2d92252672162b2ce97547b7b2479239';

@ProviderFor(tokenStore)
final tokenStoreProvider = TokenStoreProvider._();

final class TokenStoreProvider
    extends $FunctionalProvider<TokenStore, TokenStore, TokenStore>
    with $Provider<TokenStore> {
  TokenStoreProvider._()
    : super(
        from: null,
        argument: null,
        retry: null,
        name: r'tokenStoreProvider',
        isAutoDispose: false,
        dependencies: null,
        $allTransitiveDependencies: null,
      );

  @override
  String debugGetCreateSourceHash() => _$tokenStoreHash();

  @$internal
  @override
  $ProviderElement<TokenStore> $createElement($ProviderPointer pointer) =>
      $ProviderElement(pointer);

  @override
  TokenStore create(Ref ref) {
    return tokenStore(ref);
  }

  /// {@macro riverpod.override_with_value}
  Override overrideWithValue(TokenStore value) {
    return $ProviderOverride(
      origin: this,
      providerOverride: $SyncValueProvider<TokenStore>(value),
    );
  }
}

String _$tokenStoreHash() => r'6a8cb6aae6c40142541e5eb84a66e0f2a8719c4a';

@ProviderFor(cacheStore)
final cacheStoreProvider = CacheStoreProvider._();

final class CacheStoreProvider
    extends $FunctionalProvider<CacheStore, CacheStore, CacheStore>
    with $Provider<CacheStore> {
  CacheStoreProvider._()
    : super(
        from: null,
        argument: null,
        retry: null,
        name: r'cacheStoreProvider',
        isAutoDispose: false,
        dependencies: null,
        $allTransitiveDependencies: null,
      );

  @override
  String debugGetCreateSourceHash() => _$cacheStoreHash();

  @$internal
  @override
  $ProviderElement<CacheStore> $createElement($ProviderPointer pointer) =>
      $ProviderElement(pointer);

  @override
  CacheStore create(Ref ref) {
    return cacheStore(ref);
  }

  /// {@macro riverpod.override_with_value}
  Override overrideWithValue(CacheStore value) {
    return $ProviderOverride(
      origin: this,
      providerOverride: $SyncValueProvider<CacheStore>(value),
    );
  }
}

String _$cacheStoreHash() => r'd428aeffe701f427a29627635244bf71217a8d67';

@ProviderFor(connectivity)
final connectivityProvider = ConnectivityProvider._();

final class ConnectivityProvider
    extends
        $FunctionalProvider<
          ConnectivityService,
          ConnectivityService,
          ConnectivityService
        >
    with $Provider<ConnectivityService> {
  ConnectivityProvider._()
    : super(
        from: null,
        argument: null,
        retry: null,
        name: r'connectivityProvider',
        isAutoDispose: false,
        dependencies: null,
        $allTransitiveDependencies: null,
      );

  @override
  String debugGetCreateSourceHash() => _$connectivityHash();

  @$internal
  @override
  $ProviderElement<ConnectivityService> $createElement(
    $ProviderPointer pointer,
  ) => $ProviderElement(pointer);

  @override
  ConnectivityService create(Ref ref) {
    return connectivity(ref);
  }

  /// {@macro riverpod.override_with_value}
  Override overrideWithValue(ConnectivityService value) {
    return $ProviderOverride(
      origin: this,
      providerOverride: $SyncValueProvider<ConnectivityService>(value),
    );
  }
}

String _$connectivityHash() => r'c33b3427c8dd123d53c3ce3ff85f442d03e6f513';

/// Emits when connectivity returns, so a screen showing an offline state can
/// retry itself rather than waiting for a pull-to-refresh.

@ProviderFor(connectivityStatus)
final connectivityStatusProvider = ConnectivityStatusProvider._();

/// Emits when connectivity returns, so a screen showing an offline state can
/// retry itself rather than waiting for a pull-to-refresh.

final class ConnectivityStatusProvider
    extends $FunctionalProvider<AsyncValue<bool>, bool, Stream<bool>>
    with $FutureModifier<bool>, $StreamProvider<bool> {
  /// Emits when connectivity returns, so a screen showing an offline state can
  /// retry itself rather than waiting for a pull-to-refresh.
  ConnectivityStatusProvider._()
    : super(
        from: null,
        argument: null,
        retry: null,
        name: r'connectivityStatusProvider',
        isAutoDispose: false,
        dependencies: null,
        $allTransitiveDependencies: null,
      );

  @override
  String debugGetCreateSourceHash() => _$connectivityStatusHash();

  @$internal
  @override
  $StreamProviderElement<bool> $createElement($ProviderPointer pointer) =>
      $StreamProviderElement(pointer);

  @override
  Stream<bool> create(Ref ref) {
    return connectivityStatus(ref);
  }
}

String _$connectivityStatusHash() =>
    r'4c824ce26c7bfb6f29cba87a9cd2e4dd9935e687';

/// The signal that a session could not be renewed. The router watches it and
/// sends the user to sign-in; keeping it separate from the auth notifier avoids
/// a cycle, since the interceptor that raises it is built *below* auth.

@ProviderFor(SessionLost)
final sessionLostProvider = SessionLostProvider._();

/// The signal that a session could not be renewed. The router watches it and
/// sends the user to sign-in; keeping it separate from the auth notifier avoids
/// a cycle, since the interceptor that raises it is built *below* auth.
final class SessionLostProvider extends $NotifierProvider<SessionLost, bool> {
  /// The signal that a session could not be renewed. The router watches it and
  /// sends the user to sign-in; keeping it separate from the auth notifier avoids
  /// a cycle, since the interceptor that raises it is built *below* auth.
  SessionLostProvider._()
    : super(
        from: null,
        argument: null,
        retry: null,
        name: r'sessionLostProvider',
        isAutoDispose: false,
        dependencies: null,
        $allTransitiveDependencies: null,
      );

  @override
  String debugGetCreateSourceHash() => _$sessionLostHash();

  @$internal
  @override
  SessionLost create() => SessionLost();

  /// {@macro riverpod.override_with_value}
  Override overrideWithValue(bool value) {
    return $ProviderOverride(
      origin: this,
      providerOverride: $SyncValueProvider<bool>(value),
    );
  }
}

String _$sessionLostHash() => r'3a94759cb82fa177b3f8ae61f3b307e484ac29a3';

/// The signal that a session could not be renewed. The router watches it and
/// sends the user to sign-in; keeping it separate from the auth notifier avoids
/// a cycle, since the interceptor that raises it is built *below* auth.

abstract class _$SessionLost extends $Notifier<bool> {
  bool build();
  @$mustCallSuper
  @override
  void runBuild() {
    final ref = this.ref as $Ref<bool, bool>;
    final element =
        ref.element
            as $ClassProviderElement<
              AnyNotifier<bool, bool>,
              bool,
              Object?,
              Object?
            >;
    element.handleCreate(ref, build);
  }
}

@ProviderFor(apiClient)
final apiClientProvider = ApiClientProvider._();

final class ApiClientProvider
    extends $FunctionalProvider<ApiClient, ApiClient, ApiClient>
    with $Provider<ApiClient> {
  ApiClientProvider._()
    : super(
        from: null,
        argument: null,
        retry: null,
        name: r'apiClientProvider',
        isAutoDispose: false,
        dependencies: null,
        $allTransitiveDependencies: null,
      );

  @override
  String debugGetCreateSourceHash() => _$apiClientHash();

  @$internal
  @override
  $ProviderElement<ApiClient> $createElement($ProviderPointer pointer) =>
      $ProviderElement(pointer);

  @override
  ApiClient create(Ref ref) {
    return apiClient(ref);
  }

  /// {@macro riverpod.override_with_value}
  Override overrideWithValue(ApiClient value) {
    return $ProviderOverride(
      origin: this,
      providerOverride: $SyncValueProvider<ApiClient>(value),
    );
  }
}

String _$apiClientHash() => r'05a763373034bc63dfaa825325acb50a1507e25c';

@ProviderFor(dio)
final dioProvider = DioProvider._();

final class DioProvider extends $FunctionalProvider<Dio, Dio, Dio>
    with $Provider<Dio> {
  DioProvider._()
    : super(
        from: null,
        argument: null,
        retry: null,
        name: r'dioProvider',
        isAutoDispose: false,
        dependencies: null,
        $allTransitiveDependencies: null,
      );

  @override
  String debugGetCreateSourceHash() => _$dioHash();

  @$internal
  @override
  $ProviderElement<Dio> $createElement($ProviderPointer pointer) =>
      $ProviderElement(pointer);

  @override
  Dio create(Ref ref) {
    return dio(ref);
  }

  /// {@macro riverpod.override_with_value}
  Override overrideWithValue(Dio value) {
    return $ProviderOverride(
      origin: this,
      providerOverride: $SyncValueProvider<Dio>(value),
    );
  }
}

String _$dioHash() => r'3c9a828dd31488f819e90905396f39a5fab73923';
