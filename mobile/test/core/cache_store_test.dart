/// The offline cache.
///
/// The behaviour worth pinning is not "does it store things" — it is the two
/// decisions that make the cache safe to show a guest:
///
/// * an expired entry is **still returned**, marked stale, because yesterday's
///   search beats a spinner that will never resolve on a train;
/// * a corrupt entry is **dropped, not thrown**, because a cache is never worth
///   an error screen.
///
/// Both are easy to "simplify" into their opposite — returning null on expiry,
/// or letting the decode throw — and neither would fail a test that only
/// checked round-tripping.
library;

import 'package:flutter_test/flutter_test.dart';
import 'package:roaming_wandering/core/storage/cache_store.dart';

import '../support/fakes.dart';

/// A trivially decodable payload — the point here is the envelope, not a DTO.
class Note {
  const Note(this.text);
  final String text;

  factory Note.fromJson(Map<String, dynamic> json) => Note(json['text'] as String);
  Map<String, dynamic> toJson() => {'text': text};
}

void main() {
  late CacheStore cache;
  late InMemoryBox box;

  setUp(() {
    final pair = inMemoryCache();
    cache = pair.cache;
    box = pair.box;
  });

  group('read and write', () {
    test('a missing key reads as null', () {
      expect(cache.read('absent', Note.fromJson), isNull);
    });

    test('round-trips a value', () async {
      await cache.write('k', const Note('hello').toJson());

      expect(cache.read('k', Note.fromJson)?.value.text, 'hello');
    });

    test('a fresh entry is marked fresh', () async {
      await cache.write('k', const Note('hello').toJson());

      expect(cache.read('k', Note.fromJson, freshFor: const Duration(minutes: 5))?.isFresh, isTrue);
    });

    test('an entry with no freshness window is always fresh', () async {
      // `freshFor: null` means the caller does not care — bookings, mostly,
      // where a record of something that already happened does not go stale.
      await cache.write('k', const Note('hello').toJson());
      box.age('k', const Duration(days: 30));

      expect(cache.read('k', Note.fromJson)?.isFresh, isTrue);
    });

    test('an expired entry is returned, marked stale', () async {
      // **The** cache rule. Returning null here would turn a train journey
      // into a blank screen; the screen can say "saved 2 hours ago" and still
      // show the address.
      await cache.write('k', const Note('hello').toJson());
      box.age('k', const Duration(hours: 2));

      final entry = cache.read('k', Note.fromJson, freshFor: const Duration(minutes: 5));

      expect(entry, isNotNull);
      expect(entry!.value.text, 'hello');
      expect(entry.isFresh, isFalse);
    });

    test('reports when the entry was stored', () async {
      // The screen renders this. "Saved earlier" without a time is not enough
      // for a guest deciding whether to trust a price.
      await cache.write('k', const Note('hello').toJson());
      box.age('k', const Duration(hours: 3));

      final storedAt = cache.read('k', Note.fromJson)!.storedAt;

      expect(DateTime.now().difference(storedAt).inMinutes, closeTo(180, 2));
    });

    test('freshness flips at the window, not somewhere near it', () async {
      // Both sides, a second either way. Only asserting the stale side would
      // still pass if the window collapsed to zero and every read came back
      // stale; only asserting the fresh side would pass if it were infinite.
      //
      // A second of slack rather than an exact-boundary assertion: the write
      // itself takes a moment, so `age` of exactly five minutes lands a
      // millisecond or two the wrong side and the test would flake.
      await cache.write('inside', const Note('a').toJson());
      box.age('inside', const Duration(minutes: 4, seconds: 59));
      await cache.write('outside', const Note('b').toJson());
      box.age('outside', const Duration(minutes: 5, seconds: 1));

      const window = Duration(minutes: 5);
      expect(cache.read('inside', Note.fromJson, freshFor: window)!.isFresh, isTrue);
      expect(cache.read('outside', Note.fromJson, freshFor: window)!.isFresh, isFalse);
    });
  });

  group('corruption', () {
    test('unparseable JSON reads as a miss, not a throw', () async {
      box.entries['k'] = 'not json at all';

      expect(cache.read('k', Note.fromJson), isNull);
    });

    test('a payload the model no longer accepts reads as a miss', () async {
      // The realistic case: last month's build wrote a shape this month's
      // `fromJson` cannot handle. A cache miss costs one request; a `TypeError`
      // costs a red screen on every launch until the app is reinstalled.
      await cache.write('k', {'headline': 'renamed field'});

      expect(cache.read('k', Note.fromJson), isNull);
    });

    test('a corrupt entry is evicted rather than re-read forever', () async {
      box.entries['k'] = '{';

      cache.read('k', Note.fromJson);

      expect(box.entries.containsKey('k'), isFalse);
    });
  });

  group('lists', () {
    test('round-trips a list', () async {
      await cache.writeList('ks', [const Note('a').toJson(), const Note('b').toJson()]);

      final entry = cache.readList('ks', Note.fromJson);

      expect(entry!.value.map((n) => n.text), ['a', 'b']);
    });

    test('an empty list is a hit, not a miss', () async {
      // "The search returned nothing" and "we have never run this search" are
      // different, and only the first should render an empty state offline.
      await cache.writeList('ks', []);

      final entry = cache.readList('ks', Note.fromJson);

      expect(entry, isNotNull);
      expect(entry!.value, isEmpty);
    });

    test('a list carries the same staleness as a single entry', () async {
      await cache.writeList('ks', [const Note('a').toJson()]);
      box.age('ks', const Duration(hours: 1));

      final entry = cache.readList('ks', Note.fromJson, freshFor: const Duration(minutes: 5));

      expect(entry!.isFresh, isFalse);
      expect(entry.value.single.text, 'a');
    });

    test('a corrupt list reads as a miss', () async {
      box.entries['ks'] = jsonGarbage;

      expect(cache.readList('ks', Note.fromJson), isNull);
    });
  });

  group('clearing', () {
    test('remove drops one key and leaves the rest', () async {
      await cache.write('a', const Note('a').toJson());
      await cache.write('b', const Note('b').toJson());

      await cache.remove('a');

      expect(cache.read('a', Note.fromJson), isNull);
      expect(cache.read('b', Note.fromJson), isNotNull);
    });

    test('clear empties everything', () async {
      // Called on sign-out. Another person picking up the phone must not find
      // the previous account's trips in a warm cache.
      await cache.write('a', const Note('a').toJson());
      await cache.writeList('bs', [const Note('b').toJson()]);

      await cache.clear();

      expect(box.entries, isEmpty);
    });
  });

  group('CacheKeys', () {
    test('namespaces per-entity keys so they cannot collide', () {
      // A property and a booking with the same id are different things. An
      // unprefixed key would serve one as the other, which decodes to a miss
      // at best and to a wrong screen at worst.
      expect(CacheKeys.property('abc'), isNot(CacheKeys.booking('abc')));
      expect(CacheKeys.property('abc'), contains('abc'));
    });

    test('distinct searches get distinct keys', () {
      expect(CacheKeys.search('goa|2'), isNot(CacheKeys.search('goa|3')));
    });
  });
}

const jsonGarbage = '{"at": "not-a-number", "data": {}}';
