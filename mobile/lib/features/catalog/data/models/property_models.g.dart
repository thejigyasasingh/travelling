// GENERATED CODE - DO NOT MODIFY BY HAND

part of 'property_models.dart';

// **************************************************************************
// JsonSerializableGenerator
// **************************************************************************

_ImageDto _$ImageDtoFromJson(Map<String, dynamic> json) => _ImageDto(
  id: json['id'] as String,
  url: json['url'] as String,
  position: (json['position'] as num?)?.toInt() ?? 0,
  isCover: json['is_cover'] as bool? ?? false,
  altText: json['alt_text'] as String?,
  caption: json['caption'] as String?,
);

Map<String, dynamic> _$ImageDtoToJson(_ImageDto instance) => <String, dynamic>{
  'id': instance.id,
  'url': instance.url,
  'position': instance.position,
  'is_cover': instance.isCover,
  'alt_text': instance.altText,
  'caption': instance.caption,
};

_RoomTypeDto _$RoomTypeDtoFromJson(Map<String, dynamic> json) => _RoomTypeDto(
  id: json['id'] as String,
  name: json['name'] as String,
  description: json['description'] as String?,
  bedType: json['bed_type'] as String? ?? '',
  maxAdults: (json['max_adults'] as num?)?.toInt() ?? 2,
  maxChildren: (json['max_children'] as num?)?.toInt() ?? 0,
  totalUnits: (json['total_units'] as num?)?.toInt() ?? 1,
  sizeSqft: (json['size_sqft'] as num?)?.toInt(),
  amenityCodes:
      (json['amenity_codes'] as List<dynamic>?)
          ?.map((e) => e as String)
          .toList() ??
      const <String>[],
  baseRateMinor: (json['base_rate_minor'] as num?)?.toInt() ?? 0,
  currency: json['currency'] as String? ?? 'INR',
  minNights: (json['min_nights'] as num?)?.toInt() ?? 1,
  unitsAvailable: (json['units_available'] as num?)?.toInt(),
  quoteTotalMinor: (json['quote_total_minor'] as num?)?.toInt(),
);

Map<String, dynamic> _$RoomTypeDtoToJson(_RoomTypeDto instance) =>
    <String, dynamic>{
      'id': instance.id,
      'name': instance.name,
      'description': instance.description,
      'bed_type': instance.bedType,
      'max_adults': instance.maxAdults,
      'max_children': instance.maxChildren,
      'total_units': instance.totalUnits,
      'size_sqft': instance.sizeSqft,
      'amenity_codes': instance.amenityCodes,
      'base_rate_minor': instance.baseRateMinor,
      'currency': instance.currency,
      'min_nights': instance.minNights,
      'units_available': instance.unitsAvailable,
      'quote_total_minor': instance.quoteTotalMinor,
    };

_PropertyDto _$PropertyDtoFromJson(Map<String, dynamic> json) => _PropertyDto(
  id: json['id'] as String,
  slug: json['slug'] as String,
  name: json['name'] as String,
  propertyType: json['property_type'] as String? ?? '',
  description: json['description'] as String? ?? '',
  address: json['address'] as String? ?? '',
  city: json['city'] as String? ?? '',
  state: json['state'] as String?,
  countryCode: json['country_code'] as String? ?? 'IN',
  latitude: (json['latitude'] as num?)?.toDouble(),
  longitude: (json['longitude'] as num?)?.toDouble(),
  locationIsApproximate: json['location_is_approximate'] as bool? ?? true,
  amenityCodes:
      (json['amenity_codes'] as List<dynamic>?)
          ?.map((e) => e as String)
          .toList() ??
      const <String>[],
  images:
      (json['images'] as List<dynamic>?)
          ?.map((e) => ImageDto.fromJson(e as Map<String, dynamic>))
          .toList() ??
      const <ImageDto>[],
  roomTypes:
      (json['room_types'] as List<dynamic>?)
          ?.map((e) => RoomTypeDto.fromJson(e as Map<String, dynamic>))
          .toList() ??
      const <RoomTypeDto>[],
  cancellationPolicy: json['cancellation_policy'] as String? ?? 'moderate',
  checkInFrom: json['check_in_from'] as String? ?? '',
  checkOutBy: json['check_out_by'] as String? ?? '',
  houseRules:
      (json['house_rules'] as List<dynamic>?)
          ?.map((e) => e as String)
          .toList() ??
      const <String>[],
  instantBooking: json['instant_booking'] as bool? ?? false,
  reviewAverage: (json['review_average'] as num?)?.toDouble() ?? 0.0,
  reviewCount: (json['review_count'] as num?)?.toInt() ?? 0,
  currency: json['currency'] as String? ?? 'INR',
  vendorId: json['vendor_id'] as String? ?? '',
);

Map<String, dynamic> _$PropertyDtoToJson(_PropertyDto instance) =>
    <String, dynamic>{
      'id': instance.id,
      'slug': instance.slug,
      'name': instance.name,
      'property_type': instance.propertyType,
      'description': instance.description,
      'address': instance.address,
      'city': instance.city,
      'state': instance.state,
      'country_code': instance.countryCode,
      'latitude': instance.latitude,
      'longitude': instance.longitude,
      'location_is_approximate': instance.locationIsApproximate,
      'amenity_codes': instance.amenityCodes,
      'images': instance.images,
      'room_types': instance.roomTypes,
      'cancellation_policy': instance.cancellationPolicy,
      'check_in_from': instance.checkInFrom,
      'check_out_by': instance.checkOutBy,
      'house_rules': instance.houseRules,
      'instant_booking': instance.instantBooking,
      'review_average': instance.reviewAverage,
      'review_count': instance.reviewCount,
      'currency': instance.currency,
      'vendor_id': instance.vendorId,
    };

_SearchItemDto _$SearchItemDtoFromJson(Map<String, dynamic> json) =>
    _SearchItemDto(
      id: json['id'] as String,
      slug: json['slug'] as String,
      name: json['name'] as String,
      propertyType: json['property_type'] as String? ?? '',
      city: json['city'] as String? ?? '',
      countryCode: json['country_code'] as String? ?? 'IN',
      latitude: (json['latitude'] as num?)?.toDouble(),
      longitude: (json['longitude'] as num?)?.toDouble(),
      distanceM: (json['distance_m'] as num?)?.toDouble(),
      coverImageUrl: json['cover_image_url'] as String?,
      reviewAverage: (json['review_average'] as num?)?.toDouble() ?? 0.0,
      reviewCount: (json['review_count'] as num?)?.toInt() ?? 0,
      amenityCodes:
          (json['amenity_codes'] as List<dynamic>?)
              ?.map((e) => e as String)
              .toList() ??
          const <String>[],
      instantBooking: json['instant_booking'] as bool? ?? false,
      cancellationPolicy: json['cancellation_policy'] as String? ?? 'moderate',
      maxOccupancy: (json['max_occupancy'] as num?)?.toInt() ?? 2,
      fromPriceMinor: (json['from_price_minor'] as num?)?.toInt(),
      totalPriceMinor: (json['total_price_minor'] as num?)?.toInt(),
      currency: json['currency'] as String? ?? 'INR',
      isAvailable: json['is_available'] as bool? ?? true,
    );

Map<String, dynamic> _$SearchItemDtoToJson(_SearchItemDto instance) =>
    <String, dynamic>{
      'id': instance.id,
      'slug': instance.slug,
      'name': instance.name,
      'property_type': instance.propertyType,
      'city': instance.city,
      'country_code': instance.countryCode,
      'latitude': instance.latitude,
      'longitude': instance.longitude,
      'distance_m': instance.distanceM,
      'cover_image_url': instance.coverImageUrl,
      'review_average': instance.reviewAverage,
      'review_count': instance.reviewCount,
      'amenity_codes': instance.amenityCodes,
      'instant_booking': instance.instantBooking,
      'cancellation_policy': instance.cancellationPolicy,
      'max_occupancy': instance.maxOccupancy,
      'from_price_minor': instance.fromPriceMinor,
      'total_price_minor': instance.totalPriceMinor,
      'currency': instance.currency,
      'is_available': instance.isAvailable,
    };

_SearchPageDto _$SearchPageDtoFromJson(Map<String, dynamic> json) =>
    _SearchPageDto(
      items:
          (json['items'] as List<dynamic>?)
              ?.map((e) => SearchItemDto.fromJson(e as Map<String, dynamic>))
              .toList() ??
          const <SearchItemDto>[],
      nextCursor: json['next_cursor'] as String?,
      totalEstimate: (json['total_estimate'] as num?)?.toInt(),
      appliedRadiusM: (json['applied_radius_m'] as num?)?.toInt(),
    );

Map<String, dynamic> _$SearchPageDtoToJson(_SearchPageDto instance) =>
    <String, dynamic>{
      'items': instance.items,
      'next_cursor': instance.nextCursor,
      'total_estimate': instance.totalEstimate,
      'applied_radius_m': instance.appliedRadiusM,
    };

_SuggestionDto _$SuggestionDtoFromJson(Map<String, dynamic> json) =>
    _SuggestionDto(
      kind: json['kind'] as String,
      id: json['id'] as String,
      label: json['label'] as String,
      sublabel: json['sublabel'] as String?,
      slug: json['slug'] as String? ?? '',
    );

Map<String, dynamic> _$SuggestionDtoToJson(_SuggestionDto instance) =>
    <String, dynamic>{
      'kind': instance.kind,
      'id': instance.id,
      'label': instance.label,
      'sublabel': instance.sublabel,
      'slug': instance.slug,
    };

_AmenityDto _$AmenityDtoFromJson(Map<String, dynamic> json) => _AmenityDto(
  code: json['code'] as String,
  label: json['label'] as String,
  category: json['category'] as String? ?? '',
  icon: json['icon'] as String?,
  isFilterable: json['is_filterable'] as bool? ?? true,
);

Map<String, dynamic> _$AmenityDtoToJson(_AmenityDto instance) =>
    <String, dynamic>{
      'code': instance.code,
      'label': instance.label,
      'category': instance.category,
      'icon': instance.icon,
      'is_filterable': instance.isFilterable,
    };

_QuoteNightDto _$QuoteNightDtoFromJson(Map<String, dynamic> json) =>
    _QuoteNightDto(
      date: json['date'] as String,
      amountMinor: (json['amount_minor'] as num?)?.toInt() ?? 0,
      source: json['source'] as String? ?? '',
    );

Map<String, dynamic> _$QuoteNightDtoToJson(_QuoteNightDto instance) =>
    <String, dynamic>{
      'date': instance.date,
      'amount_minor': instance.amountMinor,
      'source': instance.source,
    };

_QuoteDto _$QuoteDtoFromJson(Map<String, dynamic> json) => _QuoteDto(
  roomTypeId: json['room_type_id'] as String? ?? '',
  nights:
      (json['nights'] as List<dynamic>?)
          ?.map((e) => QuoteNightDto.fromJson(e as Map<String, dynamic>))
          .toList() ??
      const <QuoteNightDto>[],
  accommodationMinor: (json['accommodation_minor'] as num?)?.toInt() ?? 0,
  extraGuestMinor: (json['extra_guest_minor'] as num?)?.toInt() ?? 0,
  cleaningFeeMinor: (json['cleaning_fee_minor'] as num?)?.toInt() ?? 0,
  taxMinor: (json['tax_minor'] as num?)?.toInt() ?? 0,
  totalMinor: (json['total_minor'] as num?)?.toInt() ?? 0,
  averageNightlyMinor: (json['average_nightly_minor'] as num?)?.toInt() ?? 0,
  currency: json['currency'] as String? ?? 'INR',
  isAvailable: json['is_available'] as bool? ?? false,
  unavailableDates:
      (json['unavailable_dates'] as List<dynamic>?)
          ?.map((e) => e as String)
          .toList() ??
      const <String>[],
);

Map<String, dynamic> _$QuoteDtoToJson(_QuoteDto instance) => <String, dynamic>{
  'room_type_id': instance.roomTypeId,
  'nights': instance.nights,
  'accommodation_minor': instance.accommodationMinor,
  'extra_guest_minor': instance.extraGuestMinor,
  'cleaning_fee_minor': instance.cleaningFeeMinor,
  'tax_minor': instance.taxMinor,
  'total_minor': instance.totalMinor,
  'average_nightly_minor': instance.averageNightlyMinor,
  'currency': instance.currency,
  'is_available': instance.isAvailable,
  'unavailable_dates': instance.unavailableDates,
};

_CalendarDayDto _$CalendarDayDtoFromJson(Map<String, dynamic> json) =>
    _CalendarDayDto(
      date: json['date'] as String,
      isBlocked: json['is_blocked'] as bool? ?? false,
      unitsAvailable: (json['units_available'] as num?)?.toInt(),
      rateMinor: (json['rate_minor'] as num?)?.toInt(),
    );

Map<String, dynamic> _$CalendarDayDtoToJson(_CalendarDayDto instance) =>
    <String, dynamic>{
      'date': instance.date,
      'is_blocked': instance.isBlocked,
      'units_available': instance.unitsAvailable,
      'rate_minor': instance.rateMinor,
    };

_CalendarDto _$CalendarDtoFromJson(Map<String, dynamic> json) => _CalendarDto(
  roomTypeId: json['room_type_id'] as String? ?? '',
  currency: json['currency'] as String? ?? 'INR',
  days:
      (json['days'] as List<dynamic>?)
          ?.map((e) => CalendarDayDto.fromJson(e as Map<String, dynamic>))
          .toList() ??
      const <CalendarDayDto>[],
);

Map<String, dynamic> _$CalendarDtoToJson(_CalendarDto instance) =>
    <String, dynamic>{
      'room_type_id': instance.roomTypeId,
      'currency': instance.currency,
      'days': instance.days,
    };
