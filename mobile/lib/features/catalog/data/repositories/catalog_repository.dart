import 'package:dio/dio.dart';

import '../../../../core/error/failure.dart';
import '../../../../core/network/result.dart';
import '../../../../core/storage/cache_store.dart';
import '../../domain/entities/search_criteria.dart';
import '../datasources/catalog_remote_datasource.dart';
import '../models/property_models.dart';

/// A page of results, with the cursor for the next one.
class SearchPage {
  const SearchPage({
    required this.items,
    this.nextCursor,
    this.totalEstimate,
    this.isStale = false,
    this.cachedAt,
  });

  final List<SearchItemDto> items;
  final String? nextCursor;
  final int? totalEstimate;

  /// True when this came from the cache after the network failed. The UI says
  /// so — showing saved prices as if they were live is how a guest arrives at
  /// checkout to a different number.
  final bool isStale;
  final DateTime? cachedAt;

  bool get hasMore => nextCursor != null;
}

/// The catalogue, with its caching policy.
///
/// The policy is the interesting part, and it differs per resource because the
/// consequences of staleness differ:
///
/// * **Amenities** are a reference list that changes monthly. Cached for a day,
///   served from cache first — a filter sheet must open instantly.
/// * **Search** is cached only for its *first* page, and only as a fallback for
///   when the network fails. Prices and availability go stale in minutes, so
///   cached results are never preferred, only better than a blank screen.
/// * **Property detail** is cached similarly, because a guest walking into a
///   lift on the way to a property should keep the address and the check-in
///   time.
///
/// Later pages are never cached: a cursor is meaningless without the query that
/// produced it, and a half-restored infinite list is worse than none.
class CatalogRepository {
  const CatalogRepository({
    required CatalogRemoteDataSource remote,
    required CacheStore cache,
  })  : _remote = remote,
        _cache = cache;

  final CatalogRemoteDataSource _remote;
  final CacheStore _cache;

  static const _searchFreshFor = Duration(minutes: 5);
  static const _propertyFreshFor = Duration(hours: 1);
  static const _amenitiesFreshFor = Duration(days: 1);

  Future<Result<SearchPage>> search(
    SearchCriteria criteria, {
    String? cursor,
    int limit = 20,
    CancelToken? cancelToken,
  }) async {
    final key = CacheKeys.search(criteria.cacheSignature);
    final isFirstPage = cursor == null;

    final result = await guard(() async {
      final dto = await _remote.search(
        criteria,
        cursor: cursor,
        limit: limit,
        cancelToken: cancelToken,
      );
      if (isFirstPage) {
        await _cache.writeList(
          key,
          dto.items.map((item) => item.toJson()).toList(growable: false),
        );
      }
      return SearchPage(
        items: dto.items,
        nextCursor: dto.nextCursor,
        totalEstimate: dto.totalEstimate,
      );
    });

    return switch (result) {
      Ok<SearchPage>() => result,
      // Only the first page has a fallback, and only when the failure was the
      // network rather than the server refusing the query — serving a cached
      // page for a 422 would hide a real bug behind stale data.
      Err<SearchPage>(:final failure) when isFirstPage && failure.isOffline =>
        _cachedSearch(key) ?? result,
      Err<SearchPage>() => result,
    };
  }

  /// Deliberately serves an expired page, unlike [property] above.
  ///
  /// The asymmetry is the presence of a banner. This returns `isStale` and
  /// `cachedAt`, so the screen says "saved 20 minutes ago" over the results and
  /// the guest can judge the prices themselves — which beats a blank screen on
  /// a train. `property` has no such signal, so it enforces its window.
  ///
  /// [_searchFreshFor] is therefore about *labelling*, not about withholding:
  /// it is what a caller would consult to decide how loudly to warn.
  Result<SearchPage>? _cachedSearch(String key) {
    final entry = _cache.readList(
      key,
      SearchItemDto.fromJson,
      freshFor: _searchFreshFor,
    );
    if (entry == null) return null;
    return Result.ok(
      SearchPage(
        items: entry.value,
        isStale: true,
        cachedAt: entry.storedAt,
      ),
    );
  }

  Future<Result<List<SuggestionDto>>> suggest(
    String query, {
    CancelToken? cancelToken,
  }) =>
      guard(() => _remote.suggest(query, cancelToken: cancelToken));

  Future<Result<PropertyDto>> property(
    String identifier, {
    CancelToken? cancelToken,
  }) async {
    final key = CacheKeys.property(identifier);

    final result = await guard(() async {
      final dto = await _remote.property(identifier, cancelToken: cancelToken);
      await _cache.write(key, dto.toJson());
      return dto;
    });

    if (result case Err<PropertyDto>(:final failure) when failure.isOffline) {
      final entry = _cache.read(
        key,
        PropertyDto.fromJson,
        freshFor: _propertyFreshFor,
      );
      // `isFresh` must be checked, not merely requested. `read` returns an
      // expired entry on purpose — that is what lets a *search* render with a
      // "saved earlier" banner — so a caller that only null-checks serves data
      // of any age. Here there is no banner to hang it on: this returns the
      // DTO the live path returns, prices and all, so anything past the window
      // has to be refused.
      if (entry != null && entry.isFresh) return Result.ok(entry.value);
    }
    return result;
  }

  Future<Result<QuoteDto>> quote({
    required String propertyId,
    required String roomTypeId,
    required String checkIn,
    required String checkOut,
    required int adults,
    int children = 0,
    int infants = 0,
    int rooms = 1,
    CancelToken? cancelToken,
  }) =>
      // Deliberately never cached. A quote is the number the guest agrees to
      // pay and the server re-checks it at booking time; a stale one produces a
      // 409 at the worst possible moment.
      guard(
        () => _remote.quote(
          propertyId: propertyId,
          roomTypeId: roomTypeId,
          checkIn: checkIn,
          checkOut: checkOut,
          adults: adults,
          children: children,
          infants: infants,
          rooms: rooms,
          cancelToken: cancelToken,
        ),
      );

  Future<Result<CalendarDto>> availability({
    required String propertyId,
    required String from,
    required String to,
    CancelToken? cancelToken,
  }) =>
      guard(
        () => _remote.availability(
          propertyId: propertyId,
          from: from,
          to: to,
          cancelToken: cancelToken,
        ),
      );

  Future<Result<List<AmenityDto>>> amenities({CancelToken? cancelToken}) async {
    // Cache-first here, unlike everywhere else: this is a reference list, the
    // filter sheet must open without a spinner, and a day-old amenity list is
    // indistinguishable from a fresh one.
    final cached = _cache.readList(
      CacheKeys.amenities,
      AmenityDto.fromJson,
      freshFor: _amenitiesFreshFor,
    );
    if (cached != null && cached.isFresh) return Result.ok(cached.value);

    final result = await guard(() async {
      final items = await _remote.amenities(cancelToken: cancelToken);
      await _cache.writeList(
        CacheKeys.amenities,
        items.map((a) => a.toJson()).toList(growable: false),
      );
      return items;
    });

    if (result case Err<List<AmenityDto>>() when cached != null) {
      return Result.ok(cached.value);
    }
    return result;
  }
}
