/// The hold countdown on the checkout screen.
///
/// This is the highest-stakes widget in the app. It tells a guest how long
/// their rooms are held while they pay, and every way it can be wrong costs
/// somebody something:
///
/// * **Running slow** — it says four minutes left when there are none, the
///   guest takes their time, and the rooms are released mid-payment.
/// * **Running fast** — it panics someone into abandoning a booking they had
///   plenty of time to finish.
/// * **Not stopping** — a negative countdown, or one that keeps ticking past
///   zero, is visibly broken on the screen where trust matters most.
///
/// The implementation avoids two specific traps and both are pinned here: it
/// counts from a *duration* rather than a server timestamp (a device with a
/// wrong clock would render nonsense), and it recomputes from a deadline each
/// tick rather than decrementing (a backgrounded app has its timers throttled,
/// and a subtract-one counter returns minutes behind reality).
library;

import 'package:clock/clock.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:roaming_wandering/features/booking/presentation/screens/checkout_screen.dart';

Future<void> pump(
  WidgetTester tester,
  int seconds, {
  VoidCallback? onExpire,
}) async {
  await tester.pumpWidget(
    MaterialApp(
      home: Scaffold(
        body: HoldCountdown(seconds: seconds, onExpire: onExpire),
      ),
    ),
  );
}

/// Runs a body with both clocks moving together.
///
/// `tester.pump(Duration)` advances Flutter's timers but not the calendar, so
/// a widget doing arithmetic on `now()` sees the same instant on every tick.
/// Overriding `clock` keeps the two in step, which is the only way the drift
/// behaviour below is observable at all.
Future<void> withMovingClock(
  WidgetTester tester,
  Future<void> Function(Future<void> Function(Duration)) body,
) async {
  var offset = Duration.zero;
  final start = DateTime.now();

  await withClock(Clock(() => start.add(offset)), () async {
    Future<void> advance(Duration by) async {
      offset += by;
      await tester.pump(by);
    }

    await body(advance);
  });
}

void main() {
  testWidgets('shows the time remaining in minutes and seconds', (tester) async {
    await pump(tester, 605);

    // 10:05 — not "605 seconds", and not "10 minutes". A guest deciding
    // whether to go and find their card needs the real number.
    expect(find.textContaining('10:05'), findsOneWidget);
  });

  testWidgets('says what the countdown is for', (tester) async {
    // A bare timer on a payment screen reads as a deadline to pay *or be
    // charged*. Naming what expires is the difference.
    await pump(tester, 600);

    expect(find.textContaining('held'), findsOneWidget);
  });

  testWidgets('counts down as time passes', (tester) async {
    await withMovingClock(tester, (advance) async {
      await pump(tester, 600);
      expect(find.textContaining('10:00'), findsOneWidget);

      await advance(const Duration(seconds: 1));

      expect(find.textContaining('9:59'), findsOneWidget);
    });
  });

  testWidgets('recomputes from the deadline rather than decrementing', (tester) async {
    /// **The** backgrounding bug.
    ///
    /// A widget test's clock jumps: `pump(Duration(minutes: 3))` fires the
    /// periodic timer once, not a hundred and eighty times — exactly like an
    /// app returning from the background with throttled timers. A counter that
    /// subtracted one per tick would read 9:59 here. One anchored to a
    /// deadline reads 7:00, which is the truth.
    await withMovingClock(tester, (advance) async {
      await pump(tester, 600);

      // One tick fires, three minutes of wall time pass. A decrementing
      // counter would show 9:59.
      await advance(const Duration(minutes: 3));

      expect(find.textContaining('7:00'), findsOneWidget);
      expect(find.textContaining('9:59'), findsNothing);
    });
  });

  testWidgets('stops at zero rather than going negative', (tester) async {
    await withMovingClock(tester, (advance) async {
      await pump(tester, 3);

      await advance(const Duration(seconds: 10));

      expect(find.textContaining('-'), findsNothing);
      expect(find.textContaining('expired'), findsOneWidget);
    });
  });

  testWidgets('says the rooms were released when the hold lapses', (tester) async {
    // "Expired" alone leaves a guest wondering whether they still have the
    // booking. They do not, and being told is what sends them back to search
    // rather than to support.
    await withMovingClock(tester, (advance) async {
      await pump(tester, 1);

      await advance(const Duration(seconds: 2));

      expect(find.textContaining('released'), findsOneWidget);
    });
  });

  testWidgets('tells the screen when the hold expires', (tester) async {
    // The callback is what swaps the payment button for a "start again"
    // notice. Without it the guest can still press Pay on rooms they no
    // longer hold, and the gateway takes the money before the server refuses.
    var expired = false;
    await withMovingClock(tester, (advance) async {
      await pump(tester, 1, onExpire: () => expired = true);

      await advance(const Duration(seconds: 2));
    });

    expect(expired, isTrue);
  });

  testWidgets('reports expiry once, not on every later tick', (tester) async {
    // The callback navigates. Firing it repeatedly pushes a route per second.
    var calls = 0;
    await withMovingClock(tester, (advance) async {
      await pump(tester, 1, onExpire: () => calls++);

      await advance(const Duration(seconds: 2));
      await advance(const Duration(seconds: 2));
      await advance(const Duration(seconds: 2));
    });

    expect(calls, 1);
  });

  testWidgets('changes colour when time is short', (tester) async {
    /// Urgency has to be visible without reading. Asserted through the
    /// container's own colour rather than a golden file: a golden would fail
    /// on any unrelated theme change and be regenerated without being read.
    await pump(tester, 600);
    final calm = tester.widget<Container>(
      find.ancestor(of: find.byIcon(Icons.timer_outlined), matching: find.byType(Container)).first,
    );

    await pump(tester, 60);
    final urgent = tester.widget<Container>(
      find.ancestor(of: find.byIcon(Icons.timer_outlined), matching: find.byType(Container)).first,
    );

    expect(
      (calm.decoration! as BoxDecoration).color,
      isNot((urgent.decoration! as BoxDecoration).color),
    );
  });

  testWidgets('a hold that is already expired renders as expired', (tester) async {
    // Reachable: the screen can be restored from the background after the
    // hold lapsed, and the first frame must not claim 0:00 of remaining time.
    await pump(tester, 0);

    expect(find.textContaining('expired'), findsOneWidget);
  });

  testWidgets('re-anchors when the server sends a new duration', (tester) async {
    // A refetched booking carries a fresh `expires_in`. Ignoring it would keep
    // counting from the original anchor and drift further every poll.
    await pump(tester, 60);
    expect(find.textContaining('1:00'), findsOneWidget);

    await pump(tester, 600);

    expect(find.textContaining('10:00'), findsOneWidget);
  });

  testWidgets('cancels its timer when removed', (tester) async {
    // A live `Timer.periodic` after dispose calls `setState` on a dead
    // element. The test framework fails on a pending timer, so this passes
    // only if `dispose` cancels it.
    await pump(tester, 600);

    await tester.pumpWidget(const MaterialApp(home: SizedBox()));
    await tester.pump(const Duration(seconds: 2));
  });
}
