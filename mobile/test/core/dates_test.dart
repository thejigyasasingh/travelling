import 'package:flutter_test/flutter_test.dart';
import 'package:roaming_wandering/core/utils/dates.dart';

/// Stay dates.
///
/// The half-open range is the rule the whole booking flow rests on: a 12th→14th
/// stay is two nights, and the 14th is free for the next guest. An off-by-one
/// here is either a wrong price or an overbooking.
void main() {
  group('nights', () {
    test('counts a half-open range', () {
      expect(nightsBetween('2026-09-12', '2026-09-14'), 2);
    });

    test('counts one night for consecutive days', () {
      expect(nightsBetween('2026-09-12', '2026-09-13'), 1);
    });

    test('crosses a month boundary', () {
      expect(nightsBetween('2026-09-29', '2026-10-02'), 3);
    });

    test('crosses a leap day', () {
      // 2028 is a leap year: 28 Feb → 1 Mar is two nights, not one.
      expect(nightsBetween('2028-02-28', '2028-03-01'), 2);
    });

    test('crosses a year boundary', () {
      expect(nightsBetween('2026-12-30', '2027-01-02'), 3);
    });
  });

  group('arithmetic', () {
    test('adds days across a month end', () {
      expect(addDays('2026-01-31', 1), '2026-02-01');
    });

    test('survives a DST-style shift', () {
      // Dates are constructed rather than advanced by a 24-hour Duration,
      // precisely so a local DST transition cannot silently drop a night.
      expect(addDays('2026-03-28', 1), '2026-03-29');
      expect(nightsBetween('2026-03-28', '2026-03-30'), 2);
    });
  });

  group('validation', () {
    test('rejects a checkout on or before check-in', () {
      expect(isValidStay('2026-09-12', '2026-09-12'), isFalse);
      expect(isValidStay('2026-09-12', '2026-09-11'), isFalse);
      expect(isValidStay('2026-09-12', '2026-09-13'), isTrue);
    });

    test('rejects missing or malformed dates without throwing', () {
      expect(isValidStay('2026-09-12', null), isFalse);
      expect(isValidStay(null, null), isFalse);
      expect(isValidStay('tomorrow', '2026-09-13'), isFalse);
      expect(isValidStay('', ''), isFalse);
    });
  });

  group('display', () {
    test('collapses a repeated month in a stay range', () {
      expect(formatStay('2026-09-12', '2026-09-14'), '12 – 14 Sep 2026');
    });

    test('keeps both months when they differ', () {
      expect(formatStay('2026-09-29', '2026-10-02'), '29 Sep – 2 Oct 2026');
    });

    test('pads the countdown seconds', () {
      expect(formatCountdown(605), '10:05');
      expect(formatCountdown(0), '0:00');
      expect(formatCountdown(-5), '0:00');
    });
  });
}
