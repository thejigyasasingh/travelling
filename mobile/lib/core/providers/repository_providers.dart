import 'package:riverpod_annotation/riverpod_annotation.dart';

import '../../features/auth/data/repositories/auth_repository.dart';
import '../../features/booking/data/repositories/booking_repository.dart';
import '../../features/booking/domain/usecases/reserve_stay.dart';
import '../../features/catalog/data/datasources/catalog_remote_datasource.dart';
import '../../features/catalog/data/repositories/catalog_repository.dart';
import '../../features/catalog/domain/usecases/get_quote.dart';
import '../../features/catalog/domain/usecases/search_properties.dart';
import 'app_providers.dart';

part 'repository_providers.g.dart';

/// Repositories and use cases.
///
/// Kept separate from `app_providers` so a widget test can override a single
/// repository with a fake and leave the HTTP layer entirely unbuilt — no Dio,
/// no interceptors, no network.

@Riverpod(keepAlive: true)
CatalogRemoteDataSource catalogRemoteDataSource(Ref ref) =>
    CatalogRemoteDataSource(ref.watch(dioProvider));

@Riverpod(keepAlive: true)
CatalogRepository catalogRepository(Ref ref) => CatalogRepository(
      remote: ref.watch(catalogRemoteDataSourceProvider),
      cache: ref.watch(cacheStoreProvider),
    );

@Riverpod(keepAlive: true)
AuthRepository authRepository(Ref ref) => AuthRepository(
      dio: ref.watch(dioProvider),
      tokens: ref.watch(tokenStoreProvider),
      cache: ref.watch(cacheStoreProvider),
    );

@Riverpod(keepAlive: true)
BookingRepository bookingRepository(Ref ref) => BookingRepository(
      dio: ref.watch(dioProvider),
      cache: ref.watch(cacheStoreProvider),
    );

@Riverpod(keepAlive: true)
SearchProperties searchProperties(Ref ref) =>
    SearchProperties(ref.watch(catalogRepositoryProvider));

@Riverpod(keepAlive: true)
GetQuote getQuote(Ref ref) => GetQuote(ref.watch(catalogRepositoryProvider));

@Riverpod(keepAlive: true)
ReserveStay reserveStay(Ref ref) =>
    ReserveStay(ref.watch(bookingRepositoryProvider));
