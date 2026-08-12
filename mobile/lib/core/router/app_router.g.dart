// GENERATED CODE - DO NOT MODIFY BY HAND

part of 'app_router.dart';

// **************************************************************************
// RiverpodGenerator
// **************************************************************************

// GENERATED CODE - DO NOT MODIFY BY HAND
// ignore_for_file: type=lint, type=warning
/// The router.
///
/// The redirect is the load-bearing part. It has to distinguish three states,
/// not two: signed in, signed out, and **still restoring**. Treating "restoring"
/// as signed-out flashes the sign-in screen at a signed-in user on every cold
/// start — a bug that only appears on a real device, because in development the
/// token exchange is instant.

@ProviderFor(appRouter)
final appRouterProvider = AppRouterProvider._();

/// The router.
///
/// The redirect is the load-bearing part. It has to distinguish three states,
/// not two: signed in, signed out, and **still restoring**. Treating "restoring"
/// as signed-out flashes the sign-in screen at a signed-in user on every cold
/// start — a bug that only appears on a real device, because in development the
/// token exchange is instant.

final class AppRouterProvider
    extends $FunctionalProvider<GoRouter, GoRouter, GoRouter>
    with $Provider<GoRouter> {
  /// The router.
  ///
  /// The redirect is the load-bearing part. It has to distinguish three states,
  /// not two: signed in, signed out, and **still restoring**. Treating "restoring"
  /// as signed-out flashes the sign-in screen at a signed-in user on every cold
  /// start — a bug that only appears on a real device, because in development the
  /// token exchange is instant.
  AppRouterProvider._()
    : super(
        from: null,
        argument: null,
        retry: null,
        name: r'appRouterProvider',
        isAutoDispose: false,
        dependencies: null,
        $allTransitiveDependencies: null,
      );

  @override
  String debugGetCreateSourceHash() => _$appRouterHash();

  @$internal
  @override
  $ProviderElement<GoRouter> $createElement($ProviderPointer pointer) =>
      $ProviderElement(pointer);

  @override
  GoRouter create(Ref ref) {
    return appRouter(ref);
  }

  /// {@macro riverpod.override_with_value}
  Override overrideWithValue(GoRouter value) {
    return $ProviderOverride(
      origin: this,
      providerOverride: $SyncValueProvider<GoRouter>(value),
    );
  }
}

String _$appRouterHash() => r'0313ad64a71946df2f7bd089aedbc84eb109af78';
