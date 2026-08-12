import 'package:cached_network_image/cached_network_image.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../../core/error/failure.dart';
import '../../../../core/router/app_router.dart';
import '../../../../core/theme/app_theme.dart';
import '../../../../core/utils/dates.dart';
import '../../../../core/utils/money.dart';
import '../../../../shared/widgets/app_shell.dart';
import '../../../../shared/widgets/state_views.dart';
import '../../../wishlist/presentation/providers/wishlist_provider.dart';
import '../../data/models/property_models.dart';
import '../../domain/entities/cancellation_policy.dart';
import '../../domain/entities/search_criteria.dart';
import '../providers/property_provider.dart';

/// Property details, with the booking panel pinned to the bottom.
///
/// The panel is `bottomNavigationBar` rather than a floating overlay so it is
/// laid out above the system inset and never sits under a gesture bar — and so
/// the price and the reserve button are always one glance away, which is what
/// the screen is for.
class PropertyScreen extends ConsumerWidget {
  const PropertyScreen({required this.identifier, super.key});

  final String identifier;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final property = ref.watch(propertyProvider(identifier));

    return property.when(
      loading: () => const Scaffold(body: LoadingView(label: 'Loading this stay')),
      error: (error, _) => Scaffold(
        appBar: AppBar(),
        body: ErrorView(
          failure: error is Failure ? error : const Failure.unexpected(),
          onRetry: () => ref.invalidate(propertyProvider(identifier)),
          title: 'We could not load this stay',
        ),
      ),
      data: (data) => _PropertyView(property: data),
    );
  }
}

class _PropertyView extends ConsumerWidget {
  const _PropertyView({required this.property});

  final PropertyDto property;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final theme = Theme.of(context);
    final policy = cancellationPolicy(property.cancellationPolicy);
    final saved = ref.watch(isSavedProvider(property.id));

    return Scaffold(
      body: CustomScrollView(
        slivers: [
          SliverAppBar(
            expandedHeight: 280,
            pinned: true,
            leading: IconButton(
              icon: const CircleAvatar(
                backgroundColor: Colors.black45,
                child: Icon(Icons.arrow_back, color: Colors.white, size: 20),
              ),
              onPressed: () => popOrGo(context, Routes.search),
            ),
            actions: [
              IconButton(
                tooltip: saved ? 'Remove from wishlist' : 'Save to wishlist',
                icon: CircleAvatar(
                  backgroundColor: Colors.black45,
                  child: Icon(
                    saved ? Icons.favorite_rounded : Icons.favorite_border_rounded,
                    color: saved ? theme.colorScheme.error : Colors.white,
                    size: 20,
                  ),
                ),
                onPressed: () => ref.read(wishlistProvider.notifier).toggle(
                      WishlistEntry(
                        propertyId: property.id,
                        slug: property.slug,
                        name: property.name,
                        city: property.city,
                        currency: property.currency,
                        savedAt: DateTime.now(),
                        coverImageUrl: property.images.isEmpty
                            ? null
                            : property.images.first.url,
                        fromPriceMinor: _cheapestRate(property),
                        reviewAverage: property.reviewAverage,
                        reviewCount: property.reviewCount,
                      ),
                    ),
              ),
              const SizedBox(width: 8),
            ],
            flexibleSpace: FlexibleSpaceBar(
              background: _Gallery(images: property.images),
            ),
          ),

          SliverPadding(
            padding: const EdgeInsets.fromLTRB(16, 16, 16, 32),
            sliver: SliverList.list(
              children: [
                Text(
                  property.name,
                  style: theme.textTheme.headlineSmall
                      ?.copyWith(fontWeight: FontWeight.w700),
                ),
                Gap.xs,
                Wrap(
                  spacing: 8,
                  crossAxisAlignment: WrapCrossAlignment.center,
                  children: [
                    if (property.reviewCount > 0) ...[
                      Icon(Icons.star_rounded,
                          size: 18, color: theme.colorScheme.primary),
                      Text(
                        '${property.reviewAverage.toStringAsFixed(1)} '
                        '(${property.reviewCount})',
                        style: theme.textTheme.bodyMedium
                            ?.copyWith(fontWeight: FontWeight.w600),
                      ),
                    ] else
                      Text('New', style: theme.textTheme.bodyMedium),
                    Text('· ${PropertyKind.labelFor(property.propertyType)}',
                        style: theme.textTheme.bodyMedium),
                    Text('· ${property.city}',
                        style: theme.textTheme.bodyMedium),
                  ],
                ),
                Gap.lg,

                _Section(
                  title: 'About this place',
                  child: Text(property.description,
                      style: theme.textTheme.bodyMedium),
                ),

                if (property.roomTypes.isNotEmpty)
                  _Section(
                    title: 'Rooms',
                    child: Column(
                      children: [
                        for (final room in property.roomTypes)
                          _RoomTile(room: room, propertyId: property.id),
                      ],
                    ),
                  ),

                if (property.amenityCodes.isNotEmpty)
                  _Section(
                    title: 'What this place offers',
                    child: Wrap(
                      spacing: 8,
                      runSpacing: 8,
                      children: [
                        for (final code in property.amenityCodes)
                          Chip(
                            label: Text(code.replaceAll('_', ' ')),
                            visualDensity: VisualDensity.compact,
                          ),
                      ],
                    ),
                  ),

                _Section(
                  title: 'Where you will be',
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(property.address, style: theme.textTheme.bodyMedium),
                      if (property.locationIsApproximate) ...[
                        Gap.sm,
                        _Note(
                          'The exact address is shared once your booking is '
                          'confirmed. Publishing a precise address would tell '
                          'anyone where an unoccupied home is.',
                        ),
                      ],
                    ],
                  ),
                ),

                _Section(
                  title: 'Things to know',
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      _Fact(
                        label: 'Check in / out',
                        value:
                            'From ${property.checkInFrom} · until ${property.checkOutBy}',
                      ),
                      Gap.sm,
                      _Fact(
                        label: 'Cancellation — ${policy.label}',
                        value: policy.detail,
                      ),
                      Gap.xs,
                      Text(
                        refundFootnote,
                        style: theme.textTheme.bodySmall?.copyWith(
                          color: theme.colorScheme.onSurfaceVariant,
                        ),
                      ),
                      if (property.houseRules.isNotEmpty) ...[
                        Gap.sm,
                        for (final rule in property.houseRules)
                          Padding(
                            padding: const EdgeInsets.only(bottom: 4),
                            child: Text('• $rule',
                                style: theme.textTheme.bodyMedium),
                          ),
                      ],
                    ],
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
      bottomNavigationBar: _BookingPanel(property: property),
    );
  }
}

int? _cheapestRate(PropertyDto property) => property.roomTypes.isEmpty
    ? null
    : property.roomTypes
        .map((r) => r.baseRateMinor)
        .reduce((a, b) => a < b ? a : b);

/// Dates, guests, live quote and the reserve button.
class _BookingPanel extends ConsumerWidget {
  const _BookingPanel({required this.property});

  final PropertyDto property;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final theme = Theme.of(context);
    final selection = ref.watch(staySelectionControllerProvider(property.id));
    final controller =
        ref.read(staySelectionControllerProvider(property.id).notifier);

    // Falls back to the first room, so the panel is usable the moment the
    // screen opens rather than after a tap nobody knows to make.
    final room = property.roomTypes.firstWhere(
      (r) => r.id == selection.roomTypeId,
      orElse: () => property.roomTypes.isEmpty
          ? const RoomTypeDto(id: '', name: '')
          : property.roomTypes.first,
    );

    final quote = ref.watch(stayQuoteProvider(property.id, room.minNights));
    final hasDates = isValidStay(selection.checkIn, selection.checkOut);

    return SafeArea(
      child: Container(
        decoration: BoxDecoration(
          color: theme.colorScheme.surface,
          border: Border(
            top: BorderSide(color: theme.colorScheme.outlineVariant),
          ),
        ),
        padding: const EdgeInsets.fromLTRB(16, 12, 16, 12),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Row(
              children: [
                Expanded(
                  child: OutlinedButton.icon(
                    icon: const Icon(Icons.calendar_today_rounded, size: 16),
                    label: Text(
                      hasDates
                          ? formatStay(selection.checkIn!, selection.checkOut!)
                          : 'Add dates',
                    ),
                    onPressed: () async {
                      final range = await showDateRangePicker(
                        context: context,
                        firstDate: DateTime.now(),
                        lastDate: DateTime.now().add(const Duration(days: 365)),
                        helpText: 'Select your stay',
                      );
                      if (range != null) {
                        controller
                          ..setRoom(room.id)
                          ..setDates(toIso(range.start), toIso(range.end));
                      }
                    },
                  ),
                ),
              ],
            ),
            Gap.sm,
            _QuoteSummary(
              quote: quote,
              room: room,
              hasDates: hasDates,
              nights: hasDates
                  ? nightsBetween(selection.checkIn!, selection.checkOut!)
                  : 0,
            ),
            Gap.sm,
            SizedBox(
              width: double.infinity,
              child: FilledButton(
                onPressed: quote.value?.isAvailable ?? false
                    ? () => context.push(
                          '${Routes.booking(property.id)}'
                          '?room=${room.id}'
                          '&check_in=${selection.checkIn}'
                          '&check_out=${selection.checkOut}'
                          '&adults=${selection.adults}'
                          '&children=${selection.children}'
                          '&rooms=${selection.rooms}',
                        )
                    : null,
                child: Text(hasDates ? 'Reserve' : 'Check availability'),
              ),
            ),
            Gap.xs,
            Text(
              'You will not be charged until the next step.',
              style: theme.textTheme.bodySmall
                  ?.copyWith(color: theme.colorScheme.onSurfaceVariant),
            ),
          ],
        ),
      ),
    );
  }
}

class _QuoteSummary extends StatelessWidget {
  const _QuoteSummary({
    required this.quote,
    required this.room,
    required this.hasDates,
    required this.nights,
  });

  final AsyncValue<QuoteDto?> quote;
  final RoomTypeDto room;
  final bool hasDates;
  final int nights;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    if (!hasDates) {
      return Align(
        alignment: Alignment.centerLeft,
        child: Text.rich(
          TextSpan(
            children: [
              TextSpan(
                text: formatMinor(room.baseRateMinor, room.currency,
                    compact: true),
                style: theme.textTheme.titleMedium
                    ?.copyWith(fontWeight: FontWeight.w700),
              ),
              TextSpan(
                text: ' / night · add dates for the total',
                style: theme.textTheme.bodySmall
                    ?.copyWith(color: theme.colorScheme.onSurfaceVariant),
              ),
            ],
          ),
        ),
      );
    }

    return quote.when(
      loading: () => const Row(
        children: [
          SizedBox(
              width: 14,
              height: 14,
              child: CircularProgressIndicator(strokeWidth: 2)),
          SizedBox(width: 8),
          Text('Checking availability…'),
        ],
      ),
      error: (error, _) => Text(
        error is Failure ? error.message : 'Could not price these dates.',
        style: theme.textTheme.bodySmall
            ?.copyWith(color: theme.colorScheme.error),
      ),
      data: (data) {
        if (data == null) return const SizedBox.shrink();
        if (!data.isAvailable) {
          return Text(
            'Not available for these dates.',
            style: theme.textTheme.bodyMedium
                ?.copyWith(color: theme.colorScheme.error),
          );
        }
        return Row(
          children: [
            Expanded(
              child: Text(
                '${formatMinor(data.averageNightlyMinor, data.currency, compact: true)}'
                ' × $nights night${nights == 1 ? '' : 's'}',
                style: theme.textTheme.bodySmall,
              ),
            ),
            Text(
              formatMinor(data.totalMinor, data.currency),
              style: theme.textTheme.titleMedium
                  ?.copyWith(fontWeight: FontWeight.w700),
            ),
          ],
        );
      },
    );
  }
}

class _RoomTile extends ConsumerWidget {
  const _RoomTile({required this.room, required this.propertyId});

  final RoomTypeDto room;
  final String propertyId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final theme = Theme.of(context);
    final selected =
        ref.watch(staySelectionControllerProvider(propertyId)).roomTypeId == room.id;

    return Card(
      margin: const EdgeInsets.only(bottom: 8),
      color: selected ? theme.colorScheme.primaryContainer : null,
      child: ListTile(
        onTap: () => ref
            .read(staySelectionControllerProvider(propertyId).notifier)
            .setRoom(room.id),
        title: Text(room.name,
            style: const TextStyle(fontWeight: FontWeight.w600)),
        subtitle: Text(
          [
            if (room.bedType.isNotEmpty) room.bedType,
            'sleeps ${room.maxAdults + room.maxChildren}',
            if (room.minNights > 1) '${room.minNights}-night minimum',
          ].join(' · '),
        ),
        trailing: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          crossAxisAlignment: CrossAxisAlignment.end,
          children: [
            Text(
              formatMinor(room.baseRateMinor, room.currency, compact: true),
              style: const TextStyle(fontWeight: FontWeight.w700),
            ),
            Text('per night', style: theme.textTheme.bodySmall),
            if (room.unitsAvailable != null && room.unitsAvailable! <= 3)
              Text(
                room.unitsAvailable == 0
                    ? 'Sold out'
                    : 'Only ${room.unitsAvailable} left',
                style: theme.textTheme.labelSmall
                    ?.copyWith(color: theme.colorScheme.error),
              ),
          ],
        ),
      ),
    );
  }
}

class _Gallery extends StatelessWidget {
  const _Gallery({required this.images});

  final List<ImageDto> images;

  @override
  Widget build(BuildContext context) {
    if (images.isEmpty) {
      return ColoredBox(
        color: Theme.of(context).colorScheme.surfaceContainerHighest,
        child: const Center(child: Icon(Icons.photo_outlined, size: 40)),
      );
    }
    return PageView.builder(
      itemCount: images.length,
      itemBuilder: (context, index) => CachedNetworkImage(
        imageUrl: images[index].url,
        fit: BoxFit.cover,
        placeholder: (_, _) => ColoredBox(
          color: Theme.of(context).colorScheme.surfaceContainerHighest,
        ),
        errorWidget: (_, _, _) => ColoredBox(
          color: Theme.of(context).colorScheme.surfaceContainerHighest,
          child: const Center(child: Icon(Icons.broken_image_outlined)),
        ),
      ),
    );
  }
}

class _Section extends StatelessWidget {
  const _Section({required this.title, required this.child});

  final String title;
  final Widget child;

  @override
  Widget build(BuildContext context) => Padding(
        padding: const EdgeInsets.only(bottom: 24),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              title,
              style: Theme.of(context)
                  .textTheme
                  .titleMedium
                  ?.copyWith(fontWeight: FontWeight.w600),
            ),
            Gap.sm,
            child,
          ],
        ),
      );
}

class _Fact extends StatelessWidget {
  const _Fact({required this.label, required this.value});

  final String label;
  final String value;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(label,
            style: theme.textTheme.bodyMedium
                ?.copyWith(fontWeight: FontWeight.w600)),
        Text(value,
            style: theme.textTheme.bodySmall
                ?.copyWith(color: theme.colorScheme.onSurfaceVariant)),
      ],
    );
  }
}

class _Note extends StatelessWidget {
  const _Note(this.text);

  final String text;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: theme.colorScheme.surfaceContainerHighest,
        borderRadius: BorderRadius.circular(12),
      ),
      child: Text(text, style: theme.textTheme.bodySmall),
    );
  }
}
