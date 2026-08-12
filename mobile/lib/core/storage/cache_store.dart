import 'dart:convert';

import 'package:hive_ce_flutter/hive_flutter.dart';

/// The offline cache.
///
/// Two properties make it useful rather than decorative:
///
/// **Entries carry their own age.** A cached search from four days ago is not
/// worth showing as if it were live, but a cached *booking* from four days ago
/// absolutely is — a guest standing at a reception desk with no signal needs
/// their reference number. So the TTL is chosen per read, by the repository
/// that knows what the data is for, rather than fixed here.
///
/// **Stale data is returned knowingly, never silently.** [read] reports whether
/// what it returned is fresh, so a screen can show the content *and* say it was
/// saved earlier. Silently showing stale prices is how a guest arrives at
/// checkout to a different number.
///
/// JSON rather than typed Hive adapters: the models are already
/// `json_serializable`, and a schema change then costs a cache miss instead of
/// a migration or a crash on data written by last month's build.
class CacheStore {
  CacheStore(this._box);

  final Box<String> _box;

  static const _boxName = 'rw_cache_v1';

  static Future<CacheStore> open() async {
    await Hive.initFlutter();
    return CacheStore(await Hive.openBox<String>(_boxName));
  }

  /// Read an entry, with its age.
  ///
  /// Returns null only when nothing is stored — an expired entry still comes
  /// back, marked stale, because showing yesterday's search beats showing a
  /// spinner that will never resolve on a train.
  CachedEntry<T>? read<T>(
    String key,
    T Function(Map<String, dynamic> json) decode, {
    Duration? freshFor,
  }) {
    final raw = _box.get(key);
    if (raw == null) return null;

    try {
      final envelope = jsonDecode(raw) as Map<String, dynamic>;
      final storedAt =
          DateTime.fromMillisecondsSinceEpoch(envelope['at'] as int);
      final age = DateTime.now().difference(storedAt);
      return CachedEntry(
        value: decode(envelope['data'] as Map<String, dynamic>),
        storedAt: storedAt,
        isFresh: freshFor == null || age <= freshFor,
      );
    } catch (_) {
      // Corrupt or written by an older model shape. Drop it rather than
      // failing the read — a cache is never worth an error screen.
      unawaited(_box.delete(key));
      return null;
    }
  }

  CachedEntry<List<T>>? readList<T>(
    String key,
    T Function(Map<String, dynamic> json) decode, {
    Duration? freshFor,
  }) {
    final entry = read<List<dynamic>>(
      key,
      (json) => json['items'] as List<dynamic>,
      freshFor: freshFor,
    );
    if (entry == null) return null;
    return CachedEntry(
      value: entry.value
          .map((item) => decode(item as Map<String, dynamic>))
          .toList(growable: false),
      storedAt: entry.storedAt,
      isFresh: entry.isFresh,
    );
  }

  Future<void> write(String key, Map<String, dynamic> json) => _box.put(
        key,
        jsonEncode({'at': DateTime.now().millisecondsSinceEpoch, 'data': json}),
      );

  Future<void> writeList(String key, List<Map<String, dynamic>> items) =>
      write(key, {'items': items});

  Future<void> remove(String key) => _box.delete(key);

  /// Called on sign-out. Another person picking up the phone must not find the
  /// previous account's trips in a warm cache.
  Future<void> clear() => _box.clear();
}

class CachedEntry<T> {
  const CachedEntry({
    required this.value,
    required this.storedAt,
    required this.isFresh,
  });

  final T value;
  final DateTime storedAt;
  final bool isFresh;
}

/// Cache keys, in one place. Scattered string literals drift, and a drifted key
/// is a cache that silently never hits.
abstract final class CacheKeys {
  static const amenities = 'amenities';
  static String search(String signature) => 'search:$signature';
  static String property(String idOrSlug) => 'property:$idOrSlug';
  static const bookings = 'bookings';
  static String booking(String id) => 'booking:$id';
  static const wishlist = 'wishlist';
  static const currentUser = 'user';
}

// `unawaited` without importing dart:async into every caller.
void unawaited(Future<void> future) {}
