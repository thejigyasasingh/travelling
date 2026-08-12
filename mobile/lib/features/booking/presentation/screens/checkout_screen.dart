import 'dart:async';

import 'package:clock/clock.dart';
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
import '../../data/models/booking_models.dart';
import '../../domain/entities/booking_status.dart';
import '../providers/booking_providers.dart';

/// Checkout.
///
/// **The client never decides that a payment succeeded.** The gateway hands the
/// app a signature; only the server, which holds the secret, can say whether it
/// is genuine. Until it does, the screen says "confirming", not "paid".
///
/// **A verification failure is not a payment failure.** If the money moved and
/// the verify call failed, the webhook still confirms the booking server-side.
/// So the guest is sent to the booking — which polls — rather than being told
/// something went wrong and invited to pay a second time.
///
/// The Razorpay SDK is not wired in here: adding it means a native dependency
/// and a merchant account, and the payment step is stubbed at the point where
/// `openGateway` would run. Everything around it — order creation, the hold
/// countdown, verification, the error paths — is real and talks to the API.
class CheckoutScreen extends ConsumerStatefulWidget {
  const CheckoutScreen({required this.bookingId, super.key});

  final String bookingId;

  @override
  ConsumerState<CheckoutScreen> createState() => _CheckoutScreenState();
}

class _CheckoutScreenState extends ConsumerState<CheckoutScreen> {
  bool _busy = false;
  Failure? _error;

  Future<void> _pay(BookingDto booking) async {
    setState(() {
      _busy = true;
      _error = null;
    });

    final order = await ref.read(bookingRepositoryProvider).createOrder(booking.id);

    if (!mounted) return;

    switch (order) {
      case Err<CheckoutSessionDto>(:final failure):
        setState(() {
          _busy = false;
          _error = failure;
        });
      case Ok<CheckoutSessionDto>(:final value):
        // ── where the Razorpay SDK would open ──────────────────────────────
        // `Razorpay().open({...key_id, order_id, amount...})` and then, in its
        // success handler, `verifyPayment(...)` with the three fields it
        // returns. The handler below is what runs on that callback.
        await _showGatewayPlaceholder(value);
    }
  }

  Future<void> _showGatewayPlaceholder(CheckoutSessionDto session) async {
    setState(() => _busy = false);
    if (!mounted) return;

    await showDialog<void>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Payment gateway'),
        content: Text(
          'The Razorpay checkout sheet opens here for order '
          '${session.gatewayOrderId} (${formatMinor(session.amountMinor, session.currency)}).\n\n'
          'The SDK is not bundled in this build — it needs a merchant account '
          'and a native dependency. Order creation, the hold countdown and '
          'server-side verification are all live.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(context).pop(),
            child: const Text('Close'),
          ),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final booking = ref.watch(bookingDetailProvider(widget.bookingId));

    // A booking that is already paid must never show a pay button — this covers
    // the back-button case and the webhook confirming while the guest sits here.
    ref.listen(bookingDetailProvider(widget.bookingId), (_, next) {
      final status = next.value?.status;
      if (status != null && !BookingStatus.parse(status).isPayable && mounted) {
        context.pushReplacement(Routes.trip(widget.bookingId));
      }
    });

    return Scaffold(
      appBar: AppBar(
        title: const Text('Confirm and pay'),
        leading: IconButton(
          icon: const Icon(Icons.close_rounded),
          onPressed: () => popOrGo(context, Routes.trips),
        ),
      ),
      body: booking.when(
        loading: () => const LoadingView(label: 'Loading your booking'),
        error: (error, _) => ErrorView(
          failure: error is Failure ? error : const Failure.unexpected(),
          onRetry: () => ref.invalidate(bookingDetailProvider(widget.bookingId)),
        ),
        data: (data) {
          final expired = data.status == BookingStatus.expired.wire ||
              (data.holdExpiresIn ?? 1) <= 0;

          return ListView(
            padding: const EdgeInsets.fromLTRB(16, 16, 16, 32),
            children: [
              Text('Booking ${data.reference}',
                  style: theme.textTheme.bodySmall?.copyWith(
                    color: theme.colorScheme.onSurfaceVariant,
                  )),
              Gap.sm,

              if (!expired && data.holdExpiresIn != null)
                HoldCountdown(
                  seconds: data.holdExpiresIn!,
                  onExpire: () =>
                      ref.invalidate(bookingDetailProvider(widget.bookingId)),
                ),

              if (expired) _ExpiredNotice(propertyId: data.propertyId),

              Gap.md,
              Card(
                child: Padding(
                  padding: const EdgeInsets.all(16),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(data.propertyName,
                          style: theme.textTheme.titleMedium
                              ?.copyWith(fontWeight: FontWeight.w600)),
                      Text(data.roomTypeName,
                          style: theme.textTheme.bodySmall?.copyWith(
                            color: theme.colorScheme.onSurfaceVariant,
                          )),
                      Gap.sm,
                      Text(
                        '${formatStay(data.checkIn, data.checkOut)} · '
                        '${data.nights} night${data.nights == 1 ? '' : 's'}',
                        style: theme.textTheme.bodyMedium,
                      ),
                      Text(
                        '${data.adults + data.children} guests in '
                        '${data.rooms} room${data.rooms == 1 ? '' : 's'}',
                        style: theme.textTheme.bodyMedium,
                      ),
                    ],
                  ),
                ),
              ),

              Gap.md,
              _PriceRows(booking: data),

              if (_error != null) ...[
                Gap.md,
                _PaymentError(failure: _error!),
              ],

              Gap.lg,
              FilledButton(
                onPressed: _busy || expired ? null : () => _pay(data),
                child: _busy
                    ? const SizedBox(
                        width: 18,
                        height: 18,
                        child: CircularProgressIndicator(strokeWidth: 2),
                      )
                    : Text('Pay ${formatMinor(data.totalMinor, data.currency)}'),
              ),
              Gap.sm,
              Center(
                child: Text(
                  'Card details are entered in the gateway’s own sheet and '
                  'never reach our servers.',
                  textAlign: TextAlign.center,
                  style: theme.textTheme.bodySmall
                      ?.copyWith(color: theme.colorScheme.onSurfaceVariant),
                ),
              ),
            ],
          );
        },
      ),
    );
  }
}

/// The hold countdown.
///
/// Counts down from a *duration* the server sent, anchored once — not to a
/// server timestamp, which a device with a wrong clock would render as
/// nonsense. Recomputed from the deadline each tick rather than decremented,
/// because a backgrounded app has its timers throttled and a subtract-one
/// counter comes back minutes behind reality.
class HoldCountdown extends StatefulWidget {
  const HoldCountdown({required this.seconds, super.key, this.onExpire});

  final int seconds;
  final VoidCallback? onExpire;

  @override
  State<HoldCountdown> createState() => _HoldCountdownState();
}

class _HoldCountdownState extends State<HoldCountdown> {
  late DateTime _deadline;
  late int _remaining;
  Timer? _timer;

  @override
  void initState() {
    super.initState();
    _anchor();
  }

  @override
  void didUpdateWidget(HoldCountdown oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.seconds != widget.seconds) _anchor();
  }

  void _anchor() {
    // `clock.now()`, not `DateTime.now()`. Identical in production —
    // `package:clock` delegates to the real clock unless something has
    // overridden it — and the difference is that the countdown arithmetic
    // becomes testable. A widget test's `pump(Duration)` advances timers but
    // not the calendar, so a hardcoded `DateTime.now()` makes every tick
    // return the same value and the drift behaviour unobservable.
    _deadline = clock.now().add(Duration(seconds: widget.seconds));
    _remaining = widget.seconds;
    _timer?.cancel();
    _timer = Timer.periodic(const Duration(seconds: 1), (_) {
      final left = _deadline.difference(clock.now()).inSeconds;
      if (!mounted) return;
      setState(() => _remaining = left < 0 ? 0 : left);
      if (left <= 0) {
        _timer?.cancel();
        widget.onExpire?.call();
      }
    });
  }

  @override
  void dispose() {
    _timer?.cancel();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final urgent = _remaining <= 120;

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
      decoration: BoxDecoration(
        color: urgent
            ? theme.colorScheme.errorContainer
            : theme.colorScheme.warningContainer,
        borderRadius: BorderRadius.circular(12),
      ),
      child: Row(
        children: [
          Icon(Icons.timer_outlined,
              size: 18,
              color: urgent ? theme.colorScheme.error : theme.colorScheme.warning),
          Gap.sm,
          Expanded(
            child: Text(
              _remaining > 0
                  ? 'Your rooms are held for ${formatCountdown(_remaining)}'
                  : 'This hold has expired. The rooms have been released.',
              style: theme.textTheme.bodyMedium?.copyWith(
                color: urgent ? theme.colorScheme.error : theme.colorScheme.warning,
                fontWeight: FontWeight.w600,
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _ExpiredNotice extends StatelessWidget {
  const _ExpiredNotice({required this.propertyId});

  final String propertyId;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: theme.colorScheme.errorContainer,
        borderRadius: BorderRadius.circular(12),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('This hold has expired',
              style: theme.textTheme.titleSmall?.copyWith(
                color: theme.colorScheme.onErrorContainer,
                fontWeight: FontWeight.w600,
              )),
          Gap.xs,
          Text(
            'The rooms went back on the calendar. Nothing was charged — the '
            'dates may still be free.',
            style: theme.textTheme.bodySmall
                ?.copyWith(color: theme.colorScheme.onErrorContainer),
          ),
          Gap.sm,
          OutlinedButton(
            onPressed: () => context.go(Routes.property(propertyId)),
            child: const Text('Check these dates again'),
          ),
        ],
      ),
    );
  }
}

class _PaymentError extends StatelessWidget {
  const _PaymentError({required this.failure});

  final Failure failure;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final disabled = failure.hasCode(ApiErrorCode.paymentsDisabled) ||
        failure.hasCode(ApiErrorCode.gatewayError);

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
            disabled
                ? 'Payments are unavailable right now'
                : 'That payment did not go through',
            style: theme.textTheme.titleSmall?.copyWith(
              color: theme.colorScheme.onErrorContainer,
              fontWeight: FontWeight.w600,
            ),
          ),
          Gap.xs,
          Text(
            '${failure.message}\nNothing has been charged and your booking is '
            'still held.',
            style: theme.textTheme.bodySmall
                ?.copyWith(color: theme.colorScheme.onErrorContainer),
          ),
        ],
      ),
    );
  }
}

class _PriceRows extends StatelessWidget {
  const _PriceRows({required this.booking});

  final BookingDto booking;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    Widget row(String label, int minor, {bool bold = false}) => Padding(
          padding: const EdgeInsets.only(bottom: 6),
          child: Row(
            children: [
              Expanded(
                child: Text(label,
                    style: bold
                        ? theme.textTheme.bodyLarge
                            ?.copyWith(fontWeight: FontWeight.w700)
                        : theme.textTheme.bodyMedium),
              ),
              Text(formatMinor(minor, booking.currency),
                  style: bold
                      ? theme.textTheme.bodyLarge
                          ?.copyWith(fontWeight: FontWeight.w700)
                      : theme.textTheme.bodyMedium),
            ],
          ),
        );

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          children: [
            row('Accommodation', booking.accommodationMinor),
            if (booking.extraGuestMinor > 0)
              row('Extra guests', booking.extraGuestMinor),
            if (booking.cleaningFeeMinor > 0)
              row('Cleaning fee', booking.cleaningFeeMinor),
            row('Taxes', booking.taxMinor),
            const Divider(),
            row('Total', booking.totalMinor, bold: true),
          ],
        ),
      ),
    );
  }
}
