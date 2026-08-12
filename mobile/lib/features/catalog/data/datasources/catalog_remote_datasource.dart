import 'package:dio/dio.dart';

import '../../domain/entities/search_criteria.dart';
import '../models/property_models.dart';

/// The catalogue endpoints.
///
/// Data sources speak DTOs and nothing else — no caching, no `Result`, no
/// domain types. They are the thinnest possible wrapper over HTTP, which is
/// what makes the repository above them the only place that decides anything.
class CatalogRemoteDataSource {
  const CatalogRemoteDataSource(this._dio);

  final Dio _dio;

  Future<SearchPageDto> search(
    SearchCriteria criteria, {
    String? cursor,
    int limit = 20,
    CancelToken? cancelToken,
  }) async {
    final response = await _dio.get<Map<String, dynamic>>(
      '/search',
      cancelToken: cancelToken,
      // Nulls are stripped so an absent filter is absent from the query string
      // rather than sent as the string "null", which the server would try to
      // parse and reject.
      queryParameters: <String, dynamic>{
        if (criteria.query != null) 'q': criteria.query,
        if (criteria.cityId != null) 'city_id': criteria.cityId,
        if (criteria.checkIn != null) 'check_in': criteria.checkIn,
        if (criteria.checkOut != null) 'check_out': criteria.checkOut,
        'adults': criteria.adults,
        if (criteria.children > 0) 'children': criteria.children,
        if (criteria.infants > 0) 'infants': criteria.infants,
        'rooms': criteria.rooms,
        // Repeated keys, not comma-joined: the API declares these as list
        // params and parses `?amenity=wifi&amenity=pool`.
        if (criteria.propertyTypes.isNotEmpty) 'property_type': criteria.propertyTypes,
        if (criteria.amenities.isNotEmpty) 'amenity': criteria.amenities,
        if (criteria.minPriceMinor != null) 'min_price': criteria.minPriceMinor,
        if (criteria.maxPriceMinor != null) 'max_price': criteria.maxPriceMinor,
        if (criteria.minRating != null) 'min_rating': criteria.minRating,
        if (criteria.instantBookingOnly) 'instant_booking': true,
        if (criteria.cancellation != null) 'cancellation': criteria.cancellation,
        'sort': criteria.sort.wire,
        'limit': limit,
        // Dart's null-aware element: the key is omitted entirely when null.
        'cursor': ?cursor,
      },
    );
    return SearchPageDto.fromJson(response.data!);
  }

  Future<List<SuggestionDto>> suggest(String query, {CancelToken? cancelToken}) async {
    final response = await _dio.get<List<dynamic>>(
      '/search/suggest',
      queryParameters: {'q': query},
      cancelToken: cancelToken,
    );
    return (response.data ?? [])
        .map((item) => SuggestionDto.fromJson(item as Map<String, dynamic>))
        .toList(growable: false);
  }

  /// Accepts an id or a slug — deep links carry slugs, saved data carries ids.
  Future<PropertyDto> property(String identifier, {CancelToken? cancelToken}) async {
    final response = await _dio.get<Map<String, dynamic>>(
      '/properties/$identifier',
      cancelToken: cancelToken,
    );
    return PropertyDto.fromJson(response.data!);
  }

  Future<QuoteDto> quote({
    required String propertyId,
    required String roomTypeId,
    required String checkIn,
    required String checkOut,
    required int adults,
    int children = 0,
    int infants = 0,
    int rooms = 1,
    CancelToken? cancelToken,
  }) async {
    final response = await _dio.post<Map<String, dynamic>>(
      '/properties/$propertyId/quote',
      cancelToken: cancelToken,
      data: {
        'room_type_id': roomTypeId,
        'check_in': checkIn,
        'check_out': checkOut,
        'adults': adults,
        'children': children,
        'infants': infants,
        'rooms': rooms,
      },
    );
    return QuoteDto.fromJson(response.data!);
  }

  Future<CalendarDto> availability({
    required String propertyId,
    required String from,
    required String to,
    CancelToken? cancelToken,
  }) async {
    final response = await _dio.get<Map<String, dynamic>>(
      '/properties/$propertyId/availability',
      queryParameters: {'from_date': from, 'to_date': to},
      cancelToken: cancelToken,
    );
    return CalendarDto.fromJson(response.data!);
  }

  Future<List<AmenityDto>> amenities({CancelToken? cancelToken}) async {
    final response = await _dio.get<List<dynamic>>(
      '/amenities',
      cancelToken: cancelToken,
    );
    return (response.data ?? [])
        .map((item) => AmenityDto.fromJson(item as Map<String, dynamic>))
        .toList(growable: false);
  }
}
