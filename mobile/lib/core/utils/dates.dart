/// Stay dates.
///
/// A stay is a **half-open** range: `[checkIn, checkOut)`. The guest sleeps on
/// the check-in night and leaves on the check-out morning, so 12th → 14th is
/// two nights and the 14th is free for the next guest. Getting this wrong is
/// either a wrong price or an overbooking, and it is the most common bug in
/// booking software.
///
/// Dates here are calendar dates, not instants. A stay starting "12 September"
/// starts on the 12th in Goa regardless of where the phone thinks it is — so
/// these travel as `yyyy-MM-dd` strings, the same thing the API speaks, and are
/// never `DateTime`s silently shifted by a timezone.
library;

import 'package:intl/intl.dart';

final _isoFormat = DateFormat('yyyy-MM-dd');
final _dayMonth = DateFormat('d MMM');
final _dayMonthYear = DateFormat('d MMM yyyy');
final _dateTime = DateFormat('d MMM yyyy, h:mm a');

/// A calendar date as `yyyy-MM-dd`.
typedef IsoDate = String;

IsoDate toIso(DateTime date) => _isoFormat.format(date);

/// Today in the *device's* timezone. At 01:00 IST the UTC date is still
/// yesterday, and yesterday is not a bookable check-in.
IsoDate today() => toIso(DateTime.now());

DateTime parseIso(IsoDate date) => DateTime.parse(date);

IsoDate addDays(IsoDate date, int days) {
  final parsed = parseIso(date);
  // Constructed rather than `add(Duration(days:))`: a DST transition makes a
  // 24-hour duration land on the same calendar day, silently dropping a night.
  return toIso(DateTime(parsed.year, parsed.month, parsed.day + days));
}

/// Nights between two dates. Half-open, so 12th → 14th is 2.
int nightsBetween(IsoDate checkIn, IsoDate checkOut) {
  final from = parseIso(checkIn);
  final to = parseIso(checkOut);
  // Both anchored to UTC midnight so the subtraction cannot be skewed by a
  // clock change between the two dates.
  return DateTime.utc(to.year, to.month, to.day)
      .difference(DateTime.utc(from.year, from.month, from.day))
      .inDays;
}

bool isValidStay(IsoDate? checkIn, IsoDate? checkOut) {
  if (checkIn == null || checkOut == null) return false;
  if (checkIn.isEmpty || checkOut.isEmpty) return false;
  try {
    return nightsBetween(checkIn, checkOut) > 0;
  } on FormatException {
    return false;
  }
}

String formatDate(IsoDate date) => _dayMonthYear.format(parseIso(date));

/// `12 – 14 Sep 2026`, collapsing the repeated month and year.
String formatStay(IsoDate checkIn, IsoDate checkOut) {
  final from = parseIso(checkIn);
  final to = parseIso(checkOut);
  final sameMonth = from.year == to.year && from.month == to.month;
  final left = sameMonth ? '${from.day}' : _dayMonth.format(from);
  return '$left – ${_dayMonthYear.format(to)}';
}

String formatDateTime(String? iso) {
  if (iso == null) return '—';
  final parsed = DateTime.tryParse(iso);
  return parsed == null ? '—' : _dateTime.format(parsed.toLocal());
}

/// `in 3 days` / `2 hours ago`, for holds and trip countdowns.
String formatRelative(String? iso) {
  if (iso == null) return '—';
  final target = DateTime.tryParse(iso);
  if (target == null) return '—';

  final delta = target.difference(DateTime.now());
  final seconds = delta.inSeconds;
  final future = seconds > 0;
  final abs = seconds.abs();

  String phrase(int value, String unit) {
    final plural = value == 1 ? unit : '${unit}s';
    return future ? 'in $value $plural' : '$value $plural ago';
  }

  if (abs >= 86400) return phrase(abs ~/ 86400, 'day');
  if (abs >= 3600) return phrase(abs ~/ 3600, 'hour');
  if (abs >= 60) return phrase(abs ~/ 60, 'minute');
  return future ? 'in a moment' : 'just now';
}

/// `mm:ss`, for the checkout hold countdown.
String formatCountdown(int secondsLeft) {
  final safe = secondsLeft < 0 ? 0 : secondsLeft;
  final minutes = safe ~/ 60;
  final seconds = safe % 60;
  return '$minutes:${seconds.toString().padLeft(2, '0')}';
}
