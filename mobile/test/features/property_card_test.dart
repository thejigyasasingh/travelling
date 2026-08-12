import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:roaming_wandering/features/catalog/data/models/property_models.dart';
import 'package:roaming_wandering/features/catalog/presentation/widgets/property_card.dart';
import 'package:roaming_wandering/core/providers/app_providers.dart';
import 'package:roaming_wandering/core/storage/cache_store.dart';

/// The search card.
///
/// The price label and the sold-out overlay are the two things on this card
/// that can mislead a customer, so both are pinned.
class _EmptyCache implements CacheStore {
  @override
  CachedEntry<T>? read<T>(String key, T Function(Map<String, dynamic>) decode,
          {Duration? freshFor}) =>
      null;

  @override
  CachedEntry<List<T>>? readList<T>(
          String key, T Function(Map<String, dynamic>) decode,
          {Duration? freshFor}) =>
      null;

  @override
  Future<void> write(String key, Map<String, dynamic> json) async {}

  @override
  Future<void> writeList(String key, List<Map<String, dynamic>> items) async {}

  @override
  Future<void> remove(String key) async {}

  @override
  Future<void> clear() async {}
}

SearchItemDto item({
  bool isAvailable = true,
  int? fromPriceMinor = 1500000,
  int? totalPriceMinor,
}) =>
    SearchItemDto(
      id: 'p1',
      slug: 'sea-breeze-villa',
      name: 'Sea Breeze Villa',
      city: 'Anjuna',
      currency: 'INR',
      isAvailable: isAvailable,
      fromPriceMinor: fromPriceMinor,
      totalPriceMinor: totalPriceMinor,
      cancellationPolicy: 'moderate',
      maxOccupancy: 4,
    );

/// Rendered inside a ListView, which is how the card is actually used: it sizes
/// itself to its content and needs unbounded height for the 4:3 cover image.
Widget harness(Widget child) => ProviderScope(
      overrides: [cacheStoreProvider.overrideWithValue(_EmptyCache())],
      child: MaterialApp(
        home: Scaffold(body: ListView(children: [child])),
      ),
    );

void main() {
  testWidgets('a dateless search shows a nightly "from" price', (tester) async {
    await tester.pumpWidget(harness(PropertyCard(item: item())));

    expect(find.textContaining('from'), findsOneWidget);
    expect(find.textContaining('15,000'), findsOneWidget);
    expect(find.textContaining('/ night'), findsOneWidget);
  });

  testWidgets('a dated search shows the stay total, not a nightly rate',
      (tester) async {
    await tester.pumpWidget(
      harness(
        PropertyCard(item: item(totalPriceMinor: 3360000), nights: 2),
      ),
    );

    // Showing a nightly rate where a guest expects a total is the oldest dark
    // pattern in travel booking.
    expect(find.textContaining('33,600'), findsOneWidget);
    expect(find.textContaining('total · 2 nights'), findsOneWidget);
    expect(find.textContaining('/ night'), findsNothing);
  });

  testWidgets('does NOT claim sold out when the search had no dates',
      (tester) async {
    // The API cannot answer availability without dates, so it returns
    // `is_available: false`. Rendering the overlay then tells every browsing
    // guest the whole catalogue is unavailable — which it is not.
    await tester.pumpWidget(harness(PropertyCard(item: item(isAvailable: false))));

    expect(find.text('Sold out for these dates'), findsNothing);
  });

  testWidgets('claims sold out only when dates were searched', (tester) async {
    await tester.pumpWidget(
      harness(PropertyCard(item: item(isAvailable: false), nights: 2)),
    );

    expect(find.text('Sold out for these dates'), findsOneWidget);
  });

  testWidgets('renders "New" rather than zero stars for an unrated stay',
      (tester) async {
    await tester.pumpWidget(harness(PropertyCard(item: item())));

    // An empty five-star row reads as "rated 0/5", which is both wrong and
    // unfair to a new host.
    expect(find.text('New'), findsOneWidget);
  });

  testWidgets('says the price includes taxes', (tester) async {
    await tester.pumpWidget(harness(PropertyCard(item: item())));
    expect(find.text('Includes taxes and fees'), findsOneWidget);
  });
}
