// GENERATED CODE - DO NOT MODIFY BY HAND

part of 'repository_providers.dart';

// **************************************************************************
// RiverpodGenerator
// **************************************************************************

// GENERATED CODE - DO NOT MODIFY BY HAND
// ignore_for_file: type=lint, type=warning
/// Repositories and use cases.
///
/// Kept separate from `app_providers` so a widget test can override a single
/// repository with a fake and leave the HTTP layer entirely unbuilt — no Dio,
/// no interceptors, no network.

@ProviderFor(catalogRemoteDataSource)
final catalogRemoteDataSourceProvider = CatalogRemoteDataSourceProvider._();

/// Repositories and use cases.
///
/// Kept separate from `app_providers` so a widget test can override a single
/// repository with a fake and leave the HTTP layer entirely unbuilt — no Dio,
/// no interceptors, no network.

final class CatalogRemoteDataSourceProvider
    extends
        $FunctionalProvider<
          CatalogRemoteDataSource,
          CatalogRemoteDataSource,
          CatalogRemoteDataSource
        >
    with $Provider<CatalogRemoteDataSource> {
  /// Repositories and use cases.
  ///
  /// Kept separate from `app_providers` so a widget test can override a single
  /// repository with a fake and leave the HTTP layer entirely unbuilt — no Dio,
  /// no interceptors, no network.
  CatalogRemoteDataSourceProvider._()
    : super(
        from: null,
        argument: null,
        retry: null,
        name: r'catalogRemoteDataSourceProvider',
        isAutoDispose: false,
        dependencies: null,
        $allTransitiveDependencies: null,
      );

  @override
  String debugGetCreateSourceHash() => _$catalogRemoteDataSourceHash();

  @$internal
  @override
  $ProviderElement<CatalogRemoteDataSource> $createElement(
    $ProviderPointer pointer,
  ) => $ProviderElement(pointer);

  @override
  CatalogRemoteDataSource create(Ref ref) {
    return catalogRemoteDataSource(ref);
  }

  /// {@macro riverpod.override_with_value}
  Override overrideWithValue(CatalogRemoteDataSource value) {
    return $ProviderOverride(
      origin: this,
      providerOverride: $SyncValueProvider<CatalogRemoteDataSource>(value),
    );
  }
}

String _$catalogRemoteDataSourceHash() =>
    r'e3da891a001f20bc54048768ec3932965832c2f7';

@ProviderFor(catalogRepository)
final catalogRepositoryProvider = CatalogRepositoryProvider._();

final class CatalogRepositoryProvider
    extends
        $FunctionalProvider<
          CatalogRepository,
          CatalogRepository,
          CatalogRepository
        >
    with $Provider<CatalogRepository> {
  CatalogRepositoryProvider._()
    : super(
        from: null,
        argument: null,
        retry: null,
        name: r'catalogRepositoryProvider',
        isAutoDispose: false,
        dependencies: null,
        $allTransitiveDependencies: null,
      );

  @override
  String debugGetCreateSourceHash() => _$catalogRepositoryHash();

  @$internal
  @override
  $ProviderElement<CatalogRepository> $createElement(
    $ProviderPointer pointer,
  ) => $ProviderElement(pointer);

  @override
  CatalogRepository create(Ref ref) {
    return catalogRepository(ref);
  }

  /// {@macro riverpod.override_with_value}
  Override overrideWithValue(CatalogRepository value) {
    return $ProviderOverride(
      origin: this,
      providerOverride: $SyncValueProvider<CatalogRepository>(value),
    );
  }
}

String _$catalogRepositoryHash() => r'2fc651f5eacf2358050de16d214d503e89ef2ead';

@ProviderFor(authRepository)
final authRepositoryProvider = AuthRepositoryProvider._();

final class AuthRepositoryProvider
    extends $FunctionalProvider<AuthRepository, AuthRepository, AuthRepository>
    with $Provider<AuthRepository> {
  AuthRepositoryProvider._()
    : super(
        from: null,
        argument: null,
        retry: null,
        name: r'authRepositoryProvider',
        isAutoDispose: false,
        dependencies: null,
        $allTransitiveDependencies: null,
      );

  @override
  String debugGetCreateSourceHash() => _$authRepositoryHash();

  @$internal
  @override
  $ProviderElement<AuthRepository> $createElement($ProviderPointer pointer) =>
      $ProviderElement(pointer);

  @override
  AuthRepository create(Ref ref) {
    return authRepository(ref);
  }

  /// {@macro riverpod.override_with_value}
  Override overrideWithValue(AuthRepository value) {
    return $ProviderOverride(
      origin: this,
      providerOverride: $SyncValueProvider<AuthRepository>(value),
    );
  }
}

String _$authRepositoryHash() => r'349f2036496d57c4c8eb2e0cb2f4eb666aafea3a';

@ProviderFor(bookingRepository)
final bookingRepositoryProvider = BookingRepositoryProvider._();

final class BookingRepositoryProvider
    extends
        $FunctionalProvider<
          BookingRepository,
          BookingRepository,
          BookingRepository
        >
    with $Provider<BookingRepository> {
  BookingRepositoryProvider._()
    : super(
        from: null,
        argument: null,
        retry: null,
        name: r'bookingRepositoryProvider',
        isAutoDispose: false,
        dependencies: null,
        $allTransitiveDependencies: null,
      );

  @override
  String debugGetCreateSourceHash() => _$bookingRepositoryHash();

  @$internal
  @override
  $ProviderElement<BookingRepository> $createElement(
    $ProviderPointer pointer,
  ) => $ProviderElement(pointer);

  @override
  BookingRepository create(Ref ref) {
    return bookingRepository(ref);
  }

  /// {@macro riverpod.override_with_value}
  Override overrideWithValue(BookingRepository value) {
    return $ProviderOverride(
      origin: this,
      providerOverride: $SyncValueProvider<BookingRepository>(value),
    );
  }
}

String _$bookingRepositoryHash() => r'e892384320c17c03020c128ef1331f0afaf7cc3a';

@ProviderFor(searchProperties)
final searchPropertiesProvider = SearchPropertiesProvider._();

final class SearchPropertiesProvider
    extends
        $FunctionalProvider<
          SearchProperties,
          SearchProperties,
          SearchProperties
        >
    with $Provider<SearchProperties> {
  SearchPropertiesProvider._()
    : super(
        from: null,
        argument: null,
        retry: null,
        name: r'searchPropertiesProvider',
        isAutoDispose: false,
        dependencies: null,
        $allTransitiveDependencies: null,
      );

  @override
  String debugGetCreateSourceHash() => _$searchPropertiesHash();

  @$internal
  @override
  $ProviderElement<SearchProperties> $createElement($ProviderPointer pointer) =>
      $ProviderElement(pointer);

  @override
  SearchProperties create(Ref ref) {
    return searchProperties(ref);
  }

  /// {@macro riverpod.override_with_value}
  Override overrideWithValue(SearchProperties value) {
    return $ProviderOverride(
      origin: this,
      providerOverride: $SyncValueProvider<SearchProperties>(value),
    );
  }
}

String _$searchPropertiesHash() => r'fb322009c3f3a4d5d4fcca99ef232facd6743c2b';

@ProviderFor(getQuote)
final getQuoteProvider = GetQuoteProvider._();

final class GetQuoteProvider
    extends $FunctionalProvider<GetQuote, GetQuote, GetQuote>
    with $Provider<GetQuote> {
  GetQuoteProvider._()
    : super(
        from: null,
        argument: null,
        retry: null,
        name: r'getQuoteProvider',
        isAutoDispose: false,
        dependencies: null,
        $allTransitiveDependencies: null,
      );

  @override
  String debugGetCreateSourceHash() => _$getQuoteHash();

  @$internal
  @override
  $ProviderElement<GetQuote> $createElement($ProviderPointer pointer) =>
      $ProviderElement(pointer);

  @override
  GetQuote create(Ref ref) {
    return getQuote(ref);
  }

  /// {@macro riverpod.override_with_value}
  Override overrideWithValue(GetQuote value) {
    return $ProviderOverride(
      origin: this,
      providerOverride: $SyncValueProvider<GetQuote>(value),
    );
  }
}

String _$getQuoteHash() => r'ae6437dd38dbd1040e768c4bc4cb33e1fca96ef8';

@ProviderFor(reserveStay)
final reserveStayProvider = ReserveStayProvider._();

final class ReserveStayProvider
    extends $FunctionalProvider<ReserveStay, ReserveStay, ReserveStay>
    with $Provider<ReserveStay> {
  ReserveStayProvider._()
    : super(
        from: null,
        argument: null,
        retry: null,
        name: r'reserveStayProvider',
        isAutoDispose: false,
        dependencies: null,
        $allTransitiveDependencies: null,
      );

  @override
  String debugGetCreateSourceHash() => _$reserveStayHash();

  @$internal
  @override
  $ProviderElement<ReserveStay> $createElement($ProviderPointer pointer) =>
      $ProviderElement(pointer);

  @override
  ReserveStay create(Ref ref) {
    return reserveStay(ref);
  }

  /// {@macro riverpod.override_with_value}
  Override overrideWithValue(ReserveStay value) {
    return $ProviderOverride(
      origin: this,
      providerOverride: $SyncValueProvider<ReserveStay>(value),
    );
  }
}

String _$reserveStayHash() => r'85783ab68cca31984b83ff76614ee1499b36cb77';
