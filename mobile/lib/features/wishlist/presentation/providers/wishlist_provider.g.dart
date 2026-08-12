// GENERATED CODE - DO NOT MODIFY BY HAND

part of 'wishlist_provider.dart';

// **************************************************************************
// RiverpodGenerator
// **************************************************************************

// GENERATED CODE - DO NOT MODIFY BY HAND
// ignore_for_file: type=lint, type=warning
/// The wishlist.
///
/// **There is no wishlist endpoint yet** — the backend has not shipped one. It
/// lives on the device, which means it does not follow the guest to another
/// phone and is lost if the app is uninstalled. That limitation is surfaced on
/// the screen rather than hidden.
///
/// Shipping it anyway is deliberate: a wishlist is how people plan a trip over
/// several days, and a device-local one is far better than none. The state is
/// held here rather than read from disk on every build, so a heart taps
/// instantly — a saved-stay toggle that waits on I/O feels broken.

@ProviderFor(Wishlist)
final wishlistProvider = WishlistProvider._();

/// The wishlist.
///
/// **There is no wishlist endpoint yet** — the backend has not shipped one. It
/// lives on the device, which means it does not follow the guest to another
/// phone and is lost if the app is uninstalled. That limitation is surfaced on
/// the screen rather than hidden.
///
/// Shipping it anyway is deliberate: a wishlist is how people plan a trip over
/// several days, and a device-local one is far better than none. The state is
/// held here rather than read from disk on every build, so a heart taps
/// instantly — a saved-stay toggle that waits on I/O feels broken.
final class WishlistProvider
    extends $NotifierProvider<Wishlist, List<WishlistEntry>> {
  /// The wishlist.
  ///
  /// **There is no wishlist endpoint yet** — the backend has not shipped one. It
  /// lives on the device, which means it does not follow the guest to another
  /// phone and is lost if the app is uninstalled. That limitation is surfaced on
  /// the screen rather than hidden.
  ///
  /// Shipping it anyway is deliberate: a wishlist is how people plan a trip over
  /// several days, and a device-local one is far better than none. The state is
  /// held here rather than read from disk on every build, so a heart taps
  /// instantly — a saved-stay toggle that waits on I/O feels broken.
  WishlistProvider._()
    : super(
        from: null,
        argument: null,
        retry: null,
        name: r'wishlistProvider',
        isAutoDispose: false,
        dependencies: null,
        $allTransitiveDependencies: null,
      );

  @override
  String debugGetCreateSourceHash() => _$wishlistHash();

  @$internal
  @override
  Wishlist create() => Wishlist();

  /// {@macro riverpod.override_with_value}
  Override overrideWithValue(List<WishlistEntry> value) {
    return $ProviderOverride(
      origin: this,
      providerOverride: $SyncValueProvider<List<WishlistEntry>>(value),
    );
  }
}

String _$wishlistHash() => r'427e9437e50f8fbe1f9182be53c7588e8c09e0e2';

/// The wishlist.
///
/// **There is no wishlist endpoint yet** — the backend has not shipped one. It
/// lives on the device, which means it does not follow the guest to another
/// phone and is lost if the app is uninstalled. That limitation is surfaced on
/// the screen rather than hidden.
///
/// Shipping it anyway is deliberate: a wishlist is how people plan a trip over
/// several days, and a device-local one is far better than none. The state is
/// held here rather than read from disk on every build, so a heart taps
/// instantly — a saved-stay toggle that waits on I/O feels broken.

abstract class _$Wishlist extends $Notifier<List<WishlistEntry>> {
  List<WishlistEntry> build();
  @$mustCallSuper
  @override
  void runBuild() {
    final ref = this.ref as $Ref<List<WishlistEntry>, List<WishlistEntry>>;
    final element =
        ref.element
            as $ClassProviderElement<
              AnyNotifier<List<WishlistEntry>, List<WishlistEntry>>,
              List<WishlistEntry>,
              Object?,
              Object?
            >;
    element.handleCreate(ref, build);
  }
}

/// Whether one property is saved. A separate provider so a card rebuilds only
/// when *its* saved state changes, not on every wishlist mutation.

@ProviderFor(isSaved)
final isSavedProvider = IsSavedFamily._();

/// Whether one property is saved. A separate provider so a card rebuilds only
/// when *its* saved state changes, not on every wishlist mutation.

final class IsSavedProvider extends $FunctionalProvider<bool, bool, bool>
    with $Provider<bool> {
  /// Whether one property is saved. A separate provider so a card rebuilds only
  /// when *its* saved state changes, not on every wishlist mutation.
  IsSavedProvider._({
    required IsSavedFamily super.from,
    required String super.argument,
  }) : super(
         retry: null,
         name: r'isSavedProvider',
         isAutoDispose: true,
         dependencies: null,
         $allTransitiveDependencies: null,
       );

  @override
  String debugGetCreateSourceHash() => _$isSavedHash();

  @override
  String toString() {
    return r'isSavedProvider'
        ''
        '($argument)';
  }

  @$internal
  @override
  $ProviderElement<bool> $createElement($ProviderPointer pointer) =>
      $ProviderElement(pointer);

  @override
  bool create(Ref ref) {
    final argument = this.argument as String;
    return isSaved(ref, argument);
  }

  /// {@macro riverpod.override_with_value}
  Override overrideWithValue(bool value) {
    return $ProviderOverride(
      origin: this,
      providerOverride: $SyncValueProvider<bool>(value),
    );
  }

  @override
  bool operator ==(Object other) {
    return other is IsSavedProvider && other.argument == argument;
  }

  @override
  int get hashCode {
    return argument.hashCode;
  }
}

String _$isSavedHash() => r'49a37007c0c312ab9083a57792d3593b06cb7d4c';

/// Whether one property is saved. A separate provider so a card rebuilds only
/// when *its* saved state changes, not on every wishlist mutation.

final class IsSavedFamily extends $Family
    with $FunctionalFamilyOverride<bool, String> {
  IsSavedFamily._()
    : super(
        retry: null,
        name: r'isSavedProvider',
        dependencies: null,
        $allTransitiveDependencies: null,
        isAutoDispose: true,
      );

  /// Whether one property is saved. A separate provider so a card rebuilds only
  /// when *its* saved state changes, not on every wishlist mutation.

  IsSavedProvider call(String propertyId) =>
      IsSavedProvider._(argument: propertyId, from: this);

  @override
  String toString() => r'isSavedProvider';
}
