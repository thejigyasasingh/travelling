import 'package:freezed_annotation/freezed_annotation.dart';

part 'property_models.freezed.dart';
part 'property_models.g.dart';

/// The wire format, exactly as the API sends it.
///
/// `snake_case`, mapped by `@JsonKey`. These shapes were verified against a
/// running server rather than read off a schema listing — a schema says what
/// *should* be sent, and the difference between the two is where the expensive
/// bugs live.
///
/// Models are `Freezed` for value equality, which Riverpod relies on to decide
/// whether a rebuild is needed: without it, every refetch of identical data
/// repaints the list.

@freezed
abstract class ImageDto with _$ImageDto {
  const factory ImageDto({
    required String id,
    required String url,
    @Default(0) int position,
    @JsonKey(name: 'is_cover') @Default(false) bool isCover,
    @JsonKey(name: 'alt_text') String? altText,
    String? caption,
  }) = _ImageDto;

  factory ImageDto.fromJson(Map<String, dynamic> json) =>
      _$ImageDtoFromJson(json);
}

@freezed
abstract class RoomTypeDto with _$RoomTypeDto {
  const factory RoomTypeDto({
    required String id,
    required String name,
    String? description,
    @JsonKey(name: 'bed_type') @Default('') String bedType,
    @JsonKey(name: 'max_adults') @Default(2) int maxAdults,
    @JsonKey(name: 'max_children') @Default(0) int maxChildren,
    @JsonKey(name: 'total_units') @Default(1) int totalUnits,
    @JsonKey(name: 'size_sqft') int? sizeSqft,
    @JsonKey(name: 'amenity_codes') @Default(<String>[]) List<String> amenityCodes,
    @JsonKey(name: 'base_rate_minor') @Default(0) int baseRateMinor,
    @Default('INR') String currency,
    @JsonKey(name: 'min_nights') @Default(1) int minNights,
    /// Present only when the request carried dates. `null` means "not asked",
    /// which is a different thing from "none left" and must not render as 0.
    @JsonKey(name: 'units_available') int? unitsAvailable,
    @JsonKey(name: 'quote_total_minor') int? quoteTotalMinor,
  }) = _RoomTypeDto;

  factory RoomTypeDto.fromJson(Map<String, dynamic> json) =>
      _$RoomTypeDtoFromJson(json);
}

@freezed
abstract class PropertyDto with _$PropertyDto {
  const factory PropertyDto({
    required String id,
    required String slug,
    required String name,
    @JsonKey(name: 'property_type') @Default('') String propertyType,
    @Default('') String description,
    @Default('') String address,
    @Default('') String city,
    String? state,
    @JsonKey(name: 'country_code') @Default('IN') String countryCode,
    double? latitude,
    double? longitude,
    /// The pin is fuzzed until a booking is confirmed. Not a bug to "fix":
    /// publishing an exact address tells anyone where an unoccupied home is.
    @JsonKey(name: 'location_is_approximate') @Default(true) bool locationIsApproximate,
    @JsonKey(name: 'amenity_codes') @Default(<String>[]) List<String> amenityCodes,
    @Default(<ImageDto>[]) List<ImageDto> images,
    @JsonKey(name: 'room_types') @Default(<RoomTypeDto>[]) List<RoomTypeDto> roomTypes,
    @JsonKey(name: 'cancellation_policy') @Default('moderate') String cancellationPolicy,
    @JsonKey(name: 'check_in_from') @Default('') String checkInFrom,
    @JsonKey(name: 'check_out_by') @Default('') String checkOutBy,
    @JsonKey(name: 'house_rules') @Default(<String>[]) List<String> houseRules,
    @JsonKey(name: 'instant_booking') @Default(false) bool instantBooking,
    @JsonKey(name: 'review_average') @Default(0.0) double reviewAverage,
    @JsonKey(name: 'review_count') @Default(0) int reviewCount,
    @Default('INR') String currency,
    @JsonKey(name: 'vendor_id') @Default('') String vendorId,
  }) = _PropertyDto;

  factory PropertyDto.fromJson(Map<String, dynamic> json) =>
      _$PropertyDtoFromJson(json);
}

@freezed
abstract class SearchItemDto with _$SearchItemDto {
  const factory SearchItemDto({
    required String id,
    required String slug,
    required String name,
    @JsonKey(name: 'property_type') @Default('') String propertyType,
    @Default('') String city,
    @JsonKey(name: 'country_code') @Default('IN') String countryCode,
    double? latitude,
    double? longitude,
    @JsonKey(name: 'distance_m') double? distanceM,
    @JsonKey(name: 'cover_image_url') String? coverImageUrl,
    @JsonKey(name: 'review_average') @Default(0.0) double reviewAverage,
    @JsonKey(name: 'review_count') @Default(0) int reviewCount,
    @JsonKey(name: 'amenity_codes') @Default(<String>[]) List<String> amenityCodes,
    @JsonKey(name: 'instant_booking') @Default(false) bool instantBooking,
    @JsonKey(name: 'cancellation_policy') @Default('moderate') String cancellationPolicy,
    @JsonKey(name: 'max_occupancy') @Default(2) int maxOccupancy,
    /// Nightly "from" price. Shown only when there are no dates.
    @JsonKey(name: 'from_price_minor') int? fromPriceMinor,
    /// The total for the searched dates. Never interchanged with the above:
    /// showing a nightly rate where a total is expected is the oldest dark
    /// pattern in travel.
    @JsonKey(name: 'total_price_minor') int? totalPriceMinor,
    @Default('INR') String currency,
    @JsonKey(name: 'is_available') @Default(true) bool isAvailable,
  }) = _SearchItemDto;

  factory SearchItemDto.fromJson(Map<String, dynamic> json) =>
      _$SearchItemDtoFromJson(json);
}

@freezed
abstract class SearchPageDto with _$SearchPageDto {
  const factory SearchPageDto({
    @Default(<SearchItemDto>[]) List<SearchItemDto> items,
    @JsonKey(name: 'next_cursor') String? nextCursor,
    @JsonKey(name: 'total_estimate') int? totalEstimate,
    @JsonKey(name: 'applied_radius_m') int? appliedRadiusM,
  }) = _SearchPageDto;

  factory SearchPageDto.fromJson(Map<String, dynamic> json) =>
      _$SearchPageDtoFromJson(json);
}

@freezed
abstract class SuggestionDto with _$SuggestionDto {
  const factory SuggestionDto({
    required String kind,
    required String id,
    required String label,
    String? sublabel,
    @Default('') String slug,
  }) = _SuggestionDto;

  factory SuggestionDto.fromJson(Map<String, dynamic> json) =>
      _$SuggestionDtoFromJson(json);
}

@freezed
abstract class AmenityDto with _$AmenityDto {
  const factory AmenityDto({
    required String code,
    required String label,
    @Default('') String category,
    String? icon,
    @JsonKey(name: 'is_filterable') @Default(true) bool isFilterable,
  }) = _AmenityDto;

  factory AmenityDto.fromJson(Map<String, dynamic> json) =>
      _$AmenityDtoFromJson(json);
}

@freezed
abstract class QuoteNightDto with _$QuoteNightDto {
  const factory QuoteNightDto({
    required String date,
    @JsonKey(name: 'amount_minor') @Default(0) int amountMinor,
    @Default('') String source,
  }) = _QuoteNightDto;

  factory QuoteNightDto.fromJson(Map<String, dynamic> json) =>
      _$QuoteNightDtoFromJson(json);
}

@freezed
abstract class QuoteDto with _$QuoteDto {
  const factory QuoteDto({
    @JsonKey(name: 'room_type_id') @Default('') String roomTypeId,
    @Default(<QuoteNightDto>[]) List<QuoteNightDto> nights,
    @JsonKey(name: 'accommodation_minor') @Default(0) int accommodationMinor,
    @JsonKey(name: 'extra_guest_minor') @Default(0) int extraGuestMinor,
    @JsonKey(name: 'cleaning_fee_minor') @Default(0) int cleaningFeeMinor,
    @JsonKey(name: 'tax_minor') @Default(0) int taxMinor,
    @JsonKey(name: 'total_minor') @Default(0) int totalMinor,
    @JsonKey(name: 'average_nightly_minor') @Default(0) int averageNightlyMinor,
    @Default('INR') String currency,
    @JsonKey(name: 'is_available') @Default(false) bool isAvailable,
    @JsonKey(name: 'unavailable_dates') @Default(<String>[]) List<String> unavailableDates,
  }) = _QuoteDto;

  factory QuoteDto.fromJson(Map<String, dynamic> json) =>
      _$QuoteDtoFromJson(json);
}

@freezed
abstract class CalendarDayDto with _$CalendarDayDto {
  const factory CalendarDayDto({
    required String date,
    @JsonKey(name: 'is_blocked') @Default(false) bool isBlocked,
    @JsonKey(name: 'units_available') int? unitsAvailable,
    @JsonKey(name: 'rate_minor') int? rateMinor,
  }) = _CalendarDayDto;

  factory CalendarDayDto.fromJson(Map<String, dynamic> json) =>
      _$CalendarDayDtoFromJson(json);
}

@freezed
abstract class CalendarDto with _$CalendarDto {
  const factory CalendarDto({
    @JsonKey(name: 'room_type_id') @Default('') String roomTypeId,
    @Default('INR') String currency,
    @Default(<CalendarDayDto>[]) List<CalendarDayDto> days,
  }) = _CalendarDto;

  factory CalendarDto.fromJson(Map<String, dynamic> json) =>
      _$CalendarDtoFromJson(json);
}
