import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../../core/network/result.dart';
import '../../../../core/providers/repository_providers.dart';
import '../../../../core/theme/app_theme.dart';
import '../../data/models/property_models.dart';
import '../../domain/entities/search_criteria.dart';
import '../providers/search_provider.dart';

Future<void> showFilterSheet(BuildContext context) => showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      showDragHandle: true,
      builder: (_) => const FilterSheet(),
    );

/// Filters.
///
/// A bottom sheet rather than a screen: filtering is a modal decision the user
/// returns from, and a sheet keeps the results visible behind it so the effect
/// of a change is obvious.
class FilterSheet extends ConsumerWidget {
  const FilterSheet({super.key});

  static const _priceSteps = [
    (label: 'Under ₹2,500', min: null, max: 250000),
    (label: '₹2,500 – ₹5,000', min: 250000, max: 500000),
    (label: '₹5,000 – ₹10,000', min: 500000, max: 1000000),
    (label: '₹10,000+', min: 1000000, max: null),
  ];

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final criteria = ref.watch(searchCriteriaControllerProvider);
    final controller = ref.read(searchCriteriaControllerProvider.notifier);
    final theme = Theme.of(context);

    return DraggableScrollableSheet(
      expand: false,
      initialChildSize: 0.75,
      maxChildSize: 0.95,
      builder: (context, scrollController) => Column(
        children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(20, 4, 12, 8),
            child: Row(
              children: [
                Text('Filters', style: theme.textTheme.titleLarge),
                const Spacer(),
                if (criteria.activeFilterCount > 0)
                  TextButton(
                    onPressed: controller.clearFilters,
                    child: Text('Clear all (${criteria.activeFilterCount})'),
                  ),
              ],
            ),
          ),
          const Divider(height: 1),
          Expanded(
            child: ListView(
              controller: scrollController,
              padding: const EdgeInsets.fromLTRB(20, 16, 20, 32),
              children: [
                _GroupLabel('Property type'),
                Wrap(
                  spacing: 8,
                  runSpacing: 8,
                  children: [
                    for (final kind in PropertyKind.values)
                      FilterChip(
                        label: Text(kind.label),
                        selected: criteria.propertyTypes.contains(kind.wire),
                        onSelected: (_) => controller.toggleType(kind.wire),
                      ),
                  ],
                ),
                Gap.lg,

                _GroupLabel('Price per night'),
                // RadioGroup owns the selection; the tiles below only declare
                // their own value. The older per-tile groupValue/onChanged pair
                // is deprecated because it let the two drift out of sync.
                RadioGroup<String>(
                  groupValue:
                      '${criteria.minPriceMinor}:${criteria.maxPriceMinor}',
                  onChanged: (value) {
                    final step = _priceSteps.firstWhere(
                      (s) => '${s.min}:${s.max}' == value,
                      orElse: () => _priceSteps.first,
                    );
                    controller.setPriceRange(step.min, step.max);
                  },
                  child: Column(
                    children: [
                      for (final step in _priceSteps)
                        RadioListTile<String>(
                          value: '${step.min}:${step.max}',
                          contentPadding: EdgeInsets.zero,
                          dense: true,
                          title: Text(step.label),
                        ),
                    ],
                  ),
                ),
                if (criteria.minPriceMinor != null || criteria.maxPriceMinor != null)
                  TextButton(
                    onPressed: () => controller.setPriceRange(null, null),
                    child: const Text('Any price'),
                  ),
                Gap.lg,

                _GroupLabel('Guest rating'),
                Wrap(
                  spacing: 8,
                  children: [
                    for (final rating in [4.5, 4.0, 3.5])
                      ChoiceChip(
                        label: Text('$rating+'),
                        selected: criteria.minRating == rating,
                        onSelected: (selected) =>
                            controller.setMinRating(selected ? rating : null),
                      ),
                  ],
                ),
                Gap.lg,

                _GroupLabel('Booking'),
                SwitchListTile(
                  value: criteria.instantBookingOnly,
                  contentPadding: EdgeInsets.zero,
                  title: const Text('Instant booking'),
                  subtitle: const Text(
                    'Confirmed immediately, without waiting for the host',
                  ),
                  onChanged: controller.setInstantBooking,
                ),
                Gap.lg,

                _GroupLabel('Amenities'),
                const _AmenityFilters(),
              ],
            ),
          ),
          SafeArea(
            child: Padding(
              padding: const EdgeInsets.fromLTRB(20, 8, 20, 12),
              child: SizedBox(
                width: double.infinity,
                child: FilledButton(
                  onPressed: () => Navigator.of(context).pop(),
                  child: const Text('Show results'),
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }
}

/// Amenities come from the API and are cached for a day — the sheet must open
/// instantly, and a day-old amenity list is indistinguishable from a fresh one.
class _AmenityFilters extends ConsumerWidget {
  const _AmenityFilters();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final amenities = ref.watch(amenityListProvider);

    return amenities.when(
      loading: () => const Padding(
        padding: EdgeInsets.symmetric(vertical: 12),
        child: LinearProgressIndicator(),
      ),
      // A failed amenity fetch hides the filter rather than showing an error:
      // it is one optional filter among several, and an error block here would
      // imply the whole sheet is broken.
      error: (_, _) => const SizedBox.shrink(),
      data: (items) {
        final criteria = ref.watch(searchCriteriaControllerProvider);
        final controller = ref.read(searchCriteriaControllerProvider.notifier);
        final filterable = items.where((a) => a.isFilterable).take(12);

        return Wrap(
          spacing: 8,
          runSpacing: 8,
          children: [
            for (final amenity in filterable)
              FilterChip(
                label: Text(amenity.label),
                selected: criteria.amenities.contains(amenity.code),
                onSelected: (_) => controller.toggleAmenity(amenity.code),
              ),
          ],
        );
      },
    );
  }
}

class _GroupLabel extends StatelessWidget {
  const _GroupLabel(this.text);

  final String text;

  @override
  Widget build(BuildContext context) => Padding(
        padding: const EdgeInsets.only(bottom: 10),
        child: Text(
          text,
          style: Theme.of(context)
              .textTheme
              .titleSmall
              ?.copyWith(fontWeight: FontWeight.w600),
        ),
      );
}

/// The amenity catalogue.
final amenityListProvider = FutureProvider<List<AmenityDto>>((ref) async {
  final result = await ref.watch(catalogRepositoryProvider).amenities();
  return switch (result) {
    Ok<List<AmenityDto>>(:final value) => value,
    Err<List<AmenityDto>>(:final failure) => throw failure,
  };
});
