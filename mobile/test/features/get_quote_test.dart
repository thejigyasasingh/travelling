/// Pricing a stay, and the questions the app refuses to ask.
///
/// The price shown to a guest is **always** the server's — nightly rates vary
/// by date, weekends and seasons have multipliers, and tax is slabbed.
/// Recomputing any of that here would produce a number that disagrees with the
/// server at booking time, which the API correctly answers with a 409.
///
/// What this use case does own is the two requests the server cannot usefully
/// answer: a zero-night stay and one below the room's minimum. Catching those
/// locally turns a validation error nobody wrote for a human into a sentence,
/// and saves a round trip.
///
/// So the assertions come in pairs: the request never reaches the network, and
/// the failure carries a message worth showing.
library;

import 'package:flutter_test/flutter_test.dart';
import 'package:roaming_wandering/core/error/failure.dart';
import 'package:roaming_wandering/core/network/result.dart';
import 'package:roaming_wandering/features/catalog/data/datasources/catalog_remote_datasource.dart';
import 'package:roaming_wandering/features/catalog/data/repositories/catalog_repository.dart';
import 'package:roaming_wandering/features/catalog/domain/usecases/get_quote.dart';

import '../support/fakes.dart';

({GetQuote quote, StubAdapter adapter}) build() {
  final http = stubbedDio(
    (_) async => jsonResponse({
      'room_type_id': 'r1',
      'total_minor': 900000,
      'currency': 'INR',
      'is_available': true,
    }),
  );
  return (
    quote: GetQuote(
      CatalogRepository(
        remote: CatalogRemoteDataSource(http.dio),
        cache: inMemoryCache().cache,
      ),
    ),
    adapter: http.adapter,
  );
}

QuoteRequest request({
  String checkIn = '2026-09-01',
  String checkOut = '2026-09-03',
  int minNights = 1,
}) =>
    QuoteRequest(
      propertyId: 'p1',
      roomTypeId: 'r1',
      checkIn: checkIn,
      checkOut: checkOut,
      adults: 2,
      minNights: minNights,
    );

void main() {
  group('nights', () {
    test('counts nights, not days', () {
      // Half-open: arriving on the 1st and leaving on the 3rd is two nights.
      // The off-by-one here is the difference between the guest's total and
      // the server's.
      expect(request().nights, 2);
    });

    test('a same-day request is zero nights', () {
      expect(request(checkIn: '2026-09-01', checkOut: '2026-09-01').nights, 0);
    });
  });

  group('what is refused locally', () {
    test('a zero-night stay never reaches the network', () async {
      final t = build();

      final result = await t.quote(request(checkIn: '2026-09-01', checkOut: '2026-09-01'));

      expect(result.isOk, isFalse);
      expect(t.adapter.requests, isEmpty);
    });

    test('a backwards stay never reaches the network', () async {
      final t = build();

      final result = await t.quote(request(checkIn: '2026-09-05', checkOut: '2026-09-01'));

      expect(result.failureOrNull!.hasCode('INVALID_DATES'), isTrue);
      expect(t.adapter.requests, isEmpty);
    });

    test('a stay below the room minimum is refused with its own code', () async {
      // Distinct from invalid dates because the recovery differs: one is "pick
      // a later date", the other is "stay longer or pick another room".
      final t = build();

      final result = await t.quote(request(checkOut: '2026-09-02', minNights: 3));

      expect(result.failureOrNull!.hasCode('BELOW_MINIMUM_STAY'), isTrue);
      expect(t.adapter.requests, isEmpty);
    });

    test('a local refusal is showable, not a stack trace', () async {
      // These are `Failure.api` values on purpose, so a screen renders
      // `failure.message` down one error path whether the problem came from
      // here or from the server.
      final t = build();

      final failure = (await t.quote(request(minNights: 5))).failureOrNull!;

      expect(failure.message, isNotEmpty);
      expect(failure.message, isNot(contains('Exception')));
    });
  });

  group('what is asked', () {
    test('a valid stay is priced by the server', () async {
      final t = build();

      final quote = expectOk(await t.quote(request()));

      expect(quote.totalMinor, 900000);
      expect(t.adapter.requests, hasLength(1));
    });

    test('a stay exactly at the minimum is allowed', () {
      // `nights < minNights`, not `<=`. The boundary is the whole point of a
      // two-night minimum.
      expect(request(minNights: 2).validate(), isNull);
    });

    test('the default minimum admits a single night', () {
      expect(request(checkOut: '2026-09-02').validate(), isNull);
    });

    test('the app does not compute a total of its own', () async {
      // Pinned deliberately. The temptation is to multiply nights by the
      // "from" price for an instant preview; that number disagrees with the
      // server on any weekend, and the guest sees it change at checkout.
      final t = build();

      final quote = expectOk(await t.quote(request()));

      expect(quote.totalMinor, 900000, reason: 'the total must be the server\'s, verbatim');
    });
  });
}
