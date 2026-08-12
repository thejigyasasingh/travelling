import 'package:flutter_test/flutter_test.dart';
import 'package:intl/date_symbol_data_local.dart';
import 'package:roaming_wandering/core/utils/money.dart';

/// Money formatting.
///
/// Every price in the app goes through this. A bug here is a wrong number in
/// front of a customer, which is the one class of client bug that costs real
/// money rather than goodwill.
void main() {
  setUpAll(() async => initializeDateFormatting('en_IN'));

  group('formatting', () {
    test('renders paise as rupees', () {
      expect(formatMinor(450000, 'INR'), '₹4,500.00');
    });

    test('groups in the Indian system, not thousands', () {
      // ₹12,34,567.00 — not ₹1,234,567.00. Getting this wrong makes every large
      // total look foreign to the audience it is shown to.
      expect(formatMinor(123456700, 'INR'), '₹12,34,567.00');
    });

    test('drops decimals in compact mode only when they are zero', () {
      expect(formatMinor(450000, 'INR', compact: true), '₹4,500');
      expect(formatMinor(450050, 'INR', compact: true), '₹4,500.50');
    });

    test('never rounds a half-rupee away', () {
      expect(formatMinor(1, 'INR'), '₹0.01');
      expect(formatMinor(99, 'INR'), '₹0.99');
    });

    test('renders an em dash for an unknown amount rather than zero', () {
      // "₹0" for "we do not know the price" is a lie a customer can act on.
      expect(formatMinor(null, 'INR'), '—');
      expect(formatMinor(0, 'INR'), '₹0.00');
    });

    test('keeps the unit attached to a nightly rate', () {
      expect(formatPerNight(450000, 'INR'), '₹4,500 / night');
    });

    test('handles a currency with no minor unit', () {
      // JPY has no subunit: 4500 is ¥4,500, not ¥45.00 — a 100× error.
      final formatted = formatMinor(4500, 'JPY');
      expect(formatted, contains('4,500'));
      expect(formatted, isNot(contains('.')));
    });

    test('is available as an extension on int', () {
      expect(450000.asMoney('INR', compact: true), '₹4,500');
    });
  });
}
