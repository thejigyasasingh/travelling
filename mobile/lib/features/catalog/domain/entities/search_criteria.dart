import 'package:freezed_annotation/freezed_annotation.dart';

import '../../../../core/utils/dates.dart';

part 'search_criteria.freezed.dart';

/// What the guest is looking for.
///
/// A value object, so it can be a cache key, a provider argument and an
/// equality check all at once — Riverpod rebuilds a family provider only when
/// its argument changes, which needs real value equality.
@freezed
abstract class SearchCriteria with _$SearchCriteria {
  const factory SearchCriteria({
    String? query,
    String? cityId,
    IsoDate? checkIn,
    IsoDate? checkOut,
    @Default(2) int adults,
    @Default(0) int children,
    @Default(0) int infants,
    @Default(1) int rooms,
    @Default(<String>[]) List<String> propertyTypes,
    @Default(<String>[]) List<String> amenities,
    int? minPriceMinor,
    int? maxPriceMinor,
    double? minRating,
    @Default(false) bool instantBookingOnly,
    String? cancellation,
    @Default(SearchSort.relevance) SearchSort sort,
  }) = _SearchCriteria;

  const SearchCriteria._();

  /// Whether the search has dates, which decides whether prices are stay
  /// totals or nightly "from" rates. The two are labelled differently and
  /// never interchanged.
  bool get hasDates => isValidStay(checkIn, checkOut);

  int get nights => hasDates ? nightsBetween(checkIn!, checkOut!) : 0;

  int get activeFilterCount =>
      propertyTypes.length +
      amenities.length +
      (minPriceMinor != null || maxPriceMinor != null ? 1 : 0) +
      (minRating != null ? 1 : 0) +
      (instantBookingOnly ? 1 : 0) +
      (cancellation != null ? 1 : 0);

  /// A stable string for cache keys. Deliberately not `toString()`, which
  /// Freezed formats for humans and may change.
  String get cacheSignature => [
        query ?? '',
        cityId ?? '',
        checkIn ?? '',
        checkOut ?? '',
        adults,
        children,
        rooms,
        propertyTypes.join(','),
        amenities.join(','),
        minPriceMinor ?? '',
        maxPriceMinor ?? '',
        minRating ?? '',
        instantBookingOnly,
        cancellation ?? '',
        sort.name,
      ].join('|');
}

/// Sort orders.
///
/// The wire values are **exactly** what the API's `SearchSort` accepts —
/// `rating_desc`, not `rating`. An unrecognised value is rejected with a 422,
/// and before the server validated these it hung the connection instead, so a
/// plausible-looking guess here is worse than a compile error.
enum SearchSort {
  relevance('relevance', 'Most relevant'),
  priceAsc('price_asc', 'Price: low to high'),
  priceDesc('price_desc', 'Price: high to low'),
  ratingDesc('rating_desc', 'Guest rating'),
  distanceAsc('distance_asc', 'Distance'),
  newest('newest', 'Newest');

  const SearchSort(this.wire, this.label);

  final String wire;
  final String label;
}

/// The five property types the platform lists.
enum PropertyKind {
  hotel('hotel', 'Hotels'),
  villa('villa', 'Villas'),
  apartment('apartment', 'Apartments'),
  homestay('homestay', 'Homestays'),
  resort('resort', 'Resorts');

  const PropertyKind(this.wire, this.label);

  final String wire;
  final String label;

  static String labelFor(String wire) => PropertyKind.values
      .firstWhere(
        (k) => k.wire == wire,
        orElse: () => PropertyKind.hotel,
      )
      .label;
}
