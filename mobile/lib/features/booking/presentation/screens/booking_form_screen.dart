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
import '../../../auth/presentation/providers/auth_provider.dart';
import '../../../catalog/domain/entities/cancellation_policy.dart';
import '../../../catalog/presentation/providers/property_provider.dart';
import '../../../catalog/data/models/property_models.dart';
import '../../data/models/booking_models.dart';
import '../../domain/usecases/reserve_stay.dart';

/// Review and reserve.
///
/// The **idempotency key is minted once, in `initState`** — not per tap. A
/// double-tapped "Reserve", or a retry after a flaky connection, sends the same
/// key and gets the same booking back. A key generated inside the handler would
/// defeat the entire mechanism and hold two rooms.
class BookingFormScreen extends ConsumerStatefulWidget {
  const BookingFormScreen({
    required this.propertyId,
    required this.roomTypeId,
    required this.checkIn,
    required this.checkOut,
    required this.adults,
    required this.children,
    required this.rooms,
    super.key,
  });

  final String propertyId;
  final String roomTypeId;
  final String checkIn;
  final String checkOut;
  final int adults;
  final int children;
  final int rooms;

  @override
  ConsumerState<BookingFormScreen> createState() => _BookingFormScreenState();
}

class _BookingFormScreenState extends ConsumerState<BookingFormScreen> {
  final _formKey = GlobalKey<FormState>();
  late final String _idempotencyKey;

  late final TextEditingController _name;
  late final TextEditingController _email;
  late final TextEditingController _phone;
  final _requests = TextEditingController();

  bool _submitting = false;
  Failure? _error;

  @override
  void initState() {
    super.initState();
    _idempotencyKey = ReservationRequest.newIdempotencyKey();

    final user = ref.read(currentUserProvider);
    _name = TextEditingController(text: user?.fullName ?? '');
    _email = TextEditingController(text: user?.email ?? '');
    _phone = TextEditingController(text: user?.phone ?? '');
  }

  @override
  void dispose() {
    _name.dispose();
    _email.dispose();
    _phone.dispose();
    _requests.dispose();
    super.dispose();
  }

  Future<void> _submit(int quotedTotalMinor) async {
    if (!(_formKey.currentState?.validate() ?? false)) return;

    setState(() {
      _submitting = true;
      _error = null;
    });

    final result = await ref.read(reserveStayProvider).call(
          ReservationRequest(
            propertyId: widget.propertyId,
            roomTypeId: widget.roomTypeId,
            checkIn: widget.checkIn,
            checkOut: widget.checkOut,
            adults: widget.adults,
            children: widget.children,
            infants: 0,
            rooms: widget.rooms,
            guestName: _name.text.trim(),
            guestEmail: _email.text.trim(),
            guestPhone: _phone.text.trim(),
            quotedTotalMinor: quotedTotalMinor,
            idempotencyKey: _idempotencyKey,
            specialRequests:
                _requests.text.trim().isEmpty ? null : _requests.text.trim(),
          ),
        );

    if (!mounted) return;

    switch (result) {
      case Ok<BookingDto>(:final value):
        // The booking now holds real inventory on a timer, so go straight to
        // payment rather than to a screen someone might wander off from.
        context.pushReplacement(Routes.checkout(value.id));
      case Err<BookingDto>(:final failure):
        setState(() {
          _submitting = false;
          _error = failure;
        });
    }
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final property = ref.watch(propertyProvider(widget.propertyId));
    final nights = isValidStay(widget.checkIn, widget.checkOut)
        ? nightsBetween(widget.checkIn, widget.checkOut)
        : 0;

    return Scaffold(
      appBar: AppBar(
        title: const Text('Review and reserve'),
        leading: IconButton(
          icon: const Icon(Icons.close_rounded),
          onPressed: () => popOrGo(context, Routes.search),
        ),
      ),
      body: property.when(
        loading: () => const LoadingIndicator(),
        error: (error, _) => Center(
          child: Text(error is Failure ? error.message : 'Could not load'),
        ),
        data: (data) {
          final room = data.roomTypes.firstWhere(
            (r) => r.id == widget.roomTypeId,
            orElse: () => const RoomTypeDto(id: '', name: 'Room'),
          );
          final quote = ref.watch(
            stayQuoteProvider(widget.propertyId, room.minNights),
          );
          final policy = cancellationPolicy(data.cancellationPolicy);

          return Form(
            key: _formKey,
            child: ListView(
              padding: const EdgeInsets.fromLTRB(16, 16, 16, 32),
              children: [
                _SummaryCard(
                  title: data.name,
                  subtitle: room.name,
                  rows: [
                    ('Dates',
                        '${formatStay(widget.checkIn, widget.checkOut)} · $nights night${nights == 1 ? '' : 's'}'),
                    ('Guests',
                        '${widget.adults + widget.children} in ${widget.rooms} room${widget.rooms == 1 ? '' : 's'}'),
                  ],
                ),
                Gap.lg,

                Text('Guest details',
                    style: theme.textTheme.titleMedium
                        ?.copyWith(fontWeight: FontWeight.w600)),
                Gap.xs,
                Text(
                  'These go to the property. The name should match the ID the '
                  'guest checks in with.',
                  style: theme.textTheme.bodySmall
                      ?.copyWith(color: theme.colorScheme.onSurfaceVariant),
                ),
                Gap.md,

                TextFormField(
                  controller: _name,
                  textCapitalization: TextCapitalization.words,
                  decoration: const InputDecoration(labelText: 'Full name'),
                  validator: (value) => (value?.trim().isEmpty ?? true)
                      ? 'Please enter the lead guest’s name'
                      : null,
                ),
                Gap.md,
                TextFormField(
                  controller: _email,
                  keyboardType: TextInputType.emailAddress,
                  decoration: const InputDecoration(
                    labelText: 'Email',
                    helperText: 'Your confirmation and invoice go here.',
                  ),
                  validator: (value) {
                    final text = value?.trim() ?? '';
                    // Deliberately loose. Strict email regexes reject valid
                    // addresses, and the real check is whether the mail arrives.
                    if (!text.contains('@') || !text.contains('.')) {
                      return 'Please enter a valid email address';
                    }
                    return null;
                  },
                ),
                Gap.md,
                TextFormField(
                  controller: _phone,
                  keyboardType: TextInputType.phone,
                  decoration: const InputDecoration(
                    labelText: 'Phone',
                    hintText: '+91 98765 43210',
                    helperText: 'The property may call about your arrival.',
                  ),
                  validator: (value) =>
                      (value?.trim().length ?? 0) < 8 ? 'Please enter a phone number' : null,
                ),
                Gap.md,
                TextFormField(
                  controller: _requests,
                  maxLines: 3,
                  maxLength: 500,
                  decoration: const InputDecoration(
                    labelText: 'Anything the host should know?',
                    helperText: 'Requests are passed on, not guaranteed.',
                  ),
                ),
                Gap.md,

                quote.when(
                  loading: () => const LinearProgressIndicator(),
                  error: (error, _) => _ErrorNote(
                    failure: error is Failure ? error : const Failure.unexpected(),
                  ),
                  data: (data) => data == null
                      ? const SizedBox.shrink()
                      : _PriceBreakdown(quote: data, nights: nights),
                ),

                Gap.md,
                _PolicyNote(policy: policy),

                if (_error != null) ...[
                  Gap.md,
                  _ReservationError(
                    failure: _error!,
                    onRefreshPrice: () => ref.invalidate(
                      stayQuoteProvider(widget.propertyId, room.minNights),
                    ),
                  ),
                ],

                Gap.lg,
                FilledButton(
                  onPressed: _submitting || (quote.value?.isAvailable != true)
                      ? null
                      : () => _submit(quote.value!.totalMinor),
                  child: _submitting
                      ? const SizedBox(
                          width: 18,
                          height: 18,
                          child: CircularProgressIndicator(strokeWidth: 2),
                        )
                      : const Text('Reserve and pay'),
                ),
                Gap.sm,
                Center(
                  child: Text(
                    'Reserving holds your rooms while you pay.',
                    style: theme.textTheme.bodySmall
                        ?.copyWith(color: theme.colorScheme.onSurfaceVariant),
                  ),
                ),
              ],
            ),
          );
        },
      ),
    );
  }
}

/// A reservation failure, explained by what the guest can do about it.
class _ReservationError extends StatelessWidget {
  const _ReservationError({required this.failure, required this.onRefreshPrice});

  final Failure failure;
  final VoidCallback onRefreshPrice;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final problem = classifyReservationFailure(failure);

    final (title, body) = switch (problem) {
      ReservationProblem.priceChanged => (
          'The price changed while you were booking',
          'Rates for these dates were updated. Refresh to see the new total — '
              'you have not been charged.',
        ),
      ReservationProblem.soldOut => (
          'Those dates just went',
          'Someone else booked the last room. Try different dates or another room.',
        ),
      ReservationProblem.holdExpired => (
          'That hold expired',
          'The rooms went back on sale. Nothing was charged.',
        ),
      ReservationProblem.other => ('We could not hold that booking', failure.message),
    };

    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: theme.colorScheme.errorContainer,
        borderRadius: BorderRadius.circular(12),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            title,
            style: theme.textTheme.titleSmall?.copyWith(
              color: theme.colorScheme.onErrorContainer,
              fontWeight: FontWeight.w600,
            ),
          ),
          Gap.xs,
          Text(
            body,
            style: theme.textTheme.bodySmall
                ?.copyWith(color: theme.colorScheme.onErrorContainer),
          ),
          if (problem == ReservationProblem.priceChanged) ...[
            Gap.sm,
            OutlinedButton(
              onPressed: onRefreshPrice,
              child: const Text('Refresh price'),
            ),
          ],
        ],
      ),
    );
  }
}

class _PriceBreakdown extends StatelessWidget {
  const _PriceBreakdown({required this.quote, required this.nights});

  final QuoteLike quote;
  final int nights;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    Widget row(String label, int minor, {bool bold = false}) => Padding(
          padding: const EdgeInsets.only(bottom: 6),
          child: Row(
            children: [
              Expanded(
                child: Text(
                  label,
                  style: bold
                      ? theme.textTheme.bodyLarge
                          ?.copyWith(fontWeight: FontWeight.w700)
                      : theme.textTheme.bodyMedium,
                ),
              ),
              Text(
                formatMinor(minor, quote.currency),
                style: bold
                    ? theme.textTheme.bodyLarge
                        ?.copyWith(fontWeight: FontWeight.w700)
                    : theme.textTheme.bodyMedium,
              ),
            ],
          ),
        );

    return Column(
      children: [
        row(
          '${formatMinor(quote.averageNightlyMinor, quote.currency, compact: true)}'
          ' × $nights night${nights == 1 ? '' : 's'}',
          quote.accommodationMinor,
        ),
        if (quote.extraGuestMinor > 0) row('Extra guests', quote.extraGuestMinor),
        if (quote.cleaningFeeMinor > 0) row('Cleaning fee', quote.cleaningFeeMinor),
        row('Taxes', quote.taxMinor),
        const Divider(),
        row('Total', quote.totalMinor, bold: true),
      ],
    );
  }
}

/// The shape the breakdown needs, so it can render a quote *or* a booking —
/// the two carry the same numbers and should look identical to a guest.
typedef QuoteLike = QuoteDto;

class _SummaryCard extends StatelessWidget {
  const _SummaryCard({
    required this.title,
    required this.subtitle,
    required this.rows,
  });

  final String title;
  final String subtitle;
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
            Text(subtitle,
                style: theme.textTheme.bodySmall
                    ?.copyWith(color: theme.colorScheme.onSurfaceVariant)),
            Gap.sm,
            for (final (label, value) in rows)
              Padding(
                padding: const EdgeInsets.only(top: 6),
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
                      child: Text(
                        value,
                        textAlign: TextAlign.right,
                        style: theme.textTheme.bodyMedium
                            ?.copyWith(fontWeight: FontWeight.w500),
                      ),
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

class _PolicyNote extends StatelessWidget {
  const _PolicyNote({required this.policy});

  final PolicySummary policy;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: theme.colorScheme.surfaceContainerHighest,
        borderRadius: BorderRadius.circular(12),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('${policy.label} cancellation',
              style: theme.textTheme.bodyMedium
                  ?.copyWith(fontWeight: FontWeight.w600)),
          Gap.xs,
          Text(policy.detail, style: theme.textTheme.bodySmall),
          Gap.xs,
          Text(refundFootnote,
              style: theme.textTheme.bodySmall
                  ?.copyWith(color: theme.colorScheme.onSurfaceVariant)),
        ],
      ),
    );
  }
}

class _ErrorNote extends StatelessWidget {
  const _ErrorNote({required this.failure});

  final Failure failure;

  @override
  Widget build(BuildContext context) => Text(
        failure.message,
        style: Theme.of(context)
            .textTheme
            .bodySmall
            ?.copyWith(color: Theme.of(context).colorScheme.error),
      );
}

class LoadingIndicator extends StatelessWidget {
  const LoadingIndicator({super.key});

  @override
  Widget build(BuildContext context) =>
      const Center(child: CircularProgressIndicator());
}
