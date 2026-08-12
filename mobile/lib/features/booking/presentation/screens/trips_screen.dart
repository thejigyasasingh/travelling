import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../../core/router/app_router.dart';
import '../../../../core/theme/app_theme.dart';
import '../../../../core/utils/dates.dart';
import '../../../../core/utils/money.dart';
import '../../../../shared/paged_state.dart';
import '../../../../shared/widgets/paged_list_view.dart';
import '../../../../shared/widgets/state_views.dart';
import '../../data/models/booking_models.dart';
import '../../domain/entities/booking_status.dart';
import '../providers/booking_providers.dart';

/// Trips.
///
/// Split into upcoming and past because the two are used for entirely different
/// things: upcoming is "where am I going and can I still change it", past is
/// "find me that invoice". A single reverse-chronological list serves neither.
class TripsScreen extends ConsumerWidget {
  const TripsScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final state = ref.watch(bookingsListProvider);
    final notifier = ref.read(bookingsListProvider.notifier);
    final upcoming = ref.watch(upcomingTripsProvider);
    final past = ref.watch(pastTripsProvider);

    return DefaultTabController(
      length: 2,
      child: Scaffold(
        appBar: AppBar(
          title: const Text('My trips'),
          bottom: TabBar(
            tabs: [
              Tab(text: 'Upcoming${upcoming.isEmpty ? '' : ' (${upcoming.length})'}'),
              Tab(text: 'Past${past.isEmpty ? '' : ' (${past.length})'}'),
            ],
          ),
        ),
        body: Column(
          children: [
            if (state.isStale)
              StaleDataBanner(cachedAt: state.cachedAt, onRefresh: notifier.refresh),
            Expanded(
              child: TabBarView(
                children: [
                  _TripList(
                    state: state.copyWith(items: upcoming),
                    notifier: notifier,
                    emptyTitle: 'No trips booked yet',
                    emptyDescription:
                        'When you book a stay it will appear here, with your '
                        'confirmation and invoice.',
                  ),
                  _TripList(
                    state: state.copyWith(items: past),
                    notifier: notifier,
                    emptyTitle: 'No past trips yet',
                    emptyDescription:
                        'Completed stays and their invoices show up here.',
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _TripList extends StatelessWidget {
  const _TripList({
    required this.state,
    required this.notifier,
    required this.emptyTitle,
    required this.emptyDescription,
  });

  final PagedState<BookingDto> state;
  final BookingsList notifier;
  final String emptyTitle;
  final String emptyDescription;

  @override
  Widget build(BuildContext context) => PagedListView<BookingDto>(
        state: state,
        onLoadMore: notifier.loadMore,
        onRefresh: notifier.refresh,
        onRetry: notifier.loadMore,
        emptyTitle: emptyTitle,
        emptyDescription: emptyDescription,
        emptyIcon: Icons.card_travel_outlined,
        emptyAction: FilledButton(
          onPressed: () => context.go(Routes.search),
          child: const Text('Find a stay'),
        ),
        itemBuilder: (context, booking, _) => TripCard(booking: booking),
      );
}

class TripCard extends StatelessWidget {
  const TripCard({required this.booking, super.key});

  final BookingDto booking;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final status = BookingStatus.parse(booking.status);

    return Card(
      clipBehavior: Clip.antiAlias,
      child: InkWell(
        onTap: () => context.push(Routes.trip(booking.id)),
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          booking.propertyName,
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                          style: theme.textTheme.titleMedium
                              ?.copyWith(fontWeight: FontWeight.w600),
                        ),
                        Text(
                          '${formatStay(booking.checkIn, booking.checkOut)} · '
                          '${booking.nights} night${booking.nights == 1 ? '' : 's'}',
                          style: theme.textTheme.bodySmall?.copyWith(
                            color: theme.colorScheme.onSurfaceVariant,
                          ),
                        ),
                        Text(
                          booking.reference,
                          style: theme.textTheme.labelSmall?.copyWith(
                            color: theme.colorScheme.outline,
                            fontFamily: 'monospace',
                          ),
                        ),
                      ],
                    ),
                  ),
                  Column(
                    crossAxisAlignment: CrossAxisAlignment.end,
                    children: [
                      StatusChip(status: status),
                      Gap.xs,
                      Text(
                        formatMinor(booking.totalMinor, booking.currency,
                            compact: true),
                        style: theme.textTheme.titleSmall
                            ?.copyWith(fontWeight: FontWeight.w700),
                      ),
                    ],
                  ),
                ],
              ),
              if (status.isPayable) ...[
                Gap.sm,
                Container(
                  padding: const EdgeInsets.all(10),
                  decoration: BoxDecoration(
                    color: theme.colorScheme.warningContainer,
                    borderRadius: BorderRadius.circular(10),
                  ),
                  child: Row(
                    children: [
                      Expanded(
                        child: Text(
                          'Payment pending — your rooms are held, but not for long.',
                          style: theme.textTheme.bodySmall
                              ?.copyWith(color: theme.colorScheme.warning),
                        ),
                      ),
                      FilledButton.tonal(
                        onPressed: () =>
                            context.push(Routes.checkout(booking.id)),
                        child: const Text('Pay now'),
                      ),
                    ],
                  ),
                ),
              ],
            ],
          ),
        ),
      ),
    );
  }
}

class StatusChip extends StatelessWidget {
  const StatusChip({required this.status, super.key});

  final BookingStatus status;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final (background, foreground) = switch (status) {
      BookingStatus.confirmed ||
      BookingStatus.completed =>
        (scheme.successContainer, scheme.success),
      BookingStatus.pendingPayment ||
      BookingStatus.pendingApproval =>
        (scheme.warningContainer, scheme.warning),
      BookingStatus.inStay => (scheme.primaryContainer, scheme.onPrimaryContainer),
      BookingStatus.cancelled ||
      BookingStatus.expired ||
      BookingStatus.rejected ||
      BookingStatus.noShow =>
        (scheme.errorContainer, scheme.onErrorContainer),
    };

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
      decoration: BoxDecoration(
        color: background,
        borderRadius: BorderRadius.circular(20),
      ),
      child: Text(
        status.label,
        style: Theme.of(context)
            .textTheme
            .labelSmall
            ?.copyWith(color: foreground, fontWeight: FontWeight.w600),
      ),
    );
  }
}
