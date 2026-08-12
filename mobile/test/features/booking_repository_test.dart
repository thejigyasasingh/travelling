/// Bookings, payments, and the offline policy that inverts the catalogue's.
///
/// A stale search result is a wrong price. A stale *booking* is a guest at a
/// reception desk with no signal who still needs their reference number — so
/// bookings are cached generously and served offline without apology. The data
/// is a record of something that already happened.
///
/// The other half of this file is the idempotency key. A double-tapped
/// "Reserve" is two rooms held on real inventory and one of them abandoned;
/// the key is the only thing that makes the second attempt return the first
/// booking rather than create a second one.
library;

import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:roaming_wandering/core/error/failure.dart';
import 'package:roaming_wandering/core/network/result.dart';
import 'package:roaming_wandering/core/storage/cache_store.dart';
import 'package:roaming_wandering/features/booking/data/repositories/booking_repository.dart';
import 'package:roaming_wandering/features/booking/domain/usecases/reserve_stay.dart';

import '../support/fakes.dart';

Map<String, dynamic> _booking({String id = 'b1', String status = 'confirmed'}) => {
      'id': id,
      'reference': 'RW-26-ABCD1234',
      'status': status,
      'property_id': 'p1',
      'property_name': 'Sea Breeze',
      'check_in': '2026-09-01',
      'check_out': '2026-09-03',
      'total_minor': 900000,
      'currency': 'INR',
    };

({BookingRepository repo, StubAdapter adapter, CacheStore cache, InMemoryBox box})
    build(Future<ResponseBody> Function(RequestOptions options) handler) {
  final http = stubbedDio(handler);
  final storage = inMemoryCache();
  return (
    repo: BookingRepository(dio: http.dio, cache: storage.cache),
    adapter: http.adapter,
    cache: storage.cache,
    box: storage.box,
  );
}

({BookingRepository repo, CacheStore cache, InMemoryBox box}) buildOffline() {
  final storage = inMemoryCache();
  return (
    repo: BookingRepository(dio: offlineDio().dio, cache: storage.cache),
    cache: storage.cache,
    box: storage.box,
  );
}

Future<Result<dynamic>> _reserve(BookingRepository repo, {required String key}) => repo.create(
      propertyId: 'p1',
      roomTypeId: 'r1',
      checkIn: '2026-09-01',
      checkOut: '2026-09-03',
      adults: 2,
      children: 0,
      infants: 0,
      rooms: 1,
      guestName: 'A Guest',
      guestEmail: 'guest@example.test',
      guestPhone: '+919876543210',
      quotedTotalMinor: 900000,
      idempotencyKey: key,
    );

void main() {
  group('create', () {
    test('sends the idempotency key as a header', () async {
      // **The** double-booking guard. Without this header a retry — a double
      // tap, a flaky connection, a "try again" button — holds a second set of
      // rooms on real inventory.
      final t = build((_) async => jsonResponse(_booking()));

      await _reserve(t.repo, key: 'key-abc');

      expect(t.adapter.requests.single.headers['Idempotency-Key'], 'key-abc');
    });

    test('sends the quoted total so a stale price is refused, not charged', () async {
      // The server compares this to its own calculation and answers 409 if
      // they differ. Omitting it would let the guest be charged an amount they
      // were never shown.
      final t = build((_) async => jsonResponse(_booking()));

      await _reserve(t.repo, key: 'k');

      final body = t.adapter.requests.single.data as Map<String, dynamic>;
      expect(body['quoted_total_minor'], 900000);
    });

    test('caches the booking it just created', () async {
      // The confirmation screen is the one a guest screenshots and then opens
      // again in a lift with no signal.
      final t = build((_) async => jsonResponse(_booking()));

      await _reserve(t.repo, key: 'k');

      expect(t.box.entries.keys, contains(CacheKeys.booking('b1')));
    });

    test('distinguishes a sold-out stay from a price change', () async {
      // Different recoveries: one is "here is the new price", the other is
      // "these dates are gone". A shared error message strands the guest.
      final soldOut = build(
        (_) async => jsonResponse({
          'error': {'code': 'BOOKING_DATES_UNAVAILABLE', 'message': 'Gone'},
        }, status: 409),
      );
      final priceChanged = build(
        (_) async => jsonResponse({
          'error': {'code': 'PRICE_CHANGED', 'message': 'Up'},
        }, status: 409),
      );

      final a = (await _reserve(soldOut.repo, key: 'k')).failureOrNull!;
      final b = (await _reserve(priceChanged.repo, key: 'k')).failureOrNull!;

      expect(classifyReservationFailure(a), ReservationProblem.soldOut);
      expect(classifyReservationFailure(b), ReservationProblem.priceChanged);
    });

    test('an unrecognised refusal is classified as other, not mislabelled', () async {
      final t = build(
        (_) async => jsonResponse({
          'error': {'code': 'SOMETHING_NEW', 'message': 'No'},
        }, status: 409),
      );

      final failure = (await _reserve(t.repo, key: 'k')).failureOrNull!;

      expect(classifyReservationFailure(failure), ReservationProblem.other);
    });

    test('does not cache anything when the reservation fails', () async {
      // A cached booking that does not exist server-side would show in Trips
      // and never resolve.
      final t = build(
        (_) async => jsonResponse({
          'error': {'code': 'BOOKING_DATES_UNAVAILABLE', 'message': 'Gone'},
        }, status: 409),
      );

      await _reserve(t.repo, key: 'k');

      expect(t.box.entries, isEmpty);
    });
  });

  group('idempotency keys', () {
    test('are unique per attempt', () {
      final keys = List.generate(500, (_) => ReservationRequest.newIdempotencyKey());

      expect(keys.toSet().length, 500);
    });

    test('are long enough that a collision is not a real risk', () {
      // 16 bytes, hex-encoded. A collision across two devices would return one
      // guest another guest's booking.
      expect(ReservationRequest.newIdempotencyKey(), hasLength(32));
    });

    test('are hex, with no missing leading zeros', () {
      // A `toRadixString` without the pad drops leading zeros and produces a
      // shorter key for some byte values — which is how a "random" key ends up
      // colliding far sooner than its length suggests.
      for (var i = 0; i < 200; i++) {
        expect(ReservationRequest.newIdempotencyKey(), matches(RegExp(r'^[0-9a-f]{32}$')));
      }
    });
  });

  group('list', () {
    test('returns the page and caches it', () async {
      final t = build(
        (_) async => jsonResponse({'items': [_booking()], 'next_cursor': null}),
      );

      final page = expectOk(await t.repo.list());

      expect(page.items.single.id, 'b1');
      expect(page.isStale, isFalse);
      expect(t.box.entries.keys, contains(CacheKeys.bookings));
    });

    test('does not cache a filtered list', () async {
      // **The** cache-key trap. A filtered page written under the unfiltered
      // key would later restore as "all your trips" while showing only the
      // cancelled ones.
      final t = build((_) async => jsonResponse({'items': [_booking()]}));

      await t.repo.list(status: 'cancelled');

      expect(t.box.entries, isEmpty);
    });

    test('does not cache a later page', () async {
      final t = build((_) async => jsonResponse({'items': [_booking()]}));

      await t.repo.list(cursor: 'c2');

      expect(t.box.entries, isEmpty);
    });

    test('serves cached trips offline, however old', () async {
      // No freshness window here, unlike search. A trip from last week is
      // still the guest's trip, and the reference number has not changed.
      final t = buildOffline();
      await t.cache.writeList(CacheKeys.bookings, [_booking()]);
      t.box.age(CacheKeys.bookings, const Duration(days: 90));

      final page = expectOk(await t.repo.list());

      expect(page.items.single.id, 'b1');
      expect(page.isStale, isTrue);
      expect(page.cachedAt, isNotNull);
    });

    test('does not serve the cache for a server error', () async {
      final t = build(
        (_) async => jsonResponse({'error': {'code': 'X', 'message': 'boom'}}, status: 500),
      );
      await t.cache.writeList(CacheKeys.bookings, [_booking()]);

      expect((await t.repo.list()).isOk, isFalse);
    });

    test('an offline list with an empty cache still reports offline', () async {
      // Not an empty Trips tab. A guest who has bookings must never be shown
      // "you have no trips" because the train went into a tunnel.
      final t = buildOffline();

      expect((await t.repo.list()).failureOrNull, isA<NetworkFailure>());
    });
  });

  group('get', () {
    test('caches under the id the server returned', () async {
      // Fetched by slug or by reference, cached by id — so the next lookup by
      // either finds it. Asserted because caching under the *request* value
      // would silently produce two entries, one of them permanently stale.
      final t = build((_) async => jsonResponse(_booking()));

      await t.repo.get('RW-26-ABCD1234');

      expect(t.box.entries.keys, contains(CacheKeys.booking('b1')));
    });

    test('serves a cached booking offline', () async {
      // The reception-desk case this whole policy exists for.
      final t = buildOffline();
      await t.cache.write(CacheKeys.booking('b1'), _booking());

      expect(expectOk(await t.repo.get('b1')).reference, 'RW-26-ABCD1234');
    });

    test('reports the failure when the booking was never cached', () async {
      final t = buildOffline();

      expect((await t.repo.get('b1')).isOk, isFalse);
    });
  });

  group('cancel', () {
    test('refreshes the cached copy with the new status', () async {
      // Otherwise the Trips tab shows "Confirmed" for a booking the guest just
      // cancelled, until the next successful list call.
      final t = build((_) async => jsonResponse(_booking(status: 'cancelled')));
      await t.cache.write(CacheKeys.booking('b1'), _booking());

      final cancelled = expectOk(await t.repo.cancel('b1', reason: 'plans changed'));

      expect(cancelled.status, 'cancelled');
      final cached = t.cache.read(CacheKeys.booking('b1'), (j) => j['status'] as String);
      expect(cached!.value, 'cancelled');
    });

    test('sends the reason', () async {
      final t = build((_) async => jsonResponse(_booking(status: 'cancelled')));

      await t.repo.cancel('b1', reason: 'plans changed');

      expect((t.adapter.requests.single.data as Map)['reason'], 'plans changed');
    });
  });

  group('refund preview', () {
    test('is never cached', () async {
      // The refundable amount depends on how long until check-in, so it is
      // time-sensitive by construction. A cached one quotes a refund the guest
      // will not receive.
      final t = build(
        (_) async => jsonResponse({
          'refundable_minor': 450000,
          'penalty_minor': 450000,
          'currency': 'INR',
        }),
      );

      await t.repo.refundPreview('b1');

      expect(t.box.entries, isEmpty);
    });
  });

  group('payments', () {
    test('creates an order for a booking', () async {
      final t = build(
        (_) async => jsonResponse({
          'payment_id': 'pay_pending_1',
          'gateway_order_id': 'order_1',
          'amount_minor': 900000,
          'currency': 'INR',
          'key_id': 'rzp_test_x',
        }),
      );

      expectOk(await t.repo.createOrder('b1'));

      expect((t.adapter.requests.single.data as Map)['booking_id'], 'b1');
    });

    test('sends the gateway fields under the names the server verifies', () async {
      // These three are hashed together to check the signature. A renamed key
      // reads as a forged payment and the booking never confirms — after the
      // guest has already been charged.
      final t = build((_) async => jsonResponse({'status': 'captured', 'booking_id': 'b1'}));

      await t.repo.verifyPayment(orderId: 'o1', paymentId: 'pay_1', signature: 'sig');

      final body = t.adapter.requests.single.data as Map<String, dynamic>;
      expect(body['razorpay_order_id'], 'o1');
      expect(body['razorpay_payment_id'], 'pay_1');
      expect(body['razorpay_signature'], 'sig');
    });

    test('a gateway refusal keeps its code', () async {
      final t = build(
        (_) async => jsonResponse({
          'error': {'code': 'PAYMENT_GATEWAY_ERROR', 'message': 'Declined'},
        }, status: 502),
      );

      final result = await t.repo.verifyPayment(orderId: 'o1', paymentId: 'p', signature: 's');

      expect(result.isOk, isFalse);
    });
  });
}
