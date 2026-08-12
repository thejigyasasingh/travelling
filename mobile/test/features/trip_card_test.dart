/// The card a guest sees for each of their trips.
///
/// This is the densest screen in the app — a list of everything a person has
/// booked — and the three things on it that can mislead someone are all here:
///
/// * **The status.** "Awaiting host" and "Confirmed" mean completely different
///   things about whether to book a flight.
/// * **The money.** Rendered from integer paise; a scaling slip shows ₹11,160
///   as ₹1,116,000 or as ₹111.
/// * **The Pay now button.** Offered for a booking that is not payable takes a
///   guest to a checkout the server will refuse.
///
/// Rendered through the real widget with a real theme rather than asserted on
/// a formatter, because every one of those failures is a rendering decision
/// rather than a formatting one.
library;

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:roaming_wandering/features/booking/data/models/booking_models.dart';
import 'package:roaming_wandering/features/booking/domain/entities/booking_status.dart';
import 'package:roaming_wandering/features/booking/presentation/screens/trips_screen.dart';

BookingDto booking({
  String status = 'confirmed',
  int totalMinor = 1_116_000,
  String propertyName = 'Sea Breeze Villa',
  int nights = 2,
}) {
  return BookingDto.fromJson({
    'id': '019feb81-2ac3-7413-841b-590fb56b7157',
    'reference': 'RW-26-ABCD1234',
    'status': status,
    'property_id': '11111111-1111-1111-1111-111111111111',
    'property_name': propertyName,
    'check_in': '2026-09-01',
    'check_out': '2026-09-0${1 + nights}',
    'nights': nights,
    'total_minor': totalMinor,
    'currency': 'INR',
  });
}

Future<void> pumpCard(WidgetTester tester, BookingDto dto) async {
  await tester.pumpWidget(
    MaterialApp(
      home: Scaffold(body: TripCard(booking: dto)),
    ),
  );
}

void main() {
  group('TripCard', () {
    testWidgets('names the property', (tester) async {
      await pumpCard(tester, booking(propertyName: 'Anjuna Beach House'));

      expect(find.text('Anjuna Beach House'), findsOneWidget);
    });

    testWidgets('shows the reference a guest quotes to support', (tester) async {
      await pumpCard(tester, booking());

      expect(find.text('RW-26-ABCD1234'), findsOneWidget);
    });

    testWidgets('renders paise as rupees', (tester) async {
      // ₹11,160 from 1,116,000 paise. A scaling slip here is the most visible
      // possible bug and the easiest to introduce.
      await pumpCard(tester, booking(totalMinor: 1_116_000));

      expect(find.textContaining('11,160'), findsOneWidget);
    });

    testWidgets('counts nights, not days', (tester) async {
      await pumpCard(tester, booking(nights: 2));

      expect(find.textContaining('2 nights'), findsOneWidget);
    });

    testWidgets('says "1 night" rather than "1 nights"', (tester) async {
      await pumpCard(tester, booking(nights: 1));

      expect(find.textContaining('1 night'), findsOneWidget);
      expect(find.textContaining('1 nights'), findsNothing);
    });
  });

  group('the Pay now button', () {
    testWidgets('is offered for a booking awaiting payment', (tester) async {
      await pumpCard(tester, booking(status: 'pending_payment'));

      expect(find.text('Pay now'), findsOneWidget);
    });

    testWidgets('is not offered for a confirmed booking', (tester) async {
      /// **The** button rule.
      ///
      /// Offering it takes the guest to a checkout the server refuses, on a
      /// booking they have already paid for — which reads as a demand for a
      /// second payment.
      await pumpCard(tester, booking(status: 'confirmed'));

      expect(find.text('Pay now'), findsNothing);
    });

    testWidgets('is not offered for anything already finished', (tester) async {
      for (final status in ['completed', 'cancelled', 'expired', 'rejected', 'no_show']) {
        await pumpCard(tester, booking(status: status));

        expect(find.text('Pay now'), findsNothing, reason: status);
      }
    });

    testWidgets('is offered exactly where the domain says it should be', (tester) async {
      // The card must not re-derive this. `isPayable` is the single answer,
      // and a card with its own opinion is one that drifts from the server's.
      for (final status in BookingStatus.values) {
        await pumpCard(tester, booking(status: status.wire));

        expect(
          find.text('Pay now'),
          status.isPayable ? findsOneWidget : findsNothing,
          reason: status.name,
        );
      }
    });
  });

  group('StatusChip', () {
    Future<void> pumpChip(WidgetTester tester, BookingStatus status) async {
      await tester.pumpWidget(
        MaterialApp(home: Scaffold(body: StatusChip(status: status))),
      );
    }

    testWidgets('shows the guest-facing label, not the wire value', (tester) async {
      // The API says `pending_approval`. A person reads "Awaiting host".
      await pumpChip(tester, BookingStatus.pendingApproval);

      expect(find.text('Awaiting host'), findsOneWidget);
      expect(find.textContaining('pending_approval'), findsNothing);
    });

    testWidgets('never says "rejected" to the guest', (tester) async {
      // "Declined" carries the same fact without the judgement.
      await pumpChip(tester, BookingStatus.rejected);

      expect(find.text('Declined'), findsOneWidget);
    });

    testWidgets('renders every status without failing', (tester) async {
      // A `switch` gaining a case and missing a colour is a crash on a list
      // that is otherwise fine — and only for the guest who has that status.
      for (final status in BookingStatus.values) {
        await pumpChip(tester, status);

        expect(find.text(status.label), findsOneWidget, reason: status.name);
      }
    });

    testWidgets('distinguishes a confirmed booking from a cancelled one', (tester) async {
      // At a glance, in a list, without reading. Asserted on the resolved
      // colour rather than a golden, so an unrelated theme change does not
      // fail it.
      await pumpChip(tester, BookingStatus.confirmed);
      final confirmed = tester.widget<Container>(find.byType(Container).first);

      await pumpChip(tester, BookingStatus.cancelled);
      final cancelled = tester.widget<Container>(find.byType(Container).first);

      expect(
        (confirmed.decoration! as BoxDecoration).color,
        isNot((cancelled.decoration! as BoxDecoration).color),
      );
    });
  });
}
