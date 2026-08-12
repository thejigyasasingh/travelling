import 'package:cached_network_image/cached_network_image.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../../core/router/app_router.dart';
import '../../../../core/theme/app_theme.dart';
import '../../../../core/utils/dates.dart';
import '../../../../core/utils/money.dart';
import '../../../../shared/widgets/state_views.dart';
import '../providers/wishlist_provider.dart';

/// Saved stays.
///
/// Every card renders from the snapshot stored when it was saved, so this
/// screen needs no network at all — which is the point, because a wishlist is
/// what people open on a flight while deciding.
///
/// The device-local limitation is stated on the screen rather than hidden: a
/// guest who saves twelve stays on their phone and finds none on a tablet
/// deserves to know why before it happens.
class WishlistScreen extends ConsumerWidget {
  const WishlistScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final entries = ref.watch(wishlistProvider);
    final theme = Theme.of(context);

    return Scaffold(
      appBar: AppBar(
        title: const Text('Wishlist'),
        actions: [
          if (entries.isNotEmpty)
            TextButton(
              onPressed: () => ref.read(wishlistProvider.notifier).clear(),
              child: const Text('Clear all'),
            ),
        ],
      ),
      body: entries.isEmpty
          ? EmptyView(
              title: 'Nothing saved yet',
              description:
                  'Tap the heart on any stay to keep it here while you plan.',
              icon: Icons.favorite_border_rounded,
              action: FilledButton(
                onPressed: () => context.go(Routes.search),
                child: const Text('Browse stays'),
              ),
            )
          : ListView.separated(
              padding: const EdgeInsets.fromLTRB(16, 8, 16, 24),
              itemCount: entries.length + 1,
              separatorBuilder: (_, _) => Gap.md,
              itemBuilder: (context, index) {
                if (index == 0) {
                  return Padding(
                    padding: const EdgeInsets.only(bottom: 4),
                    child: Text(
                      'Saved on this device. Syncing across devices is coming — '
                      'for now, reinstalling the app clears this list.',
                      style: theme.textTheme.bodySmall
                          ?.copyWith(color: theme.colorScheme.onSurfaceVariant),
                    ),
                  );
                }
                final entry = entries[index - 1];
                return _WishlistCard(entry: entry);
              },
            ),
    );
  }
}

class _WishlistCard extends ConsumerWidget {
  const _WishlistCard({required this.entry});

  final WishlistEntry entry;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final theme = Theme.of(context);

    return Card(
      clipBehavior: Clip.antiAlias,
      child: InkWell(
        onTap: () => context.push(Routes.property(entry.slug)),
        child: Row(
          children: [
            SizedBox(
              width: 110,
              height: 110,
              child: entry.coverImageUrl == null
                  ? ColoredBox(color: theme.colorScheme.surfaceContainerHighest)
                  : CachedNetworkImage(
                      imageUrl: entry.coverImageUrl!,
                      fit: BoxFit.cover,
                      placeholder: (_, _) => ColoredBox(
                        color: theme.colorScheme.surfaceContainerHighest,
                      ),
                      errorWidget: (_, _, _) => ColoredBox(
                        color: theme.colorScheme.surfaceContainerHighest,
                      ),
                    ),
            ),
            Expanded(
              child: Padding(
                padding: const EdgeInsets.all(12),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      entry.name,
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: theme.textTheme.titleSmall
                          ?.copyWith(fontWeight: FontWeight.w600),
                    ),
                    Text(entry.city,
                        style: theme.textTheme.bodySmall?.copyWith(
                          color: theme.colorScheme.onSurfaceVariant,
                        )),
                    Gap.xs,
                    if (entry.fromPriceMinor != null)
                      Text(
                        '${formatMinor(entry.fromPriceMinor, entry.currency, compact: true)} / night',
                        style: theme.textTheme.bodyMedium
                            ?.copyWith(fontWeight: FontWeight.w600),
                      ),
                    const Spacer(),
                    Text('Saved ${formatRelative(entry.savedAt.toIso8601String())}',
                        style: theme.textTheme.labelSmall
                            ?.copyWith(color: theme.colorScheme.outline)),
                  ],
                ),
              ),
            ),
            IconButton(
              tooltip: 'Remove from wishlist',
              icon: Icon(Icons.favorite_rounded, color: theme.colorScheme.error),
              onPressed: () =>
                  ref.read(wishlistProvider.notifier).toggle(entry),
            ),
          ],
        ),
      ),
    );
  }
}
