import 'dart:async';

import 'package:dio/dio.dart';
import 'package:riverpod_annotation/riverpod_annotation.dart';

import '../../../../core/network/result.dart';
import '../../../../core/providers/repository_providers.dart';
import '../../../../shared/paged_state.dart';
import '../../data/models/property_models.dart';
import '../../data/repositories/catalog_repository.dart';
import '../../domain/entities/search_criteria.dart';

part 'search_provider.g.dart';

/// The current search criteria.
///
/// Held apart from the results so that changing a filter is one notification
/// and the result list is free to decide what to do about it — rather than
/// every filter tap tearing down and rebuilding the list provider.
@riverpod
class SearchCriteriaController extends _$SearchCriteriaController {
  @override
  SearchCriteria build() => const SearchCriteria();

  void update(SearchCriteria Function(SearchCriteria current) transform) {
    state = transform(state);
  }

  void setQuery(String? query) =>
      update((c) => c.copyWith(query: query?.isEmpty ?? true ? null : query));

  void setDates(String? checkIn, String? checkOut) =>
      update((c) => c.copyWith(checkIn: checkIn, checkOut: checkOut));

  void setGuests({int? adults, int? children, int? rooms}) => update(
        (c) => c.copyWith(
          adults: adults ?? c.adults,
          children: children ?? c.children,
          rooms: rooms ?? c.rooms,
        ),
      );

  void toggleType(String type) => update(
        (c) => c.copyWith(
          propertyTypes: c.propertyTypes.contains(type)
              ? (c.propertyTypes.toList()..remove(type))
              : [...c.propertyTypes, type],
        ),
      );

  void toggleAmenity(String code) => update(
        (c) => c.copyWith(
          amenities: c.amenities.contains(code)
              ? (c.amenities.toList()..remove(code))
              : [...c.amenities, code],
        ),
      );

  void setSort(SearchSort sort) => update((c) => c.copyWith(sort: sort));

  void setPriceRange(int? minMinor, int? maxMinor) =>
      update((c) => c.copyWith(minPriceMinor: minMinor, maxPriceMinor: maxMinor));

  void setMinRating(double? rating) =>
      update((c) => c.copyWith(minRating: rating));

  void setInstantBooking(bool value) =>
      update((c) => c.copyWith(instantBookingOnly: value));

  /// Clears filters but keeps the trip: dates and guests describe *what* is
  /// being looked for, not how it is filtered, and clearing them is never what
  /// "clear filters" means.
  void clearFilters() => update(
        (c) => SearchCriteria(
          query: c.query,
          cityId: c.cityId,
          checkIn: c.checkIn,
          checkOut: c.checkOut,
          adults: c.adults,
          children: c.children,
          infants: c.infants,
          rooms: c.rooms,
        ),
      );
}

/// The search results, paginated.
///
/// Watches the criteria, so a filter change automatically starts a fresh first
/// page — and the cursor is dropped with it, because page three of the previous
/// result set means nothing in the new one.
@riverpod
class SearchResults extends _$SearchResults {
  CancelToken? _inFlight;

  @override
  PagedState<SearchItemDto> build() {
    final criteria = ref.watch(searchCriteriaControllerProvider);

    // A criteria change cancels the request already in flight. Without this, a
    // guest typing quickly gets pages racing each other and the slowest —
    // rather than the newest — wins.
    _inFlight?.cancel('criteria changed');
    final token = CancelToken();
    _inFlight = token;
    ref.onDispose(() => token.cancel('provider disposed'));

    unawaited(_loadFirstPage(criteria, token));
    return const PagedState(isInitialLoading: true);
  }

  Future<void> _loadFirstPage(SearchCriteria criteria, CancelToken token) async {
    final result = await ref
        .read(searchPropertiesProvider)
        .call(criteria, cancelToken: token);
    if (token.isCancelled) return;

    state = switch (result) {
      Ok<SearchPage>(:final value) => PagedState(
          items: value.items,
          nextCursor: value.nextCursor,
          totalEstimate: value.totalEstimate,
          isInitialLoading: false,
          isStale: value.isStale,
          cachedAt: value.cachedAt,
        ),
      Err<SearchPage>(:final failure) =>
        PagedState(isInitialLoading: false, initialError: failure),
    };
  }

  /// Fetch the next page. Safe to call from a scroll listener on every frame:
  /// it is a no-op unless there is a next page and nothing is already loading.
  Future<void> loadMore() async {
    final current = state;
    if (!current.canLoadMore) return;

    state = current.copyWith(isLoadingMore: true, pageError: null);

    final result = await ref.read(searchPropertiesProvider).call(
          ref.read(searchCriteriaControllerProvider),
          cursor: current.nextCursor,
        );

    state = switch (result) {
      Ok<SearchPage>(:final value) => state.copyWith(
          // Appended, never replaced — the pages already on screen are what the
          // user is looking at.
          items: [...state.items, ...value.items],
          nextCursor: value.nextCursor,
          isLoadingMore: false,
        ),
      // The existing items stay. A failed page four must not blank pages one
      // to three.
      Err<SearchPage>(:final failure) =>
        state.copyWith(isLoadingMore: false, pageError: failure),
    };
  }

  Future<void> refresh() async {
    state = state.copyWith(isRefreshing: true, initialError: null);
    final token = CancelToken();
    final result = await ref.read(searchPropertiesProvider).call(
          ref.read(searchCriteriaControllerProvider),
          cancelToken: token,
        );

    state = switch (result) {
      Ok<SearchPage>(:final value) => PagedState(
          items: value.items,
          nextCursor: value.nextCursor,
          totalEstimate: value.totalEstimate,
          isInitialLoading: false,
          isStale: value.isStale,
          cachedAt: value.cachedAt,
        ),
      // A failed refresh keeps what is on screen and says so, rather than
      // replacing a working list with an error.
      Err<SearchPage>(:final failure) => state.copyWith(
          isRefreshing: false,
          pageError: state.items.isEmpty ? null : failure,
          initialError: state.items.isEmpty ? failure : null,
        ),
    };
  }

  /// Retry only the failed page, keeping everything already loaded.
  Future<void> retryPage() async {
    state = state.copyWith(pageError: null);
    await loadMore();
  }
}

/// Top-rated stays for the home screen.
///
/// A separate provider rather than reusing [SearchResults]: home must not
/// disturb — or be disturbed by — whatever the user last searched for.
@riverpod
Future<List<SearchItemDto>> featuredStays(Ref ref) async {
  final result = await ref.watch(catalogRepositoryProvider).search(
        const SearchCriteria(sort: SearchSort.ratingDesc),
        limit: 6,
      );
  return switch (result) {
    Ok<SearchPage>(:final value) => value.items,
    Err<SearchPage>(:final failure) => throw failure,
  };
}
