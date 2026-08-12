import 'package:intl/intl.dart';

/// Money, in integer minor units.
///
/// The API speaks paise and so does this app, end to end. A `double` for money
/// is a rounding bug waiting for the first ₹0.005 — and on a booking screen
/// that bug is a total that disagrees with the invoice. The only place a
/// decimal appears is the string a person reads.
extension MoneyFormatting on int {
  /// `450000` → `₹4,500.00`, grouped the Indian way (`₹12,34,567.00`).
  String asMoney(String currency, {bool compact = false, String locale = 'en_IN'}) =>
      formatMinor(this, currency, compact: compact, locale: locale);
}

const _zeroDecimalCurrencies = {'JPY', 'KRW', 'VND', 'CLP', 'ISK'};

final _formatterCache = <String, NumberFormat>{};

int _exponentFor(String currency) =>
    _zeroDecimalCurrencies.contains(currency) ? 0 : 2;

NumberFormat _formatter(String currency, String locale, int decimals) {
  final key = '$locale:$currency:$decimals';
  // NumberFormat construction is genuinely expensive and a search list renders
  // one price per card, on every frame of a scroll.
  return _formatterCache[key] ??= NumberFormat.currency(
    locale: locale,
    name: currency,
    symbol: _symbolFor(currency),
    decimalDigits: decimals,
  );
}

String _symbolFor(String currency) => switch (currency) {
      'INR' => '₹',
      'USD' => r'$',
      'EUR' => '€',
      'GBP' => '£',
      _ => '$currency ',
    };

/// Format an amount in minor units.
///
/// [compact] drops `.00` — right for a price in a list, wrong for an invoice
/// line, so it is never the default.
String formatMinor(
  int? amountMinor,
  String currency, {
  bool compact = false,
  String locale = 'en_IN',
}) {
  // An em dash for "we do not know", never ₹0. Showing zero for an unknown
  // price is a number a customer can act on, and it is wrong.
  if (amountMinor == null) return '—';

  final exponent = _exponentFor(currency);
  final divisor = exponent == 0 ? 1 : 100;
  final hideDecimals = compact && amountMinor % divisor == 0;
  return _formatter(currency, locale, hideDecimals ? 0 : exponent)
      .format(amountMinor / divisor);
}

/// `₹4,500 / night` — the unit is part of the price, and omitting it is a lie.
String formatPerNight(int amountMinor, String currency) =>
    '${formatMinor(amountMinor, currency, compact: true)} / night';
