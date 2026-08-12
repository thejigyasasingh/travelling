import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../../core/error/failure.dart';
import '../../../../core/network/result.dart';
import '../../../../core/providers/repository_providers.dart';
import '../../../../core/router/app_router.dart';
import '../../../../core/theme/app_theme.dart';
import '../../../../core/utils/dates.dart';
import '../../../../core/utils/money.dart';
import '../../../../shared/widgets/app_shell.dart';
import '../../../../shared/widgets/state_views.dart';
import '../../../catalog/domain/entities/cancellation_policy.dart';
import '../../data/models/booking_models.dart';
import '../../domain/entities/booking_status.dart';
import '../providers/booking_providers.dart';
import 'trips_screen.dart';

/// One trip: the details, and cancellation.
///
/// Cancellation shows the **server's** refund preview, itemised, before asking
/// for confirmation. Guessing the refund on the client and being wrong is a
/// dispute; showing a number the guest agreed to before pressing the button is
/// how that conversation is avoided entirely.
class TripDetailScreen extends ConsumerWidget {
  const TripDetailScreen({required this.bookingId, super.key});

  final String bookingId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final booking = ref.watch(bookingDetailProvider(bookingId));

    return Scaffold(
      appBar: AppBar(
        title: const Text('Your trip'),
        leading: IconButton(
          icon: const Icon(Icons.arrow_back),
          onPressed: () => popOrGo(context, Routes.trips),
        ),
      ),
      body: booking.when(
        loading: () => const LoadingView(),
        error: (error, _) => ErrorView(
          failure: error is Failure ? error : const Failure.unexpected(),
          onRetry: () => ref.invalidate(bookingDetailProvider(bookingId)),
        ),
        data: (data) => _TripDetail(booking: data),
      ),
    );
  }
}

class _TripDetail extends ConsumerWidget {
  const _TripDetail({required this.booking});

  final BookingDto booking;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final theme = Theme.of(context);
    final status = BookingStatus.parse(booking.status);
    final policy = cancellationPolicy(booking.cancellationPolicy);

    return RefreshIndicator(
      onRefresh: () =>
          ref.read(bookingDetailProvider(booking.id).notifier).refresh(),
      child: ListView(
        padding: const EdgeInsets.fromLTRB(16, 16, 16, 32),
        children: [
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Expanded(
                child: Text(
                  booking.propertyName,
                  style: theme.textTheme.headlineSmall
                      ?.copyWith(fontWeight: FontWeight.w700),
                ),
              ),
              StatusChip(status: status),
            ],
          ),
          Gap.xs,
          Text(status.hint,
              style: theme.textTheme.bodyMedium
                  ?.copyWith(color: theme.colorScheme.onSurfaceVariant)),

          if (status.isPayable) ...[
            Gap.md,
            Container(
              padding: const EdgeInsets.all(14),
              decoration: BoxDecoration(
                color: theme.colorScheme.warningContainer,
                borderRadius: BorderRadius.circular(12),
              ),
              child: Row(
                children: [
                  Expanded(
                    child: Text(
                      'This booking is not paid for yet.',
                      style: theme.textTheme.bodyMedium
                          ?.copyWith(color: theme.colorScheme.warning),
                    ),
                  ),
                  FilledButton(
                    onPressed: () => context.push(Routes.checkout(booking.id)),
                    child: const Text('Pay now'),
                  ),
                ],
              ),
            ),
          ],

          Gap.lg,
          _DetailCard(
            title: 'Your stay',
            rows: [
              ('Reference', booking.reference),
              ('Dates',
                  '${formatStay(booking.checkIn, booking.checkOut)} · ${booking.nights} night${booking.nights == 1 ? '' : 's'}'),
              ('Room', booking.roomTypeName),
              ('Guests',
                  '${booking.adults} adult${booking.adults == 1 ? '' : 's'}'
                  '${booking.children > 0 ? ', ${booking.children} children' : ''}'
                  ' · ${booking.rooms} room${booking.rooms == 1 ? '' : 's'}'),
              ('Lead guest', booking.guestName),
              ('Contact', '${booking.guestEmail}\n${booking.guestPhone}'),
              if (booking.propertyAddress != null)
                ('Address', booking.propertyAddress!),
              if (booking.confirmedAt != null)
                ('Confirmed', formatDateTime(booking.confirmedAt)),
              if (booking.invoiceNumber != null)
                ('Invoice', booking.invoiceNumber!),
            ],
          ),

          Gap.md,
          _PaidCard(booking: booking),

          if (booking.refund != null) ...[
            Gap.md,
            _RefundCard(refund: booking.refund!),
          ],

          Gap.lg,
          if (status.canRequestCancellation)
            OutlinedButton(
              onPressed: () => _confirmCancellation(context, ref, booking),
              child: const Text('Cancel this booking'),
            ),

          Gap.md,
          Text(
            '${policy.label} cancellation — ${policy.detail} $refundFootnote',
            style: theme.textTheme.bodySmall
                ?.copyWith(color: theme.colorScheme.onSurfaceVariant),
          ),
        ],
      ),
    );
  }

  Future<void> _confirmCancellation(
    BuildContext context,
    WidgetRef ref,
    BookingDto booking,
  ) async {
    final confirmed = await showModalBottomSheet<bool>(
      context: context,
      isScrollControlled: true,
      showDragHandle: true,
      builder: (_) => _CancellationSheet(booking: booking),
    );

    if (confirmed != true || !context.mounted) return;

    final result = await ref
        .read(bookingRepositoryProvider)
        .cancel(booking.id, reason: null);

    if (!context.mounted) return;

    switch (result) {
      case Ok<BookingDto>():
        ref.invalidate(bookingDetailProvider(booking.id));
        ref.invalidate(bookingsListProvider);
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Booking cancelled. Your refund is on its way.')),
        );
      case Err<BookingDto>(:final failure):
        ScaffoldMessenger.of(context)
            .showSnackBar(SnackBar(content: Text(failure.message)));
    }
  }
}

/// The cancellation sheet, showing exactly what comes back.
class _CancellationSheet extends ConsumerWidget {
  const _CancellationSheet({required this.booking});

  final BookingDto booking;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final theme = Theme.of(context);
    final preview = ref.watch(refundPreviewProvider(booking.id));

    return Padding(
      padding: const EdgeInsets.fromLTRB(20, 8, 20, 24),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('Cancel this booking?', style: theme.textTheme.titleLarge),
          Gap.xs,
          Text(
            'Here is exactly what comes back to you, under the policy you '
            'booked under.',
            style: theme.textTheme.bodySmall
                ?.copyWith(color: theme.colorScheme.onSurfaceVariant),
          ),
          Gap.md,
          preview.when(
            loading: () => const Padding(
              padding: EdgeInsets.symmetric(vertical: 24),
              child: Center(child: CircularProgressIndicator()),
            ),
            error: (error, _) => Text(
              error is Failure ? error.message : 'Could not calculate the refund.',
              style: theme.textTheme.bodyMedium
                  ?.copyWith(color: theme.colorScheme.error),
            ),
            data: (data) => Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                _Row('Accommodation',
                    formatMinor(data.accommodationMinor, data.currency)),
                if (data.cleaningFeeMinor > 0)
                  _Row('Cleaning fee',
                      formatMinor(data.cleaningFeeMinor, data.currency)),
                _Row('Taxes', formatMinor(data.taxMinor, data.currency)),
                const Divider(),
                _Row(
                  'You get back',
                  formatMinor(data.totalMinor, data.currency),
                  bold: true,
                ),
                Gap.sm,
                Container(
                  padding: const EdgeInsets.all(12),
                  decoration: BoxDecoration(
                    color: theme.colorScheme.surfaceContainerHighest,
                    borderRadius: BorderRadius.circular(10),
                  ),
                  child: Text(
                    '${data.reason} (${data.appliedPercent} of the room rate, '
                    'with ${data.hoursBeforeCheckIn.round()} hours to check-in). '
                    '$refundFootnote',
                    style: theme.textTheme.bodySmall,
                  ),
                ),
              ],
            ),
          ),
          Gap.lg,
          Row(
            children: [
              Expanded(
                child: OutlinedButton(
                  onPressed: () => Navigator.of(context).pop(false),
                  child: const Text('Keep my booking'),
                ),
              ),
              Gap.sm,
              Expanded(
                child: FilledButton(
                  style: FilledButton.styleFrom(
                    backgroundColor: theme.colorScheme.error,
                  ),
                  onPressed: preview.value?.cancellable == false
                      ? null
                      : () => Navigator.of(context).pop(true),
                  child: const Text('Cancel booking'),
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }
}

class _PaidCard extends StatelessWidget {
  const _PaidCard({required this.booking});

  final BookingDto booking;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('What you paid',
                style: theme.textTheme.titleMedium
                    ?.copyWith(fontWeight: FontWeight.w600)),
            Gap.sm,
            _Row('Accommodation',
                formatMinor(booking.accommodationMinor, booking.currency)),
            if (booking.cleaningFeeMinor > 0)
              _Row('Cleaning fee',
                  formatMinor(booking.cleaningFeeMinor, booking.currency)),
            _Row('Taxes', formatMinor(booking.taxMinor, booking.currency)),
            const Divider(),
            _Row('Total', formatMinor(booking.totalMinor, booking.currency),
                bold: true),
            if (booking.nightlyRates.isNotEmpty) ...[
              Gap.sm,
              ExpansionTile(
                tilePadding: EdgeInsets.zero,
                title: Text('Night-by-night rates',
                    style: theme.textTheme.bodyMedium),
                children: [
                  for (final night in booking.nightlyRates)
                    _Row(formatDate(night.date),
                        formatMinor(night.amountMinor, booking.currency)),
                ],
              ),
            ],
          ],
        ),
      ),
    );
  }
}

class _RefundCard extends StatelessWidget {
  const _RefundCard({required this.refund});

  final BookingRefundDto refund;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('Refund',
                style: theme.textTheme.titleMedium
                    ?.copyWith(fontWeight: FontWeight.w600)),
            Gap.sm,
            Text(
              refund.status == 'completed'
                  ? '${formatMinor(refund.amountMinor, refund.currency)} was refunded on '
                      '${formatDateTime(refund.completedAt)}.'
                  : '${formatMinor(refund.amountMinor, refund.currency)} is being processed. '
                      'Bank refunds usually take 5–7 working days to appear.',
              style: theme.textTheme.bodyMedium,
            ),
          ],
        ),
      ),
    );
  }
}

class _DetailCard extends StatelessWidget {
  const _DetailCard({required this.title, required this.rows});

  final String title;
  final List<(String, String)> rows;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(title,
                style: theme.textTheme.titleMedium
                    ?.copyWith(fontWeight: FontWeight.w600)),
            Gap.sm,
            for (final (label, value) in rows)
              Padding(
                padding: const EdgeInsets.only(bottom: 8),
                child: Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Expanded(
                      child: Text(label,
                          style: theme.textTheme.bodySmall?.copyWith(
                            color: theme.colorScheme.onSurfaceVariant,
                          )),
                    ),
                    Expanded(
                      flex: 2,
                      child: Text(value,
                          textAlign: TextAlign.right,
                          style: theme.textTheme.bodyMedium),
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

class _Row extends StatelessWidget {
  const _Row(this.label, this.value, {this.bold = false});

  final String label;
  final String value;
  final bool bold;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final style = bold
        ? theme.textTheme.bodyLarge?.copyWith(fontWeight: FontWeight.w700)
        : theme.textTheme.bodyMedium;
    return Padding(
      padding: const EdgeInsets.only(bottom: 6),
      child: Row(
        children: [
          Expanded(child: Text(label, style: style)),
          Text(value, style: style),
        ],
      ),
    );
  }
}
