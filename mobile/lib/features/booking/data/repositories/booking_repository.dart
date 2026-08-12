import 'package:dio/dio.dart';

import '../../../../core/error/failure.dart';
import '../../../../core/network/result.dart';
import '../../../../core/storage/cache_store.dart';
import '../models/booking_models.dart';

class BookingPage {
  const BookingPage({
    required this.items,
    this.nextCursor,
    this.isStale = false,
    this.cachedAt,
  });

  final List<BookingDto> items;
  final String? nextCursor;
  final bool isStale;
  final DateTime? cachedAt;

  bool get hasMore => nextCursor != null;
}

/// Bookings and payments.
///
/// The caching policy here inverts the catalogue's, on purpose. A stale search
/// result is a wrong price; a stale *booking* is a guest at a reception desk
/// with no signal who still needs their reference number and address. So
/// bookings are cached generously and served offline without apology — the data
/// is a record of something that already happened.
class BookingRepository {
  const BookingRepository({
    required Dio dio,
    required CacheStore cache,
  })  : _dio = dio,
        _cache = cache;

  final Dio _dio;
  final CacheStore _cache;

  /// [idempotencyKey] is required, not optional. A double-tapped "Reserve" is
  /// two rooms held on real inventory and one of them abandoned; the key is
  /// what makes the second attempt return the first booking.
  Future<Result<BookingDto>> create({
    required String propertyId,
    required String roomTypeId,
    required String checkIn,
    required String checkOut,
    required int adults,
    required int children,
    required int infants,
    required int rooms,
    required String guestName,
    required String guestEmail,
    required String guestPhone,
    required int quotedTotalMinor,
    required String idempotencyKey,
    String? specialRequests,
  }) =>
      guard(() async {
        final response = await _dio.post<Map<String, dynamic>>(
          '/bookings',
          options: Options(headers: {'Idempotency-Key': idempotencyKey}),
          data: {
            'property_id': propertyId,
            'room_type_id': roomTypeId,
            'check_in': checkIn,
            'check_out': checkOut,
            'adults': adults,
            'children': children,
            'infants': infants,
            'rooms': rooms,
            'guest_name': guestName,
            'guest_email': guestEmail,
            'guest_phone': guestPhone,
            'special_requests': specialRequests,
            // Sent so the server can reject a stale price with 409 instead of
            // silently charging a different amount from the one shown.
            'quoted_total_minor': quotedTotalMinor,
            'source': 'android',
          },
        );
        final booking = BookingDto.fromJson(response.data!);
        await _cache.write(CacheKeys.booking(booking.id), booking.toJson());
        return booking;
      });

  Future<Result<BookingPage>> list({
    String? status,
    bool? upcoming,
    String? cursor,
    int limit = 20,
    CancelToken? cancelToken,
  }) async {
    final isFirstPage = cursor == null;

    final result = await guard(() async {
      final response = await _dio.get<Map<String, dynamic>>(
        '/bookings',
        cancelToken: cancelToken,
        queryParameters: {
          'status': ?status,
          'upcoming': ?upcoming,
          'cursor': ?cursor,
          'limit': limit,
        },
      );
      final page = BookingListDto.fromJson(response.data!);
      if (isFirstPage && status == null && upcoming == null) {
        await _cache.writeList(
          CacheKeys.bookings,
          page.items.map((b) => b.toJson()).toList(growable: false),
        );
      }
      return BookingPage(items: page.items, nextCursor: page.nextCursor);
    });

    if (result case Err<BookingPage>(:final failure)
        when isFirstPage && failure.isOffline) {
      final entry = _cache.readList(CacheKeys.bookings, BookingDto.fromJson);
      if (entry != null) {
        return Result.ok(
          BookingPage(
            items: entry.value,
            isStale: true,
            cachedAt: entry.storedAt,
          ),
        );
      }
    }
    return result;
  }

  Future<Result<BookingDto>> get(String identifier, {CancelToken? cancelToken}) async {
    final result = await guard(() async {
      final response = await _dio.get<Map<String, dynamic>>(
        '/bookings/$identifier',
        cancelToken: cancelToken,
      );
      final booking = BookingDto.fromJson(response.data!);
      await _cache.write(CacheKeys.booking(booking.id), booking.toJson());
      return booking;
    });

    if (result case Err<BookingDto>(:final failure) when failure.isOffline) {
      final entry = _cache.read(CacheKeys.booking(identifier), BookingDto.fromJson);
      if (entry != null) return Result.ok(entry.value);
    }
    return result;
  }

  Future<Result<RefundPreviewDto>> refundPreview(String bookingId) =>
      // Never cached: the refundable amount depends on how long until check-in,
      // so it is time-sensitive by construction.
      guard(() async {
        final response = await _dio.get<Map<String, dynamic>>(
          '/bookings/$bookingId/refund-preview',
        );
        return RefundPreviewDto.fromJson(response.data!);
      });

  Future<Result<BookingDto>> cancel(String bookingId, {String? reason}) =>
      guard(() async {
        final response = await _dio.post<Map<String, dynamic>>(
          '/bookings/$bookingId/cancel',
          data: {'reason': reason},
        );
        final booking = BookingDto.fromJson(response.data!);
        await _cache.write(CacheKeys.booking(booking.id), booking.toJson());
        return booking;
      });

  // ── payments ────────────────────────────────────────────────────────────

  Future<Result<CheckoutSessionDto>> createOrder(String bookingId) =>
      guard(() async {
        final response = await _dio.post<Map<String, dynamic>>(
          '/payments/orders',
          data: {'booking_id': bookingId},
        );
        return CheckoutSessionDto.fromJson(response.data!);
      });

  Future<Result<PaymentResultDto>> verifyPayment({
    required String orderId,
    required String paymentId,
    required String signature,
  }) =>
      guard(() async {
        final response = await _dio.post<Map<String, dynamic>>(
          '/payments/verify',
          data: {
            'razorpay_order_id': orderId,
            'razorpay_payment_id': paymentId,
            'razorpay_signature': signature,
          },
        );
        return PaymentResultDto.fromJson(response.data!);
      });
}
