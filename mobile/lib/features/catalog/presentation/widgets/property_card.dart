import 'package:cached_network_image/cached_network_image.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../../core/router/app_router.dart';
import '../../../../core/theme/app_theme.dart';
import '../../../../core/utils/money.dart';
import '../../../wishlist/presentation/providers/wishlist_provider.dart';
import '../../data/models/property_models.dart';
import '../../domain/entities/cancellation_policy.dart';

/// A stay, as a card.
///
/// The price shown depends on whether the search carried dates. With dates it
/// is the **total for the stay**; without, it is a nightly "from". They are
/// labelled differently and never interchanged — showing a nightly rate where a
/// guest expects a total is the oldest dark pattern in travel.
class PropertyCard extends ConsumerWidget {
  const PropertyCard({required this.item, super.key, this.nights});

  final SearchItemDto item;
  final int? nights;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final theme = Theme.of(context);
    final policy = cancellationPolicy(item.cancellationPolicy);

    // "Sold out for these dates" only means something when there *are* dates.
    // A dateless search cannot be answered for availability, so the API returns
    // `is_available: false` — and showing the overlay then tells every browsing
    // guest that the entire catalogue is unavailable.
    final soldOut = nights != null && !item.isAvailable;

    return Card(
      clipBehavior: Clip.antiAlias,
      child: InkWell(
        onTap: () => context.push(Routes.property(item.slug)),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Stack(
              children: [
                AspectRatio(
                  aspectRatio: 4 / 3,
                  child: _Cover(url: item.coverImageUrl),
                ),
                Positioned(
                  top: 8,
                  right: 8,
                  child: _SaveButton(item: item),
                ),
                if (item.instantBooking)
                  Positioned(
                    bottom: 8,
                    left: 8,
                    child: _Pill(
                      label: 'Instant booking',
                      background: theme.colorScheme.primary,
                      foreground: theme.colorScheme.onPrimary,
                    ),
                  ),
                if (soldOut)
                  Positioned.fill(
                    child: ColoredBox(
                      color: theme.colorScheme.surface.withValues(alpha: 0.7),
                      child: Center(
                        child: _Pill(
                          label: 'Sold out for these dates',
                          background: theme.colorScheme.errorContainer,
                          foreground: theme.colorScheme.onErrorContainer,
                        ),
                      ),
                    ),
                  ),
              ],
            ),
            Padding(
              padding: const EdgeInsets.all(14),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Expanded(
                        child: Text(
                          item.name,
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                          style: theme.textTheme.titleMedium
                              ?.copyWith(fontWeight: FontWeight.w600),
                        ),
                      ),
                      Gap.sm,
                      _Rating(
                        value: item.reviewAverage,
                        count: item.reviewCount,
                      ),
                    ],
                  ),
                  Gap.xs,
                  Text(
                    item.distanceM == null
                        ? item.city
                        : '${item.city} · ${(item.distanceM! / 1000).toStringAsFixed(1)} km away',
                    style: theme.textTheme.bodySmall
                        ?.copyWith(color: theme.colorScheme.onSurfaceVariant),
                  ),
                  Gap.xs,
                  Text(
                    policy.short,
                    style: theme.textTheme.bodySmall
                        ?.copyWith(color: theme.colorScheme.onSurfaceVariant),
                  ),
                  Gap.sm,
                  _Price(item: item, nights: nights),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _Price extends StatelessWidget {
  const _Price({required this.item, this.nights});

  final SearchItemDto item;
  final int? nights;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final muted = theme.textTheme.bodySmall
        ?.copyWith(color: theme.colorScheme.onSurfaceVariant);

    final total = item.totalPriceMinor;
    final from = item.fromPriceMinor;

    return Row(
      crossAxisAlignment: CrossAxisAlignment.end,
      children: [
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              if (total != null)
                Text.rich(
                  TextSpan(
                    children: [
                      TextSpan(
                        text: formatMinor(total, item.currency, compact: true),
                        style: theme.textTheme.titleMedium
                            ?.copyWith(fontWeight: FontWeight.w700),
                      ),
                      TextSpan(
                        text: nights == null
                            ? ' total'
                            : ' total · $nights night${nights == 1 ? '' : 's'}',
                        style: muted,
                      ),
                    ],
                  ),
                )
              else if (from != null)
                Text.rich(
                  TextSpan(
                    children: [
                      TextSpan(text: 'from ', style: muted),
                      TextSpan(
                        text: formatMinor(from, item.currency, compact: true),
                        style: theme.textTheme.titleMedium
                            ?.copyWith(fontWeight: FontWeight.w700),
                      ),
                      TextSpan(text: ' / night', style: muted),
                    ],
                  ),
                )
              else
                Text('Price on request', style: muted),
              Text('Includes taxes and fees', style: muted),
            ],
          ),
        ),
        Text('Sleeps ${item.maxOccupancy}', style: muted),
      ],
    );
  }
}

class _SaveButton extends ConsumerWidget {
  const _SaveButton({required this.item});

  final SearchItemDto item;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final saved = ref.watch(isSavedProvider(item.id));
    final theme = Theme.of(context);

    return Material(
      color: theme.colorScheme.surface.withValues(alpha: 0.9),
      shape: const CircleBorder(),
      child: IconButton(
        // Announced properly: a bare heart icon tells a screen reader nothing
        // about what it does or which stay it belongs to.
        tooltip: saved ? 'Remove from wishlist' : 'Save to wishlist',
        icon: Icon(
          saved ? Icons.favorite_rounded : Icons.favorite_border_rounded,
          color: saved ? theme.colorScheme.error : theme.colorScheme.onSurface,
          size: 20,
        ),
        onPressed: () => ref.read(wishlistProvider.notifier).toggle(
              WishlistEntry(
                propertyId: item.id,
                slug: item.slug,
                name: item.name,
                city: item.city,
                currency: item.currency,
                savedAt: DateTime.now(),
                coverImageUrl: item.coverImageUrl,
                fromPriceMinor: item.fromPriceMinor,
                reviewAverage: item.reviewAverage,
                reviewCount: item.reviewCount,
              ),
            ),
      ),
    );
  }
}

class _Rating extends StatelessWidget {
  const _Rating({required this.value, required this.count});

  final double value;
  final int count;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    // A new listing shows "New", not an empty five-star row — which reads as
    // "rated 0/5" and is both wrong and unfair to the host.
    if (count == 0) {
      return Text(
        'New',
        style: theme.textTheme.bodySmall
            ?.copyWith(color: theme.colorScheme.onSurfaceVariant),
      );
    }
    return Semantics(
      label: 'Rated ${value.toStringAsFixed(1)} out of 5 from $count reviews',
      excludeSemantics: true,
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(Icons.star_rounded, size: 16, color: theme.colorScheme.primary),
          const SizedBox(width: 2),
          Text(
            value.toStringAsFixed(1),
            style: theme.textTheme.bodyMedium
                ?.copyWith(fontWeight: FontWeight.w600),
          ),
          Text(
            ' ($count)',
            style: theme.textTheme.bodySmall
                ?.copyWith(color: theme.colorScheme.onSurfaceVariant),
          ),
        ],
      ),
    );
  }
}

class _Pill extends StatelessWidget {
  const _Pill({
    required this.label,
    required this.background,
    required this.foreground,
  });

  final String label;
  final Color background;
  final Color foreground;

  @override
  Widget build(BuildContext context) => Container(
        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
        decoration: BoxDecoration(
          color: background,
          borderRadius: BorderRadius.circular(20),
        ),
        child: Text(
          label,
          style: Theme.of(context)
              .textTheme
              .labelSmall
              ?.copyWith(color: foreground, fontWeight: FontWeight.w600),
        ),
      );
}

class _Cover extends StatelessWidget {
  const _Cover({this.url});

  final String? url;

  @override
  Widget build(BuildContext context) {
    final placeholder = ColoredBox(
      color: Theme.of(context).colorScheme.surfaceContainerHighest,
      child: Center(
        child: Icon(
          Icons.photo_outlined,
          color: Theme.of(context).colorScheme.outline,
        ),
      ),
    );

    if (url == null) return placeholder;
    return CachedNetworkImage(
      imageUrl: url!,
      fit: BoxFit.cover,
      width: double.infinity,
      // Cached to disk by the package, which is what makes a scrolled-past card
      // instant on the way back up and available offline.
      placeholder: (_, _) => placeholder,
      errorWidget: (_, _, _) => placeholder,
      fadeInDuration: const Duration(milliseconds: 180),
    );
  }
}
