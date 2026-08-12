/// The booking status machine, as a guest experiences it.
library;

enum BookingStatus {
  pendingPayment('pending_payment'),
  pendingApproval('pending_approval'),
  confirmed('confirmed'),
  inStay('in_stay'),
  completed('completed'),
  cancelled('cancelled'),
  expired('expired'),
  rejected('rejected'),
  noShow('no_show');

  const BookingStatus(this.wire);

  final String wire;

  static BookingStatus parse(String wire) => BookingStatus.values.firstWhere(
        (s) => s.wire == wire,
        // An unknown status from a newer server must not crash an older app.
        // Treating it as completed is the safest read-only interpretation: it
        // offers no actions rather than the wrong ones.
        orElse: () => BookingStatus.completed,
      );

  String get label => switch (this) {
        BookingStatus.pendingPayment => 'Payment pending',
        BookingStatus.pendingApproval => 'Awaiting host',
        BookingStatus.confirmed => 'Confirmed',
        BookingStatus.inStay => 'In stay',
        BookingStatus.completed => 'Completed',
        BookingStatus.cancelled => 'Cancelled',
        BookingStatus.expired => 'Expired',
        BookingStatus.rejected => 'Declined',
        BookingStatus.noShow => 'No show',
      };

  String get hint => switch (this) {
        BookingStatus.pendingPayment =>
          'Your rooms are held. Pay to confirm before the hold lapses.',
        BookingStatus.pendingApproval =>
          'The host has your request. You will not be charged until they accept.',
        BookingStatus.confirmed => 'Your stay is booked.',
        BookingStatus.inStay => 'Enjoy your stay.',
        BookingStatus.completed => 'This stay has ended.',
        BookingStatus.cancelled => 'This booking was cancelled.',
        BookingStatus.expired =>
          'The payment window closed and the rooms were released.',
        BookingStatus.rejected => 'The host could not take this booking.',
        BookingStatus.noShow => 'Recorded as a no-show by the property.',
      };

  /// Money is owed and the rooms are held: checkout is reachable.
  bool get isPayable => this == BookingStatus.pendingPayment;

  bool get isUpcoming =>
      this == BookingStatus.confirmed || this == BookingStatus.pendingApproval;

  bool get isActive =>
      isUpcoming || this == BookingStatus.inStay || isPayable;

  /// Whether to *offer* cancellation. The authoritative answer — and the refund
  /// amount — comes from the server's preview; this only decides whether
  /// showing the button makes sense.
  bool get canRequestCancellation =>
      this == BookingStatus.confirmed ||
      this == BookingStatus.pendingApproval ||
      isPayable;
}
