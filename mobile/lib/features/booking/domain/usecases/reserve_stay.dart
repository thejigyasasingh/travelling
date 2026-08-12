import 'dart:math';

import '../../../../core/error/failure.dart';
import '../../../../core/network/result.dart';
import '../../data/models/booking_models.dart';
import '../../data/repositories/booking_repository.dart';

/// Reserve a stay.
///
/// A use case rather than a direct repository call because reserving has rules
/// that are neither HTTP nor UI, and that must hold no matter which screen
/// starts it:
///
/// * the **idempotency key belongs to the attempt**, not to the tap. It is
///   minted when the guest opens the form and reused for every retry, so a
///   double tap, a flaky connection and a "try again" button all resolve to one
///   booking rather than three held rooms;
/// * the **quoted total is sent** so the server can reject a stale price rather
///   than charge a different amount from the one shown;
/// * a price change and a sold-out stay are **distinguished**, because the
///   recoveries differ — one is "here is the new price", the other is "these
///   dates are gone".
class ReserveStay {
  const ReserveStay(this._repository);

  final BookingRepository _repository;

  Future<Result<BookingDto>> call(ReservationRequest request) =>
      _repository.create(
        propertyId: request.propertyId,
        roomTypeId: request.roomTypeId,
        checkIn: request.checkIn,
        checkOut: request.checkOut,
        adults: request.adults,
        children: request.children,
        infants: request.infants,
        rooms: request.rooms,
        guestName: request.guestName,
        guestEmail: request.guestEmail,
        guestPhone: request.guestPhone,
        quotedTotalMinor: request.quotedTotalMinor,
        idempotencyKey: request.idempotencyKey,
        specialRequests: request.specialRequests,
      );
}

class ReservationRequest {
  ReservationRequest({
    required this.propertyId,
    required this.roomTypeId,
    required this.checkIn,
    required this.checkOut,
    required this.adults,
    required this.children,
    required this.infants,
    required this.rooms,
    required this.guestName,
    required this.guestEmail,
    required this.guestPhone,
    required this.quotedTotalMinor,
    required this.idempotencyKey,
    this.specialRequests,
  });

  final String propertyId;
  final String roomTypeId;
  final String checkIn;
  final String checkOut;
  final int adults;
  final int children;
  final int infants;
  final int rooms;
  final String guestName;
  final String guestEmail;
  final String guestPhone;
  final int quotedTotalMinor;
  final String idempotencyKey;
  final String? specialRequests;

  /// Minted once per booking attempt. Uses the platform's secure RNG so two
  /// devices cannot collide.
  static String newIdempotencyKey() {
    final random = Random.secure();
    final bytes = List<int>.generate(16, (_) => random.nextInt(256));
    return bytes.map((b) => b.toRadixString(16).padLeft(2, '0')).join();
  }
}

/// How a failed reservation should be explained, and what to offer next.
enum ReservationProblem { priceChanged, soldOut, holdExpired, other }

ReservationProblem classifyReservationFailure(Failure failure) {
  if (failure.hasCode(ApiErrorCode.priceChanged)) {
    return ReservationProblem.priceChanged;
  }
  if (failure.hasCode(ApiErrorCode.datesUnavailable)) {
    return ReservationProblem.soldOut;
  }
  if (failure.hasCode(ApiErrorCode.holdExpired)) {
    return ReservationProblem.holdExpired;
  }
  return ReservationProblem.other;
}
