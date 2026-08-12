import 'package:freezed_annotation/freezed_annotation.dart';

part 'booking_models.freezed.dart';
part 'booking_models.g.dart';

@freezed
abstract class NightlyRateDto with _$NightlyRateDto {
  const factory NightlyRateDto({
    required String date,
    @JsonKey(name: 'amount_minor') @Default(0) int amountMinor,
  }) = _NightlyRateDto;

  factory NightlyRateDto.fromJson(Map<String, dynamic> json) =>
      _$NightlyRateDtoFromJson(json);
}

@freezed
abstract class BookingRefundDto with _$BookingRefundDto {
  const factory BookingRefundDto({
    @Default('pending') String status,
    @JsonKey(name: 'amount_minor') @Default(0) int amountMinor,
    @Default('INR') String currency,
    String? reason,
    @JsonKey(name: 'requested_at') String? requestedAt,
    @JsonKey(name: 'completed_at') String? completedAt,
  }) = _BookingRefundDto;

  factory BookingRefundDto.fromJson(Map<String, dynamic> json) =>
      _$BookingRefundDtoFromJson(json);
}

@freezed
abstract class BookingDto with _$BookingDto {
  const factory BookingDto({
    required String id,
    required String reference,
    required String status,
    @JsonKey(name: 'property_id') @Default('') String propertyId,
    @JsonKey(name: 'property_name') @Default('') String propertyName,
    @JsonKey(name: 'property_address') String? propertyAddress,
    @JsonKey(name: 'room_type_id') @Default('') String roomTypeId,
    @JsonKey(name: 'room_type_name') @Default('') String roomTypeName,
    @JsonKey(name: 'check_in') required String checkIn,
    @JsonKey(name: 'check_out') required String checkOut,
    @Default(0) int nights,
    @Default(1) int adults,
    @Default(0) int children,
    @Default(0) int infants,
    @Default(1) int rooms,
    @JsonKey(name: 'guest_name') @Default('') String guestName,
    @JsonKey(name: 'guest_email') @Default('') String guestEmail,
    @JsonKey(name: 'guest_phone') @Default('') String guestPhone,
    @JsonKey(name: 'special_requests') String? specialRequests,
    @JsonKey(name: 'accommodation_minor') @Default(0) int accommodationMinor,
    @JsonKey(name: 'extra_guest_minor') @Default(0) int extraGuestMinor,
    @JsonKey(name: 'cleaning_fee_minor') @Default(0) int cleaningFeeMinor,
    @JsonKey(name: 'tax_minor') @Default(0) int taxMinor,
    @JsonKey(name: 'platform_fee_minor') @Default(0) int platformFeeMinor,
    @JsonKey(name: 'total_minor') @Default(0) int totalMinor,
    @Default('INR') String currency,
    @JsonKey(name: 'cancellation_policy') @Default('moderate') String cancellationPolicy,
    @JsonKey(name: 'created_at') String? createdAt,
    @JsonKey(name: 'confirmed_at') String? confirmedAt,
    @JsonKey(name: 'cancelled_at') String? cancelledAt,
    @JsonKey(name: 'cancellation_reason') String? cancellationReason,
    @JsonKey(name: 'invoice_number') String? invoiceNumber,
    /// Seconds until the hold lapses and the rooms go back on sale. Present
    /// only while `pending_payment`. Not decoration: a guest who misses it
    /// loses the room.
    @JsonKey(name: 'hold_expires_in') int? holdExpiresIn,
    @JsonKey(name: 'nightly_rates') @Default(<NightlyRateDto>[]) List<NightlyRateDto> nightlyRates,
    BookingRefundDto? refund,
  }) = _BookingDto;

  factory BookingDto.fromJson(Map<String, dynamic> json) =>
      _$BookingDtoFromJson(json);
}

@freezed
abstract class BookingListDto with _$BookingListDto {
  const factory BookingListDto({
    @Default(<BookingDto>[]) List<BookingDto> items,
    @JsonKey(name: 'next_cursor') String? nextCursor,
    int? total,
  }) = _BookingListDto;

  factory BookingListDto.fromJson(Map<String, dynamic> json) =>
      _$BookingListDtoFromJson(json);
}

@freezed
abstract class RefundPreviewDto with _$RefundPreviewDto {
  const factory RefundPreviewDto({
    @Default('') String policy,
    @JsonKey(name: 'hours_before_check_in') @Default(0.0) double hoursBeforeCheckIn,
    @JsonKey(name: 'applied_percent') @Default('0%') String appliedPercent,
    @JsonKey(name: 'accommodation_minor') @Default(0) int accommodationMinor,
    @JsonKey(name: 'cleaning_fee_minor') @Default(0) int cleaningFeeMinor,
    @JsonKey(name: 'tax_minor') @Default(0) int taxMinor,
    @JsonKey(name: 'total_minor') @Default(0) int totalMinor,
    @JsonKey(name: 'vendor_retains_minor') @Default(0) int vendorRetainsMinor,
    @Default('') String reason,
    @Default('INR') String currency,
    @Default(false) bool cancellable,
  }) = _RefundPreviewDto;

  factory RefundPreviewDto.fromJson(Map<String, dynamic> json) =>
      _$RefundPreviewDtoFromJson(json);
}

@freezed
abstract class CheckoutSessionDto with _$CheckoutSessionDto {
  const factory CheckoutSessionDto({
    @JsonKey(name: 'payment_id') required String paymentId,
    @JsonKey(name: 'gateway_order_id') required String gatewayOrderId,
    /// Razorpay's **public** merchant key. Authorises nothing on its own.
    @JsonKey(name: 'key_id') @Default('') String keyId,
    @JsonKey(name: 'amount_minor') @Default(0) int amountMinor,
    @Default('INR') String currency,
    @JsonKey(name: 'booking_reference') @Default('') String bookingReference,
    @JsonKey(name: 'prefill_name') @Default('') String prefillName,
    @JsonKey(name: 'prefill_email') @Default('') String prefillEmail,
    @JsonKey(name: 'prefill_contact') @Default('') String prefillContact,
    @JsonKey(name: 'property_name') @Default('') String propertyName,
    @JsonKey(name: 'expires_in') int? expiresIn,
  }) = _CheckoutSessionDto;

  factory CheckoutSessionDto.fromJson(Map<String, dynamic> json) =>
      _$CheckoutSessionDtoFromJson(json);
}

@freezed
abstract class PaymentResultDto with _$PaymentResultDto {
  const factory PaymentResultDto({
    @JsonKey(name: 'payment_id') @Default('') String paymentId,
    @Default('') String status,
    @JsonKey(name: 'booking_id') @Default('') String bookingId,
    @JsonKey(name: 'booking_reference') @Default('') String bookingReference,
    @JsonKey(name: 'amount_minor') @Default(0) int amountMinor,
    @Default('INR') String currency,
    @Default('unknown') String method,
    @JsonKey(name: 'invoice_number') String? invoiceNumber,
    @JsonKey(name: 'booking_status') String? bookingStatus,
  }) = _PaymentResultDto;

  factory PaymentResultDto.fromJson(Map<String, dynamic> json) =>
      _$PaymentResultDtoFromJson(json);
}
