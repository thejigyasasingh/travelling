import 'dart:convert';

import 'package:flutter/foundation.dart';
import 'package:riverpod_annotation/riverpod_annotation.dart';

import '../../../../core/providers/app_providers.dart';
import '../../../../core/storage/cache_store.dart';

part 'wishlist_provider.g.dart';

/// A saved stay.
///
/// Stores a **snapshot** of the card, not just an id. That is what lets the
/// wishlist render instantly with no N+1 fetch and, more importantly, what
/// makes it work offline — the whole point of a saved list is that it is there
/// on the flight when you are deciding.
@immutable
class WishlistEntry {
  const WishlistEntry({
    required this.propertyId,
    required this.slug,
    required this.name,
    required this.city,
    required this.currency,
    required this.savedAt,
    this.coverImageUrl,
    this.fromPriceMinor,
    this.reviewAverage = 0,
    this.reviewCount = 0,
  });

  factory WishlistEntry.fromJson(Map<String, dynamic> json) => WishlistEntry(
        propertyId: json['property_id'] as String,
        slug: json['slug'] as String? ?? '',
        name: json['name'] as String? ?? '',
        city: json['city'] as String? ?? '',
        currency: json['currency'] as String? ?? 'INR',
        savedAt: DateTime.parse(json['saved_at'] as String),
        coverImageUrl: json['cover_image_url'] as String?,
        fromPriceMinor: (json['from_price_minor'] as num?)?.toInt(),
        reviewAverage: (json['review_average'] as num?)?.toDouble() ?? 0,
        reviewCount: (json['review_count'] as num?)?.toInt() ?? 0,
      );

  final String propertyId;
  final String slug;
  final String name;
  final String city;
  final String currency;
  final DateTime savedAt;
  final String? coverImageUrl;
  final int? fromPriceMinor;
  final double reviewAverage;
  final int reviewCount;

  Map<String, dynamic> toJson() => {
        'property_id': propertyId,
        'slug': slug,
        'name': name,
        'city': city,
        'currency': currency,
        'saved_at': savedAt.toIso8601String(),
        'cover_image_url': coverImageUrl,
        'from_price_minor': fromPriceMinor,
        'review_average': reviewAverage,
        'review_count': reviewCount,
      };

  @override
  bool operator ==(Object other) =>
      other is WishlistEntry && other.propertyId == propertyId;

  @override
  int get hashCode => propertyId.hashCode;
}

/// The wishlist.
///
/// **There is no wishlist endpoint yet** — the backend has not shipped one. It
/// lives on the device, which means it does not follow the guest to another
/// phone and is lost if the app is uninstalled. That limitation is surfaced on
/// the screen rather than hidden.
///
/// Shipping it anyway is deliberate: a wishlist is how people plan a trip over
/// several days, and a device-local one is far better than none. The state is
/// held here rather than read from disk on every build, so a heart taps
/// instantly — a saved-stay toggle that waits on I/O feels broken.
@Riverpod(keepAlive: true)
class Wishlist extends _$Wishlist {
  @override
  List<WishlistEntry> build() {
    final cache = ref.watch(cacheStoreProvider);
    final entry = cache.readList(CacheKeys.wishlist, WishlistEntry.fromJson);
    final items = entry?.value.toList() ?? <WishlistEntry>[];
    // Newest first: the thing just saved is the thing you want to see.
    items.sort((a, b) => b.savedAt.compareTo(a.savedAt));
    return items;
  }

  bool contains(String propertyId) =>
      state.any((e) => e.propertyId == propertyId);

  Future<void> toggle(WishlistEntry entry) async {
    final saved = contains(entry.propertyId);
    // Optimistic by construction: state changes first, disk follows. A heart
    // that waits for I/O to turn red reads as a broken button.
    state = saved
        ? state.where((e) => e.propertyId != entry.propertyId).toList()
        : [entry, ...state.where((e) => e.propertyId != entry.propertyId)];
    await _persist();
  }

  Future<void> clear() async {
    state = const [];
    await ref.read(cacheStoreProvider).remove(CacheKeys.wishlist);
  }

  Future<void> _persist() => ref.read(cacheStoreProvider).writeList(
        CacheKeys.wishlist,
        state.map((e) => e.toJson()).toList(growable: false),
      );
}

/// Whether one property is saved. A separate provider so a card rebuilds only
/// when *its* saved state changes, not on every wishlist mutation.
@riverpod
bool isSaved(Ref ref, String propertyId) =>
    ref.watch(wishlistProvider).any((e) => e.propertyId == propertyId);

/// Exposed for the tests, which assert the on-disk shape survives a round trip.
String encodeWishlist(List<WishlistEntry> entries) =>
    jsonEncode(entries.map((e) => e.toJson()).toList());
