// GENERATED CODE - DO NOT MODIFY BY HAND

part of 'search_provider.dart';

// **************************************************************************
// RiverpodGenerator
// **************************************************************************

// GENERATED CODE - DO NOT MODIFY BY HAND
// ignore_for_file: type=lint, type=warning
/// The current search criteria.
///
/// Held apart from the results so that changing a filter is one notification
/// and the result list is free to decide what to do about it — rather than
/// every filter tap tearing down and rebuilding the list provider.

@ProviderFor(SearchCriteriaController)
final searchCriteriaControllerProvider = SearchCriteriaControllerProvider._();

/// The current search criteria.
///
/// Held apart from the results so that changing a filter is one notification
/// and the result list is free to decide what to do about it — rather than
/// every filter tap tearing down and rebuilding the list provider.
final class SearchCriteriaControllerProvider
    extends $NotifierProvider<SearchCriteriaController, SearchCriteria> {
  /// The current search criteria.
  ///
  /// Held apart from the results so that changing a filter is one notification
  /// and the result list is free to decide what to do about it — rather than
  /// every filter tap tearing down and rebuilding the list provider.
  SearchCriteriaControllerProvider._()
    : super(
        from: null,
        argument: null,
        retry: null,
        name: r'searchCriteriaControllerProvider',
        isAutoDispose: true,
        dependencies: null,
        $allTransitiveDependencies: null,
      );

  @override
  String debugGetCreateSourceHash() => _$searchCriteriaControllerHash();

  @$internal
  @override
  SearchCriteriaController create() => SearchCriteriaController();

  /// {@macro riverpod.override_with_value}
  Override overrideWithValue(SearchCriteria value) {
    return $ProviderOverride(
      origin: this,
      providerOverride: $SyncValueProvider<SearchCriteria>(value),
    );
  }
}

String _$searchCriteriaControllerHash() =>
    r'c277b2c0ff717c38194c63bdbd5eeafdd7650b19';

/// The current search criteria.
///
/// Held apart from the results so that changing a filter is one notification
/// and the result list is free to decide what to do about it — rather than
/// every filter tap tearing down and rebuilding the list provider.

abstract class _$SearchCriteriaController extends $Notifier<SearchCriteria> {
  SearchCriteria build();
  @$mustCallSuper
  @override
  void runBuild() {
    final ref = this.ref as $Ref<SearchCriteria, SearchCriteria>;
    final element =
        ref.element
            as $ClassProviderElement<
              AnyNotifier<SearchCriteria, SearchCriteria>,
              SearchCriteria,
              Object?,
              Object?
            >;
    element.handleCreate(ref, build);
  }
}

/// The search results, paginated.
///
/// Watches the criteria, so a filter change automatically starts a fresh first
/// page — and the cursor is dropped with it, because page three of the previous
/// result set means nothing in the new one.

@ProviderFor(SearchResults)
final searchResultsProvider = SearchResultsProvider._();

/// The search results, paginated.
///
/// Watches the criteria, so a filter change automatically starts a fresh first
/// page — and the cursor is dropped with it, because page three of the previous
/// result set means nothing in the new one.
final class SearchResultsProvider
    extends $NotifierProvider<SearchResults, PagedState<SearchItemDto>> {
  /// The search results, paginated.
  ///
  /// Watches the criteria, so a filter change automatically starts a fresh first
  /// page — and the cursor is dropped with it, because page three of the previous
  /// result set means nothing in the new one.
  SearchResultsProvider._()
    : super(
        from: null,
        argument: null,
        retry: null,
        name: r'searchResultsProvider',
        isAutoDispose: true,
        dependencies: null,
        $allTransitiveDependencies: null,
      );

  @override
  String debugGetCreateSourceHash() => _$searchResultsHash();

  @$internal
  @override
  SearchResults create() => SearchResults();

  /// {@macro riverpod.override_with_value}
  Override overrideWithValue(PagedState<SearchItemDto> value) {
    return $ProviderOverride(
      origin: this,
      providerOverride: $SyncValueProvider<PagedState<SearchItemDto>>(value),
    );
  }
}

String _$searchResultsHash() => r'246381fba65b8d351e61676d00b0dae73b9001c7';

/// The search results, paginated.
///
/// Watches the criteria, so a filter change automatically starts a fresh first
/// page — and the cursor is dropped with it, because page three of the previous
/// result set means nothing in the new one.

abstract class _$SearchResults extends $Notifier<PagedState<SearchItemDto>> {
  PagedState<SearchItemDto> build();
  @$mustCallSuper
  @override
  void runBuild() {
    final ref =
        this.ref as $Ref<PagedState<SearchItemDto>, PagedState<SearchItemDto>>;
    final element =
        ref.element
            as $ClassProviderElement<
              AnyNotifier<PagedState<SearchItemDto>, PagedState<SearchItemDto>>,
              PagedState<SearchItemDto>,
              Object?,
              Object?
            >;
    element.handleCreate(ref, build);
  }
}

/// Top-rated stays for the home screen.
///
/// A separate provider rather than reusing [SearchResults]: home must not
/// disturb — or be disturbed by — whatever the user last searched for.

@ProviderFor(featuredStays)
final featuredStaysProvider = FeaturedStaysProvider._();

/// Top-rated stays for the home screen.
///
/// A separate provider rather than reusing [SearchResults]: home must not
/// disturb — or be disturbed by — whatever the user last searched for.

final class FeaturedStaysProvider
    extends
        $FunctionalProvider<
          AsyncValue<List<SearchItemDto>>,
          List<SearchItemDto>,
          FutureOr<List<SearchItemDto>>
        >
    with
        $FutureModifier<List<SearchItemDto>>,
        $FutureProvider<List<SearchItemDto>> {
  /// Top-rated stays for the home screen.
  ///
  /// A separate provider rather than reusing [SearchResults]: home must not
  /// disturb — or be disturbed by — whatever the user last searched for.
  FeaturedStaysProvider._()
    : super(
        from: null,
        argument: null,
        retry: null,
        name: r'featuredStaysProvider',
        isAutoDispose: true,
        dependencies: null,
        $allTransitiveDependencies: null,
      );

  @override
  String debugGetCreateSourceHash() => _$featuredStaysHash();

  @$internal
  @override
  $FutureProviderElement<List<SearchItemDto>> $createElement(
    $ProviderPointer pointer,
  ) => $FutureProviderElement(pointer);

  @override
  FutureOr<List<SearchItemDto>> create(Ref ref) {
    return featuredStays(ref);
  }
}

String _$featuredStaysHash() => r'ac67c85e76ca16898a84071e4c2e0e509d7684b0';
