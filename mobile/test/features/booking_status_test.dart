/// The booking status machine, as a guest experiences it.
///
/// Every one of these booleans gates a button. `isPayable` shows "Pay now";
/// `canRequestCancellation` shows "Cancel booking". Getting one wrong does not
/// crash anything — it offers a guest an action the server will refuse, or
/// hides one they are entitled to, and both arrive as support tickets rather
/// than as errors.
///
/// The unknown-status case matters most of all: it is what an old app does
/// against a newer server, which is the normal state of a mobile fleet.
library;

import 'package:flutter_test/flutter_test.dart';
import 'package:roaming_wandering/features/booking/domain/entities/booking_status.dart';

void main() {
  group('parsing', () {
    test('round-trips every wire value', () {
      // Guards against a typo in a single `wire` string, which would silently
      // route one status to the fallback below and mislabel it forever.
      for (final status in BookingStatus.values) {
        expect(BookingStatus.parse(status.wire), status, reason: status.name);
      }
    });

    test('wire values are the snake_case the API sends', () {
      // Spelled out rather than derived. Deriving them from `name` would make
      // a rename of the Dart enum silently change the wire contract.
      expect(BookingStatus.pendingPayment.wire, 'pending_payment');
      expect(BookingStatus.pendingApproval.wire, 'pending_approval');
      expect(BookingStatus.inStay.wire, 'in_stay');
      expect(BookingStatus.noShow.wire, 'no_show');
    });

    test('an unknown status does not crash an older app', () {
      // **The** compatibility rule. The server will grow statuses this build
      // has never heard of. `firstWhere` without an `orElse` throws, and the
      // trip list would fail to render entirely.
      expect(BookingStatus.parse('teleported'), BookingStatus.completed);
    });

    test('the unknown fallback offers no actions', () {
      // Why `completed` and not, say, `confirmed`: it is the safest read-only
      // reading. An unknown status rendered as confirmed would offer a Cancel
      // button for a booking in a state this build cannot reason about.
      final unknown = BookingStatus.parse('something_new');

      expect(unknown.isPayable, isFalse);
      expect(unknown.canRequestCancellation, isFalse);
      expect(unknown.isActive, isFalse);
    });

    test('an empty string is treated as unknown rather than throwing', () {
      expect(BookingStatus.parse(''), BookingStatus.completed);
    });
  });

  group('what the guest is told', () {
    test('every status has a label and a hint', () {
      for (final status in BookingStatus.values) {
        expect(status.label, isNotEmpty, reason: status.name);
        expect(status.hint, isNotEmpty, reason: status.name);
      }
    });

    test('no two statuses share a label', () {
      // Two rows reading "Cancelled" for genuinely different outcomes — the
      // guest cancelled, versus the host declined — is a support call.
      final labels = BookingStatus.values.map((s) => s.label).toSet();

      expect(labels.length, BookingStatus.values.length);
    });

    test('a rejected booking is not called "rejected" to the guest', () {
      // Wire vocabulary is not guest vocabulary. "Declined" is what a person
      // reads without feeling judged.
      expect(BookingStatus.rejected.label, 'Declined');
    });

    test('the pending-approval hint promises no charge', () {
      // The single most common question about a request-to-book. Saying it on
      // the screen removes the ticket.
      expect(BookingStatus.pendingApproval.hint, contains('not be charged'));
    });

    test('the expired hint explains the rooms were released', () {
      // Otherwise "Expired" reads as an app problem rather than a lapsed hold.
      expect(BookingStatus.expired.hint.toLowerCase(), contains('released'));
    });
  });

  group('what the guest can do', () {
    test('only a pending payment is payable', () {
      // The checkout route is gated on this. Any other status reaching it
      // means charging for a booking that is already paid, gone, or refused.
      final payable = BookingStatus.values.where((s) => s.isPayable).toSet();

      expect(payable, {BookingStatus.pendingPayment});
    });

    test('upcoming means confirmed or awaiting the host', () {
      final upcoming = BookingStatus.values.where((s) => s.isUpcoming).toSet();

      expect(upcoming, {BookingStatus.confirmed, BookingStatus.pendingApproval});
    });

    test('active covers everything still in play', () {
      // What the "Trips" tab shows above the fold. A stay in progress belongs
      // there; a completed one does not.
      final active = BookingStatus.values.where((s) => s.isActive).toSet();

      expect(active, {
        BookingStatus.pendingPayment,
        BookingStatus.pendingApproval,
        BookingStatus.confirmed,
        BookingStatus.inStay,
      });
    });

    test('a finished or dead booking is never active', () {
      for (final status in [
        BookingStatus.completed,
        BookingStatus.cancelled,
        BookingStatus.expired,
        BookingStatus.rejected,
        BookingStatus.noShow,
      ]) {
        expect(status.isActive, isFalse, reason: status.name);
      }
    });

    test('cancellation is offered only where it can succeed', () {
      // **The** button rule. Offering Cancel on a completed stay produces a
      // server refusal the guest reads as a broken app; hiding it on a
      // confirmed one sends them to support for something self-service.
      final cancellable =
          BookingStatus.values.where((s) => s.canRequestCancellation).toSet();

      expect(cancellable, {
        BookingStatus.confirmed,
        BookingStatus.pendingApproval,
        BookingStatus.pendingPayment,
      });
    });

    test('an in-stay booking is active but not cancellable', () {
      // The guest is standing in the room. Cancellation is a conversation with
      // the property, not a button.
      expect(BookingStatus.inStay.isActive, isTrue);
      expect(BookingStatus.inStay.canRequestCancellation, isFalse);
    });

    test('anything cancellable is also active', () {
      // An invariant rather than a case: a booking cannot be dead enough to
      // leave the Trips tab yet alive enough to cancel.
      for (final status in BookingStatus.values.where((s) => s.canRequestCancellation)) {
        expect(status.isActive, isTrue, reason: status.name);
      }
    });
  });
}
