import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../../core/theme/app_theme.dart';
import '../../../../shared/widgets/paged_list_view.dart';
import '../../../../shared/widgets/state_views.dart';
import '../../domain/entities/search_criteria.dart';
import '../providers/search_provider.dart';
import '../widgets/filter_sheet.dart';
import '../widgets/property_card.dart';
import '../widgets/search_bar_field.dart';

/// Search results.
///
/// Infinite scroll over cursor pagination, with the criteria held in their own
/// provider so a filter change starts a fresh first page without tearing the
/// screen down.
class SearchScreen extends ConsumerWidget {
  const SearchScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final criteria = ref.watch(searchCriteriaControllerProvider);
    final results = ref.watch(searchResultsProvider);
    final notifier = ref.read(searchResultsProvider.notifier);
    final theme = Theme.of(context);

    return Scaffold(
      appBar: AppBar(
        title: const SearchBarField(),
        titleSpacing: 16,
        actions: [
          Stack(
            alignment: Alignment.center,
            children: [
              IconButton(
                icon: const Icon(Icons.tune_rounded),
                tooltip: 'Filters',
                onPressed: () => showFilterSheet(context),
              ),
              if (criteria.activeFilterCount > 0)
                Positioned(
                  top: 8,
                  right: 6,
                  child: Container(
                    padding: const EdgeInsets.symmetric(horizontal: 5, vertical: 1),
                    decoration: BoxDecoration(
                      color: theme.colorScheme.primary,
                      borderRadius: BorderRadius.circular(10),
                    ),
                    child: Text(
                      '${criteria.activeFilterCount}',
                      style: theme.textTheme.labelSmall
                          ?.copyWith(color: theme.colorScheme.onPrimary),
                    ),
                  ),
                ),
            ],
          ),
        ],
        bottom: PreferredSize(
          preferredSize: const Size.fromHeight(48),
          child: _ResultsBar(criteria: criteria),
        ),
      ),
      body: Column(
        children: [
          if (results.isStale)
            StaleDataBanner(
              cachedAt: results.cachedAt,
              onRefresh: notifier.refresh,
            ),
          Expanded(
            child: PagedListView<dynamic>(
              state: results,
              onLoadMore: notifier.loadMore,
              onRefresh: notifier.refresh,
              onRetry: notifier.retryPage,
              emptyTitle: 'No stays match those filters',
              emptyDescription:
                  'Try widening the dates, raising the price range, or removing an amenity.',
              emptyIcon: Icons.search_off_rounded,
              emptyAction: FilledButton.tonal(
                onPressed: () =>
                    ref.read(searchCriteriaControllerProvider.notifier).clearFilters(),
                child: const Text('Clear filters'),
              ),
              itemBuilder: (context, item, index) => PropertyCard(
                item: item,
                nights: criteria.hasDates ? criteria.nights : null,
              ),
            ),
          ),
        ],
      ),
    );
  }
}

/// The count and the sort control.
class _ResultsBar extends ConsumerWidget {
  const _ResultsBar({required this.criteria});

  final SearchCriteria criteria;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final results = ref.watch(searchResultsProvider);
    final theme = Theme.of(context);

    final label = results.isInitialLoading
        ? 'Searching…'
        : '${results.totalEstimate ?? results.items.length} '
            '${(results.totalEstimate ?? results.items.length) == 1 ? 'stay' : 'stays'}'
            '${criteria.hasDates ? ' · ${criteria.nights} night${criteria.nights == 1 ? '' : 's'}' : ''}';

    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 0, 8, 8),
      child: Row(
        children: [
          Expanded(
            child: Text(
              label,
              // Announced when it changes, so a screen-reader user learns the
              // result count without hunting for it.
              semanticsLabel: label,
              style: theme.textTheme.bodyMedium,
            ),
          ),
          DropdownButtonHideUnderline(
            child: DropdownButton<SearchSort>(
              value: criteria.sort,
              isDense: true,
              borderRadius: BorderRadius.circular(12),
              onChanged: (sort) {
                if (sort != null) {
                  ref.read(searchCriteriaControllerProvider.notifier).setSort(sort);
                }
              },
              items: [
                for (final sort in SearchSort.values)
                  DropdownMenuItem(
                    value: sort,
                    child: Text(sort.label, style: theme.textTheme.bodySmall),
                  ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

/// The skeleton shown on the very first load, shaped like a property card so
/// the layout does not jump when real content arrives.
class PropertyCardSkeleton extends StatelessWidget {
  const PropertyCardSkeleton({super.key});

  @override
  Widget build(BuildContext context) => const Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          ShimmerBox(height: 180, radius: 16),
          Gap.sm,
          ShimmerBox(width: 220),
          Gap.xs,
          ShimmerBox(width: 140, height: 12),
        ],
      );
}
