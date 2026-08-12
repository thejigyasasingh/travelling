/// The catalogue's caching policy.
///
/// The repository is where "what happens on a bad connection" is decided, and
/// the policy deliberately differs per resource because the cost of staleness
/// does:
///
/// * **amenities** — cache-first, a day old is indistinguishable from fresh;
/// * **search** — network-first, cache only as a fallback, and only page one;
/// * **property** — same, but a longer window, because an address does not
///   change while a guest is in a lift;
/// * **quote** — never cached, because it is the number the guest agrees to pay.
///
/// Each of those is one `if` away from its opposite, and the wrong branch is
/// invisible in development where the network always works. Hence this file.
///
/// The HTTP stub sits at Dio's adapter seam, so the real interceptor chain,
/// query serialisation and error mapping all run.
library;

import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:roaming_wandering/core/error/failure.dart';
import 'package:roaming_wandering/core/network/result.dart';
import 'package:roaming_wandering/core/storage/cache_store.dart';
import 'package:roaming_wandering/features/catalog/data/datasources/catalog_remote_datasource.dart';
import 'package:roaming_wandering/features/catalog/data/repositories/catalog_repository.dart';
import 'package:roaming_wandering/features/catalog/domain/entities/search_criteria.dart';

import '../support/fakes.dart';

const _criteria = SearchCriteria(query: 'Anjuna');

Map<String, dynamic> _item(String id) => {
      'id': id,
      'slug': 'slug-$id',
      'name': 'Villa $id',
      'city': 'Anjuna',
      'from_price_minor': 450000,
      'currency': 'INR',
    };

Map<String, dynamic> _searchBody({String? cursor, List<String> ids = const ['a', 'b']}) => {
      'items': ids.map(_item).toList(),
      'next_cursor': cursor,
      'total_estimate': 42,
    };

Map<String, dynamic> _propertyBody() => {
      'id': 'p1',
      'slug': 'sea-breeze',
      'name': 'Sea Breeze',
      'city': 'Anjuna',
      'description': 'By the water.',
    };

/// Builds a repository over a stubbed network and an in-memory cache, handing
/// back every seam so a test can assert on requests *and* on what was stored.
({
  CatalogRepository repo,
  StubAdapter adapter,
  CacheStore cache,
  InMemoryBox box,
}) build(Future<ResponseBody> Function(RequestOptions options) handler) {
  final http = stubbedDio(handler);
  final storage = inMemoryCache();
  return (
    repo: CatalogRepository(
      remote: CatalogRemoteDataSource(http.dio),
      cache: storage.cache,
    ),
    adapter: http.adapter,
    cache: storage.cache,
    box: storage.box,
  );
}

/// The same, but every request fails the way a phone in a tunnel does.
({CatalogRepository repo, CacheStore cache, InMemoryBox box}) buildOffline() {
  final http = offlineDio();
  final storage = inMemoryCache();
  return (
    repo: CatalogRepository(
      remote: CatalogRemoteDataSource(http.dio),
      cache: storage.cache,
    ),
    cache: storage.cache,
    box: storage.box,
  );
}

void main() {
  group('search', () {
    test('returns the page the server sent', () async {
      final t = build((_) async => jsonResponse(_searchBody(cursor: 'c2')));

      final page = expectOk(await t.repo.search(_criteria));

      expect(page.items.map((i) => i.id), ['a', 'b']);
      expect(page.nextCursor, 'c2');
      expect(page.hasMore, isTrue);
      expect(page.isStale, isFalse);
    });

    test('a live page is never marked stale', () {
      // The banner is driven by this flag. Setting it on a live response would
      // tell every guest their prices are old.
      expect(const SearchPage(items: []).isStale, isFalse);
    });

    test('caches the first page', () async {
      final t = build((_) async => jsonResponse(_searchBody()));

      await t.repo.search(_criteria);

      expect(t.box.entries.keys, contains(CacheKeys.search(_criteria.cacheSignature)));
    });

    test('does not cache later pages', () async {
      // **The** paging rule. A cursor is meaningless without the query that
      // produced it, so a cached page two would restore as an arbitrary
      // fragment of a list — worse than nothing.
      final t = build((_) async => jsonResponse(_searchBody()));

      await t.repo.search(_criteria, cursor: 'c2');

      expect(t.box.entries, isEmpty);
    });

    test('two different searches do not share a cache entry', () async {
      final t = build((_) async => jsonResponse(_searchBody()));

      await t.repo.search(const SearchCriteria(query: 'Anjuna'));
      await t.repo.search(const SearchCriteria(query: 'Vagator'));

      expect(t.box.entries.length, 2);
    });

    test('falls back to the cache when the network is gone', () async {
      // The whole reason the cache exists: a blank screen on a train is the
      // failure this prevents.
      final storage = inMemoryCache();
      final online = CatalogRepository(
        remote: CatalogRemoteDataSource(stubbedDio((_) async => jsonResponse(_searchBody())).dio),
        cache: storage.cache,
      );
      await online.search(_criteria);

      final offline = CatalogRepository(
        remote: CatalogRemoteDataSource(offlineDio().dio),
        cache: storage.cache,
      );
      final page = expectOk(await offline.search(_criteria));

      expect(page.items.map((i) => i.id), ['a', 'b']);
    });

    test('a cached fallback says it is stale, and when it was saved', () async {
      // Silently showing saved prices as live is how a guest arrives at
      // checkout to a different number. The screen needs both flags to say so.
      final storage = inMemoryCache();
      await storage.cache.writeList(
        CacheKeys.search(_criteria.cacheSignature),
        [_item('a')],
      );
      final repo = CatalogRepository(
        remote: CatalogRemoteDataSource(offlineDio().dio),
        cache: storage.cache,
      );

      final page = expectOk(await repo.search(_criteria));

      expect(page.isStale, isTrue);
      expect(page.cachedAt, isNotNull);
    });

    test('does not fall back for a server refusal', () async {
      // **The** fallback rule. A 422 means the query itself is wrong; serving
      // a stale page for it hides a real bug behind plausible-looking data.
      final t = build(
        (_) async => jsonResponse({
          'error': {'code': 'VALIDATION_ERROR', 'message': 'bad dates'},
        }, status: 422),
      );
      await t.cache.writeList(CacheKeys.search(_criteria.cacheSignature), [_item('a')]);

      final result = await t.repo.search(_criteria);

      expect(result.isOk, isFalse);
      expect(result.failureOrNull!.hasCode(ApiErrorCode.validation), isTrue);
    });

    test('does not fall back for a later page even offline', () async {
      final t = buildOffline();
      await t.cache.writeList(CacheKeys.search(_criteria.cacheSignature), [_item('a')]);

      final result = await t.repo.search(_criteria, cursor: 'c2');

      expect(result.isOk, isFalse);
    });

    test('an offline search with nothing cached reports offline', () async {
      // Not an empty result. "No stays match" and "we could not look" lead the
      // guest to do completely different things.
      final t = buildOffline();

      final result = await t.repo.search(_criteria);

      expect(result.failureOrNull, isA<NetworkFailure>());
    });

    test('sends the cursor only when there is one', () async {
      // A literal `cursor=null` in the query string is a value the server
      // tries to decode, and rejects.
      final t = build((_) async => jsonResponse(_searchBody()));

      await t.repo.search(_criteria);
      expect(t.adapter.requests.single.uri.queryParameters, isNot(contains('cursor')));

      await t.repo.search(_criteria, cursor: 'c2');
      expect(t.adapter.requests.last.uri.queryParameters['cursor'], 'c2');
    });

    test('sends repeated keys for list filters, not a joined string', () async {
      // The API declares these as list params and parses
      // `?amenity=wifi&amenity=pool`. A comma-joined value silently matches
      // nothing.
      final t = build((_) async => jsonResponse(_searchBody()));

      await t.repo.search(const SearchCriteria(amenities: ['wifi', 'pool']));

      expect(t.adapter.requests.single.uri.queryParametersAll['amenity'], ['wifi', 'pool']);
    });
  });

  group('property', () {
    test('returns and caches the listing', () async {
      final t = build((_) async => jsonResponse(_propertyBody()));

      final property = expectOk(await t.repo.property('sea-breeze'));

      expect(property.name, 'Sea Breeze');
      expect(t.box.entries.keys, contains(CacheKeys.property('sea-breeze')));
    });

    test('serves the cached listing when offline', () async {
      // A guest already on the way keeps the address and the check-in time.
      final storage = inMemoryCache();
      await storage.cache.write(CacheKeys.property('sea-breeze'), _propertyBody());
      final repo = CatalogRepository(
        remote: CatalogRemoteDataSource(offlineDio().dio),
        cache: storage.cache,
      );

      expect(expectOk(await repo.property('sea-breeze')).name, 'Sea Breeze');
    });

    test('does not serve a cached listing for a 404', () async {
      // The listing was taken down. Showing it from cache sends the guest to a
      // booking flow that cannot complete.
      final t = build(
        (_) async => jsonResponse({
          'error': {'code': 'NOT_FOUND', 'message': 'gone'},
        }, status: 404),
      );
      await t.cache.write(CacheKeys.property('sea-breeze'), _propertyBody());

      expect((await t.repo.property('sea-breeze')).isOk, isFalse);
    });

    test('a stale cached listing is not served past its window', () async {
      // An hour, not a day: check-in times and house rules do change, and the
      // consequence of showing an old one is a guest at a locked door.
      final storage = inMemoryCache();
      await storage.cache.write(CacheKeys.property('sea-breeze'), _propertyBody());
      storage.box.age(CacheKeys.property('sea-breeze'), const Duration(hours: 6));
      final repo = CatalogRepository(
        remote: CatalogRemoteDataSource(offlineDio().dio),
        cache: storage.cache,
      );

      expect((await repo.property('sea-breeze')).isOk, isFalse);
    });
  });

  group('amenities', () {
    List<Map<String, dynamic>> body() => [
          {'code': 'wifi', 'label': 'Wi-Fi', 'category': 'basics'},
        ];

    test('fetches and caches on a cold start', () async {
      final t = build((_) async => jsonResponse(body()));

      expect(expectOk(await t.repo.amenities()).single.code, 'wifi');
      expect(t.box.entries.keys, contains(CacheKeys.amenities));
    });

    test('serves a warm cache without touching the network', () async {
      // Cache-first, unlike everything else here: the filter sheet must open
      // without a spinner, and a day-old amenity list is indistinguishable
      // from a fresh one.
      final t = build((_) async => jsonResponse(body()));
      await t.repo.amenities();

      await t.repo.amenities();

      expect(t.adapter.requests.length, 1);
    });

    test('refetches once the cache goes cold', () async {
      final t = build((_) async => jsonResponse(body()));
      await t.repo.amenities();
      t.box.age(CacheKeys.amenities, const Duration(days: 2));

      await t.repo.amenities();

      expect(t.adapter.requests.length, 2);
    });

    test('serves an expired cache rather than failing', () async {
      // A reference list from last week still opens a working filter sheet.
      // An error here would break filtering entirely on a bad connection.
      final t = buildOffline();
      await t.cache.writeList(CacheKeys.amenities, body());
      t.box.age(CacheKeys.amenities, const Duration(days: 30));

      expect(expectOk(await t.repo.amenities()).single.code, 'wifi');
    });

    test('reports the failure when there is nothing cached at all', () async {
      final t = buildOffline();

      expect((await t.repo.amenities()).isOk, isFalse);
    });
  });

  group('quote', () {
    test('is never cached', () async {
      // **The** money rule. A quote is the number the guest agrees to pay, and
      // the server re-checks it at booking time — a stale one produces a 409
      // at the worst possible moment.
      final t = build(
        (_) async => jsonResponse({
          'room_type_id': 'r1',
          'total_minor': 900000,
          'currency': 'INR',
          'is_available': true,
        }),
      );

      await t.repo.quote(
        propertyId: 'p1',
        roomTypeId: 'r1',
        checkIn: '2026-09-01',
        checkOut: '2026-09-03',
        adults: 2,
      );

      expect(t.box.entries, isEmpty);
      expect(t.box.writes, 0);
    });

    test('posts the stay as the server expects it', () async {
      final t = build(
        (_) async => jsonResponse({'total_minor': 1, 'currency': 'INR'}),
      );

      await t.repo.quote(
        propertyId: 'p1',
        roomTypeId: 'r1',
        checkIn: '2026-09-01',
        checkOut: '2026-09-03',
        adults: 2,
        children: 1,
      );

      final body = t.adapter.requests.single.data as Map<String, dynamic>;
      expect(body['room_type_id'], 'r1');
      expect(body['check_in'], '2026-09-01');
      // Half-open: check-out is the morning after the last night.
      expect(body['check_out'], '2026-09-03');
      expect(body['children'], 1);
    });

    test('surfaces a price change as its own code', () async {
      // The checkout screen branches on this to show "the price has changed"
      // rather than a generic failure with no way forward.
      final t = build(
        (_) async => jsonResponse({
          'error': {'code': 'PRICE_CHANGED', 'message': 'The price has changed.'},
        }, status: 409),
      );

      final result = await t.repo.quote(
        propertyId: 'p1',
        roomTypeId: 'r1',
        checkIn: '2026-09-01',
        checkOut: '2026-09-03',
        adults: 2,
      );

      expect(result.failureOrNull!.hasCode(ApiErrorCode.priceChanged), isTrue);
    });
  });
}
