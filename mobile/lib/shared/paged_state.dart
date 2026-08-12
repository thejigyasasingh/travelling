import 'package:freezed_annotation/freezed_annotation.dart';

import '../core/error/failure.dart';

part 'paged_state.freezed.dart';

/// The state of an infinitely-scrolling list.
///
/// A single record rather than a `AsyncValue<List<T>>`, because a paged list
/// has states `AsyncValue` cannot express and a user can plainly see:
///
/// * items on screen **and** a spinner at the bottom (loading page four);
/// * items on screen **and** an error (page four failed — the first three are
///   still perfectly good and must not be thrown away);
/// * items on screen that are **stale**, restored from cache while offline.
///
/// Collapsing those into "loading" or "error" is what produces a list that
/// blanks itself when the last page fails.
@freezed
abstract class PagedState<T> with _$PagedState<T> {
  const factory PagedState({
    @Default(<Never>[]) List<T> items,
    String? nextCursor,
    int? totalEstimate,
    /// The first load, with nothing to show yet.
    @Default(true) bool isInitialLoading,
    /// Fetching the next page, with items already on screen.
    @Default(false) bool isLoadingMore,
    /// A pull-to-refresh over existing items.
    @Default(false) bool isRefreshing,
    /// Failed the *first* load: there is nothing to show but this.
    Failure? initialError,
    /// Failed a *subsequent* page: the list stands, with a retry at the end.
    Failure? pageError,
    /// Served from cache because the network was unreachable.
    @Default(false) bool isStale,
    DateTime? cachedAt,
  }) = _PagedState<T>;

  const PagedState._();

  bool get hasMore => nextCursor != null;
  bool get isEmpty => items.isEmpty && !isInitialLoading && initialError == null;
  bool get canLoadMore => hasMore && !isLoadingMore && pageError == null;

  /// How many rows the list should build: the items, plus one for the loading
  /// indicator, the page-error retry, or the end-of-results marker.
  int get rowCount => items.length + (hasMore || pageError != null ? 1 : 0);
}
