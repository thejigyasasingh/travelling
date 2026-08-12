// GENERATED CODE - DO NOT MODIFY BY HAND

part of 'booking_models.dart';

// **************************************************************************
// JsonSerializableGenerator
// **************************************************************************

_NightlyRateDto _$NightlyRateDtoFromJson(Map<String, dynamic> json) =>
    _NightlyRateDto(
      date: json['date'] as String,
      amountMinor: (json['amount_minor'] as num?)?.toInt() ?? 0,
    );

Map<String, dynamic> _$NightlyRateDtoToJson(_NightlyRateDto instance) =>
    <String, dynamic>{
      'date': instance.date,
      'amount_minor': instance.amountMinor,
    };

_BookingRefundDto _$BookingRefundDtoFromJson(Map<String, dynamic> json) =>
    _BookingRefundDto(
      status: json['status'] as String? ?? 'pending',
      amountMinor: (json['amount_minor'] as num?)?.toInt() ?? 0,
      currency: json['currency'] as String? ?? 'INR',
      reason: json['reason'] as String?,
      requestedAt: json['requested_at'] as String?,
      completedAt: json['completed_at'] as String?,
    );

Map<String, dynamic> _$BookingRefundDtoToJson(_BookingRefundDto instance) =>
    <String, dynamic>{
      'status': instance.status,
      'amount_minor': instance.amountMinor,
      'currency': instance.currency,
      'reason': instance.reason,
      'requested_at': instance.requestedAt,
      'completed_at': instance.completedAt,
    };

_BookingDto _$BookingDtoFromJson(Map<String, dynamic> json) => _BookingDto(
  id: json['id'] as String,
  reference: json['reference'] as String,
  status: json['status'] as String,
  propertyId: json['property_id'] as String? ?? '',
  propertyName: json['property_name'] as String? ?? '',
  propertyAddress: json['property_address'] as String?,
  roomTypeId: json['room_type_id'] as String? ?? '',
  roomTypeName: json['room_type_name'] as String? ?? '',
  checkIn: json['check_in'] as String,
  checkOut: json['check_out'] as String,
  nights: (json['nights'] as num?)?.toInt() ?? 0,
  adults: (json['adults'] as num?)?.toInt() ?? 1,
  children: (json['children'] as num?)?.toInt() ?? 0,
  infants: (json['infants'] as num?)?.toInt() ?? 0,
  rooms: (json['rooms'] as num?)?.toInt() ?? 1,
  guestName: json['guest_name'] as String? ?? '',
  guestEmail: json['guest_email'] as String? ?? '',
  guestPhone: json['guest_phone'] as String? ?? '',
  specialRequests: json['special_requests'] as String?,
  accommodationMinor: (json['accommodation_minor'] as num?)?.toInt() ?? 0,
  extraGuestMinor: (json['extra_guest_minor'] as num?)?.toInt() ?? 0,
  cleaningFeeMinor: (json['cleaning_fee_minor'] as num?)?.toInt() ?? 0,
  taxMinor: (json['tax_minor'] as num?)?.toInt() ?? 0,
  platformFeeMinor: (json['platform_fee_minor'] as num?)?.toInt() ?? 0,
  totalMinor: (json['total_minor'] as num?)?.toInt() ?? 0,
  currency: json['currency'] as String? ?? 'INR',
  cancellationPolicy: json['cancellation_policy'] as String? ?? 'moderate',
  createdAt: json['created_at'] as String?,
  confirmedAt: json['confirmed_at'] as String?,
  cancelledAt: json['cancelled_at'] as String?,
  cancellationReason: json['cancellation_reason'] as String?,
  invoiceNumber: json['invoice_number'] as String?,
  holdExpiresIn: (json['hold_expires_in'] as num?)?.toInt(),
  nightlyRates:
      (json['nightly_rates'] as List<dynamic>?)
          ?.map((e) => NightlyRateDto.fromJson(e as Map<String, dynamic>))
          .toList() ??
      const <NightlyRateDto>[],
  refund: json['refund'] == null
      ? null
      : BookingRefundDto.fromJson(json['refund'] as Map<String, dynamic>),
);

Map<String, dynamic> _$BookingDtoToJson(_BookingDto instance) =>
    <String, dynamic>{
      'id': instance.id,
      'reference': instance.reference,
      'status': instance.status,
      'property_id': instance.propertyId,
      'property_name': instance.propertyName,
      'property_address': instance.propertyAddress,
      'room_type_id': instance.roomTypeId,
      'room_type_name': instance.roomTypeName,
      'check_in': instance.checkIn,
      'check_out': instance.checkOut,
      'nights': instance.nights,
      'adults': instance.adults,
      'children': instance.children,
      'infants': instance.infants,
      'rooms': instance.rooms,
      'guest_name': instance.guestName,
      'guest_email': instance.guestEmail,
      'guest_phone': instance.guestPhone,
      'special_requests': instance.specialRequests,
      'accommodation_minor': instance.accommodationMinor,
      'extra_guest_minor': instance.extraGuestMinor,
      'cleaning_fee_minor': instance.cleaningFeeMinor,
      'tax_minor': instance.taxMinor,
      'platform_fee_minor': instance.platformFeeMinor,
      'total_minor': instance.totalMinor,
      'currency': instance.currency,
      'cancellation_policy': instance.cancellationPolicy,
      'created_at': instance.createdAt,
      'confirmed_at': instance.confirmedAt,
      'cancelled_at': instance.cancelledAt,
      'cancellation_reason': instance.cancellationReason,
      'invoice_number': instance.invoiceNumber,
      'hold_expires_in': instance.holdExpiresIn,
      'nightly_rates': instance.nightlyRates,
      'refund': instance.refund,
    };

_BookingListDto _$BookingListDtoFromJson(Map<String, dynamic> json) =>
    _BookingListDto(
      items:
          (json['items'] as List<dynamic>?)
              ?.map((e) => BookingDto.fromJson(e as Map<String, dynamic>))
              .toList() ??
          const <BookingDto>[],
      nextCursor: json['next_cursor'] as String?,
      total: (json['total'] as num?)?.toInt(),
    );

Map<String, dynamic> _$BookingListDtoToJson(_BookingListDto instance) =>
    <String, dynamic>{
      'items': instance.items,
      'next_cursor': instance.nextCursor,
      'total': instance.total,
    };

_RefundPreviewDto _$RefundPreviewDtoFromJson(Map<String, dynamic> json) =>
    _RefundPreviewDto(
      policy: json['policy'] as String? ?? '',
      hoursBeforeCheckIn:
          (json['hours_before_check_in'] as num?)?.toDouble() ?? 0.0,
      appliedPercent: json['applied_percent'] as String? ?? '0%',
      accommodationMinor: (json['accommodation_minor'] as num?)?.toInt() ?? 0,
      cleaningFeeMinor: (json['cleaning_fee_minor'] as num?)?.toInt() ?? 0,
      taxMinor: (json['tax_minor'] as num?)?.toInt() ?? 0,
      totalMinor: (json['total_minor'] as num?)?.toInt() ?? 0,
      vendorRetainsMinor: (json['vendor_retains_minor'] as num?)?.toInt() ?? 0,
      reason: json['reason'] as String? ?? '',
      currency: json['currency'] as String? ?? 'INR',
      cancellable: json['cancellable'] as bool? ?? false,
    );

Map<String, dynamic> _$RefundPreviewDtoToJson(_RefundPreviewDto instance) =>
    <String, dynamic>{
      'policy': instance.policy,
      'hours_before_check_in': instance.hoursBeforeCheckIn,
      'applied_percent': instance.appliedPercent,
      'accommodation_minor': instance.accommodationMinor,
      'cleaning_fee_minor': instance.cleaningFeeMinor,
      'tax_minor': instance.taxMinor,
      'total_minor': instance.totalMinor,
      'vendor_retains_minor': instance.vendorRetainsMinor,
      'reason': instance.reason,
      'currency': instance.currency,
      'cancellable': instance.cancellable,
    };

_CheckoutSessionDto _$CheckoutSessionDtoFromJson(Map<String, dynamic> json) =>
    _CheckoutSessionDto(
      paymentId: json['payment_id'] as String,
      gatewayOrderId: json['gateway_order_id'] as String,
      keyId: json['key_id'] as String? ?? '',
      amountMinor: (json['amount_minor'] as num?)?.toInt() ?? 0,
      currency: json['currency'] as String? ?? 'INR',
      bookingReference: json['booking_reference'] as String? ?? '',
      prefillName: json['prefill_name'] as String? ?? '',
      prefillEmail: json['prefill_email'] as String? ?? '',
      prefillContact: json['prefill_contact'] as String? ?? '',
      propertyName: json['property_name'] as String? ?? '',
      expiresIn: (json['expires_in'] as num?)?.toInt(),
    );

Map<String, dynamic> _$CheckoutSessionDtoToJson(_CheckoutSessionDto instance) =>
    <String, dynamic>{
      'payment_id': instance.paymentId,
      'gateway_order_id': instance.gatewayOrderId,
      'key_id': instance.keyId,
      'amount_minor': instance.amountMinor,
      'currency': instance.currency,
      'booking_reference': instance.bookingReference,
      'prefill_name': instance.prefillName,
      'prefill_email': instance.prefillEmail,
      'prefill_contact': instance.prefillContact,
      'property_name': instance.propertyName,
      'expires_in': instance.expiresIn,
    };

_PaymentResultDto _$PaymentResultDtoFromJson(Map<String, dynamic> json) =>
    _PaymentResultDto(
      paymentId: json['payment_id'] as String? ?? '',
      status: json['status'] as String? ?? '',
      bookingId: json['booking_id'] as String? ?? '',
      bookingReference: json['booking_reference'] as String? ?? '',
      amountMinor: (json['amount_minor'] as num?)?.toInt() ?? 0,
      currency: json['currency'] as String? ?? 'INR',
      method: json['method'] as String? ?? 'unknown',
      invoiceNumber: json['invoice_number'] as String?,
      bookingStatus: json['booking_status'] as String?,
    );

Map<String, dynamic> _$PaymentResultDtoToJson(_PaymentResultDto instance) =>
    <String, dynamic>{
      'payment_id': instance.paymentId,
      'status': instance.status,
      'booking_id': instance.bookingId,
      'booking_reference': instance.bookingReference,
      'amount_minor': instance.amountMinor,
      'currency': instance.currency,
      'method': instance.method,
      'invoice_number': instance.invoiceNumber,
      'booking_status': instance.bookingStatus,
    };
