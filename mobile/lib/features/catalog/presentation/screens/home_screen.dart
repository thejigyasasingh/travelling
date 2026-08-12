import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../../core/router/app_router.dart';
import '../../../../core/theme/app_theme.dart';
import '../../domain/entities/search_criteria.dart';
import '../providers/search_provider.dart';
import '../../../../shared/widgets/state_views.dart';
import '../widgets/property_card.dart';

/// Home.
///
/// One job: get someone into a search. Everything below the fold is a shortcut
/// into one rather than content for its own sake, because nobody opens a
/// booking app to read.
class HomeScreen extends ConsumerWidget {
  const HomeScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final theme = Theme.of(context);
    final featured = ref.watch(featuredStaysProvider);

    return Scaffold(
      body: RefreshIndicator(
        onRefresh: () async => ref.invalidate(featuredStaysProvider),
        child: CustomScrollView(
          slivers: [
            SliverAppBar.large(
              title: const Text('Roaming & Wandering'),
              expandedHeight: 150,
              flexibleSpace: FlexibleSpaceBar(
                background: DecoratedBox(
                  decoration: BoxDecoration(
                    gradient: LinearGradient(
                      begin: Alignment.topLeft,
                      end: Alignment.bottomRight,
                      colors: [
                        theme.colorScheme.primaryContainer,
                        theme.colorScheme.surface,
                      ],
                    ),
                  ),
                ),
              ),
            ),

            SliverToBoxAdapter(
              child: Padding(
                padding: const EdgeInsets.fromLTRB(16, 8, 16, 0),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'Find a place worth the journey',
                      style: theme.textTheme.headlineSmall
                          ?.copyWith(fontWeight: FontWeight.w700),
                    ),
                    Gap.sm,
                    Text(
                      'Hotels, villas, apartments, homestays and resorts across '
                      'India. Clear prices, fair cancellation.',
                      style: theme.textTheme.bodyMedium
                          ?.copyWith(color: theme.colorScheme.onSurfaceVariant),
                    ),
                    Gap.md,
                    _SearchLauncher(
                      onTap: () => context.go(Routes.search),
                    ),
                    Gap.lg,
                    Text(
                      'Browse by type',
                      style: theme.textTheme.titleMedium
                          ?.copyWith(fontWeight: FontWeight.w600),
                    ),
                    Gap.sm,
                  ],
                ),
              ),
            ),

            SliverToBoxAdapter(
              child: SizedBox(
                height: 96,
                child: ListView.separated(
                  scrollDirection: Axis.horizontal,
                  padding: const EdgeInsets.symmetric(horizontal: 16),
                  itemCount: PropertyKind.values.length,
                  separatorBuilder: (_, _) => Gap.sm,
                  itemBuilder: (context, index) {
                    final kind = PropertyKind.values[index];
                    return _TypeTile(
                      label: kind.label,
                      onTap: () {
                        ref
                            .read(searchCriteriaControllerProvider.notifier)
                            .toggleType(kind.wire);
                        context.go(Routes.search);
                      },
                    );
                  },
                ),
              ),
            ),

            SliverToBoxAdapter(
              child: Padding(
                padding: const EdgeInsets.fromLTRB(16, 24, 16, 8),
                child: Row(
                  children: [
                    Expanded(
                      child: Text(
                        'Top rated stays',
                        style: theme.textTheme.titleMedium
                            ?.copyWith(fontWeight: FontWeight.w600),
                      ),
                    ),
                    TextButton(
                      onPressed: () => context.go(Routes.search),
                      child: const Text('See all'),
                    ),
                  ],
                ),
              ),
            ),

            featured.when(
              loading: () => const SliverToBoxAdapter(
                child: Padding(
                  padding: EdgeInsets.symmetric(horizontal: 16),
                  child: Column(
                    children: [
                      PropertyCardSkeletonRow(),
                      Gap.md,
                      PropertyCardSkeletonRow(),
                    ],
                  ),
                ),
              ),
              // Home degrades quietly. A failed "top rated" strip is not worth
              // an error screen on the app's front door — search still works,
              // and that is what this screen exists to reach.
              error: (_, _) => const SliverToBoxAdapter(child: SizedBox.shrink()),
              data: (items) => SliverPadding(
                padding: const EdgeInsets.fromLTRB(16, 0, 16, 24),
                sliver: SliverList.separated(
                  itemCount: items.length,
                  separatorBuilder: (_, _) => Gap.md,
                  itemBuilder: (context, index) =>
                      PropertyCard(item: items[index]),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _SearchLauncher extends StatelessWidget {
  const _SearchLauncher({required this.onTap});

  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Material(
      color: theme.colorScheme.surfaceContainerHighest,
      borderRadius: BorderRadius.circular(14),
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(14),
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 16),
          child: Row(
            children: [
              Icon(Icons.search_rounded, color: theme.colorScheme.primary),
              Gap.sm,
              Text(
                'Where to?',
                style: theme.textTheme.bodyLarge
                    ?.copyWith(color: theme.colorScheme.onSurfaceVariant),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _TypeTile extends StatelessWidget {
  const _TypeTile({required this.label, required this.onTap});

  final String label;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return SizedBox(
      width: 120,
      child: Card(
        clipBehavior: Clip.antiAlias,
        child: InkWell(
          onTap: onTap,
          child: Padding(
            padding: const EdgeInsets.all(12),
            child: Align(
              alignment: Alignment.bottomLeft,
              child: Text(
                label,
                style: theme.textTheme.titleSmall
                    ?.copyWith(fontWeight: FontWeight.w600),
              ),
            ),
          ),
        ),
      ),
    );
  }
}

class PropertyCardSkeletonRow extends StatelessWidget {
  const PropertyCardSkeletonRow({super.key});

  @override
  Widget build(BuildContext context) => const Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          ShimmerBox(height: 170, radius: 16),
          Gap.sm,
          ShimmerBox(width: 200),
        ],
      );
}
