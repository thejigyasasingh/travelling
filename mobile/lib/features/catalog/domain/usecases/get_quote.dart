import '../../../../core/error/failure.dart';
import '../../../../core/network/result.dart';
import '../../../../core/utils/dates.dart';
import '../../data/models/property_models.dart';
import '../../data/repositories/catalog_repository.dart';
import 'quote_problem.dart';

/// Price a stay.
///
/// The price shown to a guest is **always** the server's. Nightly rates vary by
/// date, weekends and seasons have multipliers, and tax is slabbed —
/// reimplementing that here would produce a number that disagrees with the
/// server at booking time, which the API correctly rejects with a 409.
///
/// What this use case does own is refusing to ask a question the server cannot
/// answer: a zero-night stay, or one below the room's minimum, is caught here
/// so the guest sees a sentence instead of a validation error.
class GetQuote {
  const GetQuote(this._repository);

  final CatalogRepository _repository;

  Future<Result<QuoteDto>> call(QuoteRequest request) {
    final problem = request.validate();
    if (problem != null) return Future.value(Result.err(problem));

    return _repository.quote(
      propertyId: request.propertyId,
      roomTypeId: request.roomTypeId,
      checkIn: request.checkIn,
      checkOut: request.checkOut,
      adults: request.adults,
      children: request.children,
      infants: request.infants,
      rooms: request.rooms,
    );
  }
}

class QuoteRequest {
  const QuoteRequest({
    required this.propertyId,
    required this.roomTypeId,
    required this.checkIn,
    required this.checkOut,
    required this.adults,
    this.children = 0,
    this.infants = 0,
    this.rooms = 1,
    this.minNights = 1,
  });

  final String propertyId;
  final String roomTypeId;
  final IsoDate checkIn;
  final IsoDate checkOut;
  final int adults;
  final int children;
  final int infants;
  final int rooms;
  final int minNights;

  int get nights => nightsBetween(checkIn, checkOut);

  Failure? validate() {
    if (!isValidStay(checkIn, checkOut)) return QuoteProblem.invalidDates;
    if (nights < minNights) return QuoteProblem.belowMinimumStay;
    return null;
  }
}
