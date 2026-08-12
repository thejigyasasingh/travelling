// GENERATED CODE - DO NOT MODIFY BY HAND
// coverage:ignore-file
// ignore_for_file: type=lint
// ignore_for_file: unused_element, deprecated_member_use, deprecated_member_use_from_same_package, use_function_type_syntax_for_parameters, unnecessary_const, avoid_init_to_null, invalid_override_different_default_values_named, prefer_expression_function_bodies, annotate_overrides, invalid_annotation_target, unnecessary_question_mark

part of 'booking_models.dart';

// **************************************************************************
// FreezedGenerator
// **************************************************************************

// dart format off
T _$identity<T>(T value) => value;

/// @nodoc
mixin _$NightlyRateDto {

 String get date;@JsonKey(name: 'amount_minor') int get amountMinor;
/// Create a copy of NightlyRateDto
/// with the given fields replaced by the non-null parameter values.
@JsonKey(includeFromJson: false, includeToJson: false)
@pragma('vm:prefer-inline')
$NightlyRateDtoCopyWith<NightlyRateDto> get copyWith => _$NightlyRateDtoCopyWithImpl<NightlyRateDto>(this as NightlyRateDto, _$identity);

  /// Serializes this NightlyRateDto to a JSON map.
  Map<String, dynamic> toJson();


@override
bool operator ==(Object other) {
  return identical(this, other) || (other.runtimeType == runtimeType&&other is NightlyRateDto&&(identical(other.date, date) || other.date == date)&&(identical(other.amountMinor, amountMinor) || other.amountMinor == amountMinor));
}

@JsonKey(includeFromJson: false, includeToJson: false)
@override
int get hashCode => Object.hash(runtimeType,date,amountMinor);

@override
String toString() {
  return 'NightlyRateDto(date: $date, amountMinor: $amountMinor)';
}


}

/// @nodoc
abstract mixin class $NightlyRateDtoCopyWith<$Res>  {
  factory $NightlyRateDtoCopyWith(NightlyRateDto value, $Res Function(NightlyRateDto) _then) = _$NightlyRateDtoCopyWithImpl;
@useResult
$Res call({
 String date,@JsonKey(name: 'amount_minor') int amountMinor
});




}
/// @nodoc
class _$NightlyRateDtoCopyWithImpl<$Res>
    implements $NightlyRateDtoCopyWith<$Res> {
  _$NightlyRateDtoCopyWithImpl(this._self, this._then);

  final NightlyRateDto _self;
  final $Res Function(NightlyRateDto) _then;

/// Create a copy of NightlyRateDto
/// with the given fields replaced by the non-null parameter values.
@pragma('vm:prefer-inline') @override $Res call({Object? date = null,Object? amountMinor = null,}) {
  return _then(_self.copyWith(
date: null == date ? _self.date : date // ignore: cast_nullable_to_non_nullable
as String,amountMinor: null == amountMinor ? _self.amountMinor : amountMinor // ignore: cast_nullable_to_non_nullable
as int,
  ));
}

}


/// Adds pattern-matching-related methods to [NightlyRateDto].
extension NightlyRateDtoPatterns on NightlyRateDto {
/// A variant of `map` that fallback to returning `orElse`.
///
/// It is equivalent to doing:
/// ```dart
/// switch (sealedClass) {
///   case final Subclass value:
///     return ...;
///   case _:
///     return orElse();
/// }
/// ```

@optionalTypeArgs TResult maybeMap<TResult extends Object?>(TResult Function( _NightlyRateDto value)?  $default,{required TResult orElse(),}){
final _that = this;
switch (_that) {
case _NightlyRateDto() when $default != null:
return $default(_that);case _:
  return orElse();

}
}
/// A `switch`-like method, using callbacks.
///
/// Callbacks receives the raw object, upcasted.
/// It is equivalent to doing:
/// ```dart
/// switch (sealedClass) {
///   case final Subclass value:
///     return ...;
///   case final Subclass2 value:
///     return ...;
/// }
/// ```

@optionalTypeArgs TResult map<TResult extends Object?>(TResult Function( _NightlyRateDto value)  $default,){
final _that = this;
switch (_that) {
case _NightlyRateDto():
return $default(_that);case _:
  throw StateError('Unexpected subclass');

}
}
/// A variant of `map` that fallback to returning `null`.
///
/// It is equivalent to doing:
/// ```dart
/// switch (sealedClass) {
///   case final Subclass value:
///     return ...;
///   case _:
///     return null;
/// }
/// ```

@optionalTypeArgs TResult? mapOrNull<TResult extends Object?>(TResult? Function( _NightlyRateDto value)?  $default,){
final _that = this;
switch (_that) {
case _NightlyRateDto() when $default != null:
return $default(_that);case _:
  return null;

}
}
/// A variant of `when` that fallback to an `orElse` callback.
///
/// It is equivalent to doing:
/// ```dart
/// switch (sealedClass) {
///   case Subclass(:final field):
///     return ...;
///   case _:
///     return orElse();
/// }
/// ```

@optionalTypeArgs TResult maybeWhen<TResult extends Object?>(TResult Function( String date, @JsonKey(name: 'amount_minor')  int amountMinor)?  $default,{required TResult orElse(),}) {final _that = this;
switch (_that) {
case _NightlyRateDto() when $default != null:
return $default(_that.date,_that.amountMinor);case _:
  return orElse();

}
}
/// A `switch`-like method, using callbacks.
///
/// As opposed to `map`, this offers destructuring.
/// It is equivalent to doing:
/// ```dart
/// switch (sealedClass) {
///   case Subclass(:final field):
///     return ...;
///   case Subclass2(:final field2):
///     return ...;
/// }
/// ```

@optionalTypeArgs TResult when<TResult extends Object?>(TResult Function( String date, @JsonKey(name: 'amount_minor')  int amountMinor)  $default,) {final _that = this;
switch (_that) {
case _NightlyRateDto():
return $default(_that.date,_that.amountMinor);case _:
  throw StateError('Unexpected subclass');

}
}
/// A variant of `when` that fallback to returning `null`
///
/// It is equivalent to doing:
/// ```dart
/// switch (sealedClass) {
///   case Subclass(:final field):
///     return ...;
///   case _:
///     return null;
/// }
/// ```

@optionalTypeArgs TResult? whenOrNull<TResult extends Object?>(TResult? Function( String date, @JsonKey(name: 'amount_minor')  int amountMinor)?  $default,) {final _that = this;
switch (_that) {
case _NightlyRateDto() when $default != null:
return $default(_that.date,_that.amountMinor);case _:
  return null;

}
}

}

/// @nodoc
@JsonSerializable()

class _NightlyRateDto implements NightlyRateDto {
  const _NightlyRateDto({required this.date, @JsonKey(name: 'amount_minor') this.amountMinor = 0});
  factory _NightlyRateDto.fromJson(Map<String, dynamic> json) => _$NightlyRateDtoFromJson(json);

@override final  String date;
@override@JsonKey(name: 'amount_minor') final  int amountMinor;

/// Create a copy of NightlyRateDto
/// with the given fields replaced by the non-null parameter values.
@override @JsonKey(includeFromJson: false, includeToJson: false)
@pragma('vm:prefer-inline')
_$NightlyRateDtoCopyWith<_NightlyRateDto> get copyWith => __$NightlyRateDtoCopyWithImpl<_NightlyRateDto>(this, _$identity);

@override
Map<String, dynamic> toJson() {
  return _$NightlyRateDtoToJson(this, );
}

@override
bool operator ==(Object other) {
  return identical(this, other) || (other.runtimeType == runtimeType&&other is _NightlyRateDto&&(identical(other.date, date) || other.date == date)&&(identical(other.amountMinor, amountMinor) || other.amountMinor == amountMinor));
}

@JsonKey(includeFromJson: false, includeToJson: false)
@override
int get hashCode => Object.hash(runtimeType,date,amountMinor);

@override
String toString() {
  return 'NightlyRateDto(date: $date, amountMinor: $amountMinor)';
}


}

/// @nodoc
abstract mixin class _$NightlyRateDtoCopyWith<$Res> implements $NightlyRateDtoCopyWith<$Res> {
  factory _$NightlyRateDtoCopyWith(_NightlyRateDto value, $Res Function(_NightlyRateDto) _then) = __$NightlyRateDtoCopyWithImpl;
@override @useResult
$Res call({
 String date,@JsonKey(name: 'amount_minor') int amountMinor
});




}
/// @nodoc
class __$NightlyRateDtoCopyWithImpl<$Res>
    implements _$NightlyRateDtoCopyWith<$Res> {
  __$NightlyRateDtoCopyWithImpl(this._self, this._then);

  final _NightlyRateDto _self;
  final $Res Function(_NightlyRateDto) _then;

/// Create a copy of NightlyRateDto
/// with the given fields replaced by the non-null parameter values.
@override @pragma('vm:prefer-inline') $Res call({Object? date = null,Object? amountMinor = null,}) {
  return _then(_NightlyRateDto(
date: null == date ? _self.date : date // ignore: cast_nullable_to_non_nullable
as String,amountMinor: null == amountMinor ? _self.amountMinor : amountMinor // ignore: cast_nullable_to_non_nullable
as int,
  ));
}


}


/// @nodoc
mixin _$BookingRefundDto {

 String get status;@JsonKey(name: 'amount_minor') int get amountMinor; String get currency; String? get reason;@JsonKey(name: 'requested_at') String? get requestedAt;@JsonKey(name: 'completed_at') String? get completedAt;
/// Create a copy of BookingRefundDto
/// with the given fields replaced by the non-null parameter values.
@JsonKey(includeFromJson: false, includeToJson: false)
@pragma('vm:prefer-inline')
$BookingRefundDtoCopyWith<BookingRefundDto> get copyWith => _$BookingRefundDtoCopyWithImpl<BookingRefundDto>(this as BookingRefundDto, _$identity);

  /// Serializes this BookingRefundDto to a JSON map.
  Map<String, dynamic> toJson();


@override
bool operator ==(Object other) {
  return identical(this, other) || (other.runtimeType == runtimeType&&other is BookingRefundDto&&(identical(other.status, status) || other.status == status)&&(identical(other.amountMinor, amountMinor) || other.amountMinor == amountMinor)&&(identical(other.currency, currency) || other.currency == currency)&&(identical(other.reason, reason) || other.reason == reason)&&(identical(other.requestedAt, requestedAt) || other.requestedAt == requestedAt)&&(identical(other.completedAt, completedAt) || other.completedAt == completedAt));
}

@JsonKey(includeFromJson: false, includeToJson: false)
@override
int get hashCode => Object.hash(runtimeType,status,amountMinor,currency,reason,requestedAt,completedAt);

@override
String toString() {
  return 'BookingRefundDto(status: $status, amountMinor: $amountMinor, currency: $currency, reason: $reason, requestedAt: $requestedAt, completedAt: $completedAt)';
}


}

/// @nodoc
abstract mixin class $BookingRefundDtoCopyWith<$Res>  {
  factory $BookingRefundDtoCopyWith(BookingRefundDto value, $Res Function(BookingRefundDto) _then) = _$BookingRefundDtoCopyWithImpl;
@useResult
$Res call({
 String status,@JsonKey(name: 'amount_minor') int amountMinor, String currency, String? reason,@JsonKey(name: 'requested_at') String? requestedAt,@JsonKey(name: 'completed_at') String? completedAt
});




}
/// @nodoc
class _$BookingRefundDtoCopyWithImpl<$Res>
    implements $BookingRefundDtoCopyWith<$Res> {
  _$BookingRefundDtoCopyWithImpl(this._self, this._then);

  final BookingRefundDto _self;
  final $Res Function(BookingRefundDto) _then;

/// Create a copy of BookingRefundDto
/// with the given fields replaced by the non-null parameter values.
@pragma('vm:prefer-inline') @override $Res call({Object? status = null,Object? amountMinor = null,Object? currency = null,Object? reason = freezed,Object? requestedAt = freezed,Object? completedAt = freezed,}) {
  return _then(_self.copyWith(
status: null == status ? _self.status : status // ignore: cast_nullable_to_non_nullable
as String,amountMinor: null == amountMinor ? _self.amountMinor : amountMinor // ignore: cast_nullable_to_non_nullable
as int,currency: null == currency ? _self.currency : currency // ignore: cast_nullable_to_non_nullable
as String,reason: freezed == reason ? _self.reason : reason // ignore: cast_nullable_to_non_nullable
as String?,requestedAt: freezed == requestedAt ? _self.requestedAt : requestedAt // ignore: cast_nullable_to_non_nullable
as String?,completedAt: freezed == completedAt ? _self.completedAt : completedAt // ignore: cast_nullable_to_non_nullable
as String?,
  ));
}

}


/// Adds pattern-matching-related methods to [BookingRefundDto].
extension BookingRefundDtoPatterns on BookingRefundDto {
/// A variant of `map` that fallback to returning `orElse`.
///
/// It is equivalent to doing:
/// ```dart
/// switch (sealedClass) {
///   case final Subclass value:
///     return ...;
///   case _:
///     return orElse();
/// }
/// ```

@optionalTypeArgs TResult maybeMap<TResult extends Object?>(TResult Function( _BookingRefundDto value)?  $default,{required TResult orElse(),}){
final _that = this;
switch (_that) {
case _BookingRefundDto() when $default != null:
return $default(_that);case _:
  return orElse();

}
}
/// A `switch`-like method, using callbacks.
///
/// Callbacks receives the raw object, upcasted.
/// It is equivalent to doing:
/// ```dart
/// switch (sealedClass) {
///   case final Subclass value:
///     return ...;
///   case final Subclass2 value:
///     return ...;
/// }
/// ```

@optionalTypeArgs TResult map<TResult extends Object?>(TResult Function( _BookingRefundDto value)  $default,){
final _that = this;
switch (_that) {
case _BookingRefundDto():
return $default(_that);case _:
  throw StateError('Unexpected subclass');

}
}
/// A variant of `map` that fallback to returning `null`.
///
/// It is equivalent to doing:
/// ```dart
/// switch (sealedClass) {
///   case final Subclass value:
///     return ...;
///   case _:
///     return null;
/// }
/// ```

@optionalTypeArgs TResult? mapOrNull<TResult extends Object?>(TResult? Function( _BookingRefundDto value)?  $default,){
final _that = this;
switch (_that) {
case _BookingRefundDto() when $default != null:
return $default(_that);case _:
  return null;

}
}
/// A variant of `when` that fallback to an `orElse` callback.
///
/// It is equivalent to doing:
/// ```dart
/// switch (sealedClass) {
///   case Subclass(:final field):
///     return ...;
///   case _:
///     return orElse();
/// }
/// ```

@optionalTypeArgs TResult maybeWhen<TResult extends Object?>(TResult Function( String status, @JsonKey(name: 'amount_minor')  int amountMinor,  String currency,  String? reason, @JsonKey(name: 'requested_at')  String? requestedAt, @JsonKey(name: 'completed_at')  String? completedAt)?  $default,{required TResult orElse(),}) {final _that = this;
switch (_that) {
case _BookingRefundDto() when $default != null:
return $default(_that.status,_that.amountMinor,_that.currency,_that.reason,_that.requestedAt,_that.completedAt);case _:
  return orElse();

}
}
/// A `switch`-like method, using callbacks.
///
/// As opposed to `map`, this offers destructuring.
/// It is equivalent to doing:
/// ```dart
/// switch (sealedClass) {
///   case Subclass(:final field):
///     return ...;
///   case Subclass2(:final field2):
///     return ...;
/// }
/// ```

@optionalTypeArgs TResult when<TResult extends Object?>(TResult Function( String status, @JsonKey(name: 'amount_minor')  int amountMinor,  String currency,  String? reason, @JsonKey(name: 'requested_at')  String? requestedAt, @JsonKey(name: 'completed_at')  String? completedAt)  $default,) {final _that = this;
switch (_that) {
case _BookingRefundDto():
return $default(_that.status,_that.amountMinor,_that.currency,_that.reason,_that.requestedAt,_that.completedAt);case _:
  throw StateError('Unexpected subclass');

}
}
/// A variant of `when` that fallback to returning `null`
///
/// It is equivalent to doing:
/// ```dart
/// switch (sealedClass) {
///   case Subclass(:final field):
///     return ...;
///   case _:
///     return null;
/// }
/// ```

@optionalTypeArgs TResult? whenOrNull<TResult extends Object?>(TResult? Function( String status, @JsonKey(name: 'amount_minor')  int amountMinor,  String currency,  String? reason, @JsonKey(name: 'requested_at')  String? requestedAt, @JsonKey(name: 'completed_at')  String? completedAt)?  $default,) {final _that = this;
switch (_that) {
case _BookingRefundDto() when $default != null:
return $default(_that.status,_that.amountMinor,_that.currency,_that.reason,_that.requestedAt,_that.completedAt);case _:
  return null;

}
}

}

/// @nodoc
@JsonSerializable()

class _BookingRefundDto implements BookingRefundDto {
  const _BookingRefundDto({this.status = 'pending', @JsonKey(name: 'amount_minor') this.amountMinor = 0, this.currency = 'INR', this.reason, @JsonKey(name: 'requested_at') this.requestedAt, @JsonKey(name: 'completed_at') this.completedAt});
  factory _BookingRefundDto.fromJson(Map<String, dynamic> json) => _$BookingRefundDtoFromJson(json);

@override@JsonKey() final  String status;
@override@JsonKey(name: 'amount_minor') final  int amountMinor;
@override@JsonKey() final  String currency;
@override final  String? reason;
@override@JsonKey(name: 'requested_at') final  String? requestedAt;
@override@JsonKey(name: 'completed_at') final  String? completedAt;

/// Create a copy of BookingRefundDto
/// with the given fields replaced by the non-null parameter values.
@override @JsonKey(includeFromJson: false, includeToJson: false)
@pragma('vm:prefer-inline')
_$BookingRefundDtoCopyWith<_BookingRefundDto> get copyWith => __$BookingRefundDtoCopyWithImpl<_BookingRefundDto>(this, _$identity);

@override
Map<String, dynamic> toJson() {
  return _$BookingRefundDtoToJson(this, );
}

@override
bool operator ==(Object other) {
  return identical(this, other) || (other.runtimeType == runtimeType&&other is _BookingRefundDto&&(identical(other.status, status) || other.status == status)&&(identical(other.amountMinor, amountMinor) || other.amountMinor == amountMinor)&&(identical(other.currency, currency) || other.currency == currency)&&(identical(other.reason, reason) || other.reason == reason)&&(identical(other.requestedAt, requestedAt) || other.requestedAt == requestedAt)&&(identical(other.completedAt, completedAt) || other.completedAt == completedAt));
}

@JsonKey(includeFromJson: false, includeToJson: false)
@override
int get hashCode => Object.hash(runtimeType,status,amountMinor,currency,reason,requestedAt,completedAt);

@override
String toString() {
  return 'BookingRefundDto(status: $status, amountMinor: $amountMinor, currency: $currency, reason: $reason, requestedAt: $requestedAt, completedAt: $completedAt)';
}


}

/// @nodoc
abstract mixin class _$BookingRefundDtoCopyWith<$Res> implements $BookingRefundDtoCopyWith<$Res> {
  factory _$BookingRefundDtoCopyWith(_BookingRefundDto value, $Res Function(_BookingRefundDto) _then) = __$BookingRefundDtoCopyWithImpl;
@override @useResult
$Res call({
 String status,@JsonKey(name: 'amount_minor') int amountMinor, String currency, String? reason,@JsonKey(name: 'requested_at') String? requestedAt,@JsonKey(name: 'completed_at') String? completedAt
});




}
/// @nodoc
class __$BookingRefundDtoCopyWithImpl<$Res>
    implements _$BookingRefundDtoCopyWith<$Res> {
  __$BookingRefundDtoCopyWithImpl(this._self, this._then);

  final _BookingRefundDto _self;
  final $Res Function(_BookingRefundDto) _then;

/// Create a copy of BookingRefundDto
/// with the given fields replaced by the non-null parameter values.
@override @pragma('vm:prefer-inline') $Res call({Object? status = null,Object? amountMinor = null,Object? currency = null,Object? reason = freezed,Object? requestedAt = freezed,Object? completedAt = freezed,}) {
  return _then(_BookingRefundDto(
status: null == status ? _self.status : status // ignore: cast_nullable_to_non_nullable
as String,amountMinor: null == amountMinor ? _self.amountMinor : amountMinor // ignore: cast_nullable_to_non_nullable
as int,currency: null == currency ? _self.currency : currency // ignore: cast_nullable_to_non_nullable
as String,reason: freezed == reason ? _self.reason : reason // ignore: cast_nullable_to_non_nullable
as String?,requestedAt: freezed == requestedAt ? _self.requestedAt : requestedAt // ignore: cast_nullable_to_non_nullable
as String?,completedAt: freezed == completedAt ? _self.completedAt : completedAt // ignore: cast_nullable_to_non_nullable
as String?,
  ));
}


}


/// @nodoc
mixin _$BookingDto {

 String get id; String get reference; String get status;@JsonKey(name: 'property_id') String get propertyId;@JsonKey(name: 'property_name') String get propertyName;@JsonKey(name: 'property_address') String? get propertyAddress;@JsonKey(name: 'room_type_id') String get roomTypeId;@JsonKey(name: 'room_type_name') String get roomTypeName;@JsonKey(name: 'check_in') String get checkIn;@JsonKey(name: 'check_out') String get checkOut; int get nights; int get adults; int get children; int get infants; int get rooms;@JsonKey(name: 'guest_name') String get guestName;@JsonKey(name: 'guest_email') String get guestEmail;@JsonKey(name: 'guest_phone') String get guestPhone;@JsonKey(name: 'special_requests') String? get specialRequests;@JsonKey(name: 'accommodation_minor') int get accommodationMinor;@JsonKey(name: 'extra_guest_minor') int get extraGuestMinor;@JsonKey(name: 'cleaning_fee_minor') int get cleaningFeeMinor;@JsonKey(name: 'tax_minor') int get taxMinor;@JsonKey(name: 'platform_fee_minor') int get platformFeeMinor;@JsonKey(name: 'total_minor') int get totalMinor; String get currency;@JsonKey(name: 'cancellation_policy') String get cancellationPolicy;@JsonKey(name: 'created_at') String? get createdAt;@JsonKey(name: 'confirmed_at') String? get confirmedAt;@JsonKey(name: 'cancelled_at') String? get cancelledAt;@JsonKey(name: 'cancellation_reason') String? get cancellationReason;@JsonKey(name: 'invoice_number') String? get invoiceNumber;/// Seconds until the hold lapses and the rooms go back on sale. Present
/// only while `pending_payment`. Not decoration: a guest who misses it
/// loses the room.
@JsonKey(name: 'hold_expires_in') int? get holdExpiresIn;@JsonKey(name: 'nightly_rates') List<NightlyRateDto> get nightlyRates; BookingRefundDto? get refund;
/// Create a copy of BookingDto
/// with the given fields replaced by the non-null parameter values.
@JsonKey(includeFromJson: false, includeToJson: false)
@pragma('vm:prefer-inline')
$BookingDtoCopyWith<BookingDto> get copyWith => _$BookingDtoCopyWithImpl<BookingDto>(this as BookingDto, _$identity);

  /// Serializes this BookingDto to a JSON map.
  Map<String, dynamic> toJson();


@override
bool operator ==(Object other) {
  return identical(this, other) || (other.runtimeType == runtimeType&&other is BookingDto&&(identical(other.id, id) || other.id == id)&&(identical(other.reference, reference) || other.reference == reference)&&(identical(other.status, status) || other.status == status)&&(identical(other.propertyId, propertyId) || other.propertyId == propertyId)&&(identical(other.propertyName, propertyName) || other.propertyName == propertyName)&&(identical(other.propertyAddress, propertyAddress) || other.propertyAddress == propertyAddress)&&(identical(other.roomTypeId, roomTypeId) || other.roomTypeId == roomTypeId)&&(identical(other.roomTypeName, roomTypeName) || other.roomTypeName == roomTypeName)&&(identical(other.checkIn, checkIn) || other.checkIn == checkIn)&&(identical(other.checkOut, checkOut) || other.checkOut == checkOut)&&(identical(other.nights, nights) || other.nights == nights)&&(identical(other.adults, adults) || other.adults == adults)&&(identical(other.children, children) || other.children == children)&&(identical(other.infants, infants) || other.infants == infants)&&(identical(other.rooms, rooms) || other.rooms == rooms)&&(identical(other.guestName, guestName) || other.guestName == guestName)&&(identical(other.guestEmail, guestEmail) || other.guestEmail == guestEmail)&&(identical(other.guestPhone, guestPhone) || other.guestPhone == guestPhone)&&(identical(other.specialRequests, specialRequests) || other.specialRequests == specialRequests)&&(identical(other.accommodationMinor, accommodationMinor) || other.accommodationMinor == accommodationMinor)&&(identical(other.extraGuestMinor, extraGuestMinor) || other.extraGuestMinor == extraGuestMinor)&&(identical(other.cleaningFeeMinor, cleaningFeeMinor) || other.cleaningFeeMinor == cleaningFeeMinor)&&(identical(other.taxMinor, taxMinor) || other.taxMinor == taxMinor)&&(identical(other.platformFeeMinor, platformFeeMinor) || other.platformFeeMinor == platformFeeMinor)&&(identical(other.totalMinor, totalMinor) || other.totalMinor == totalMinor)&&(identical(other.currency, currency) || other.currency == currency)&&(identical(other.cancellationPolicy, cancellationPolicy) || other.cancellationPolicy == cancellationPolicy)&&(identical(other.createdAt, createdAt) || other.createdAt == createdAt)&&(identical(other.confirmedAt, confirmedAt) || other.confirmedAt == confirmedAt)&&(identical(other.cancelledAt, cancelledAt) || other.cancelledAt == cancelledAt)&&(identical(other.cancellationReason, cancellationReason) || other.cancellationReason == cancellationReason)&&(identical(other.invoiceNumber, invoiceNumber) || other.invoiceNumber == invoiceNumber)&&(identical(other.holdExpiresIn, holdExpiresIn) || other.holdExpiresIn == holdExpiresIn)&&const DeepCollectionEquality().equals(other.nightlyRates, nightlyRates)&&(identical(other.refund, refund) || other.refund == refund));
}

@JsonKey(includeFromJson: false, includeToJson: false)
@override
int get hashCode => Object.hashAll([runtimeType,id,reference,status,propertyId,propertyName,propertyAddress,roomTypeId,roomTypeName,checkIn,checkOut,nights,adults,children,infants,rooms,guestName,guestEmail,guestPhone,specialRequests,accommodationMinor,extraGuestMinor,cleaningFeeMinor,taxMinor,platformFeeMinor,totalMinor,currency,cancellationPolicy,createdAt,confirmedAt,cancelledAt,cancellationReason,invoiceNumber,holdExpiresIn,const DeepCollectionEquality().hash(nightlyRates),refund]);

@override
String toString() {
  return 'BookingDto(id: $id, reference: $reference, status: $status, propertyId: $propertyId, propertyName: $propertyName, propertyAddress: $propertyAddress, roomTypeId: $roomTypeId, roomTypeName: $roomTypeName, checkIn: $checkIn, checkOut: $checkOut, nights: $nights, adults: $adults, children: $children, infants: $infants, rooms: $rooms, guestName: $guestName, guestEmail: $guestEmail, guestPhone: $guestPhone, specialRequests: $specialRequests, accommodationMinor: $accommodationMinor, extraGuestMinor: $extraGuestMinor, cleaningFeeMinor: $cleaningFeeMinor, taxMinor: $taxMinor, platformFeeMinor: $platformFeeMinor, totalMinor: $totalMinor, currency: $currency, cancellationPolicy: $cancellationPolicy, createdAt: $createdAt, confirmedAt: $confirmedAt, cancelledAt: $cancelledAt, cancellationReason: $cancellationReason, invoiceNumber: $invoiceNumber, holdExpiresIn: $holdExpiresIn, nightlyRates: $nightlyRates, refund: $refund)';
}


}

/// @nodoc
abstract mixin class $BookingDtoCopyWith<$Res>  {
  factory $BookingDtoCopyWith(BookingDto value, $Res Function(BookingDto) _then) = _$BookingDtoCopyWithImpl;
@useResult
$Res call({
 String id, String reference, String status,@JsonKey(name: 'property_id') String propertyId,@JsonKey(name: 'property_name') String propertyName,@JsonKey(name: 'property_address') String? propertyAddress,@JsonKey(name: 'room_type_id') String roomTypeId,@JsonKey(name: 'room_type_name') String roomTypeName,@JsonKey(name: 'check_in') String checkIn,@JsonKey(name: 'check_out') String checkOut, int nights, int adults, int children, int infants, int rooms,@JsonKey(name: 'guest_name') String guestName,@JsonKey(name: 'guest_email') String guestEmail,@JsonKey(name: 'guest_phone') String guestPhone,@JsonKey(name: 'special_requests') String? specialRequests,@JsonKey(name: 'accommodation_minor') int accommodationMinor,@JsonKey(name: 'extra_guest_minor') int extraGuestMinor,@JsonKey(name: 'cleaning_fee_minor') int cleaningFeeMinor,@JsonKey(name: 'tax_minor') int taxMinor,@JsonKey(name: 'platform_fee_minor') int platformFeeMinor,@JsonKey(name: 'total_minor') int totalMinor, String currency,@JsonKey(name: 'cancellation_policy') String cancellationPolicy,@JsonKey(name: 'created_at') String? createdAt,@JsonKey(name: 'confirmed_at') String? confirmedAt,@JsonKey(name: 'cancelled_at') String? cancelledAt,@JsonKey(name: 'cancellation_reason') String? cancellationReason,@JsonKey(name: 'invoice_number') String? invoiceNumber,@JsonKey(name: 'hold_expires_in') int? holdExpiresIn,@JsonKey(name: 'nightly_rates') List<NightlyRateDto> nightlyRates, BookingRefundDto? refund
});


$BookingRefundDtoCopyWith<$Res>? get refund;

}
/// @nodoc
class _$BookingDtoCopyWithImpl<$Res>
    implements $BookingDtoCopyWith<$Res> {
  _$BookingDtoCopyWithImpl(this._self, this._then);

  final BookingDto _self;
  final $Res Function(BookingDto) _then;

/// Create a copy of BookingDto
/// with the given fields replaced by the non-null parameter values.
@pragma('vm:prefer-inline') @override $Res call({Object? id = null,Object? reference = null,Object? status = null,Object? propertyId = null,Object? propertyName = null,Object? propertyAddress = freezed,Object? roomTypeId = null,Object? roomTypeName = null,Object? checkIn = null,Object? checkOut = null,Object? nights = null,Object? adults = null,Object? children = null,Object? infants = null,Object? rooms = null,Object? guestName = null,Object? guestEmail = null,Object? guestPhone = null,Object? specialRequests = freezed,Object? accommodationMinor = null,Object? extraGuestMinor = null,Object? cleaningFeeMinor = null,Object? taxMinor = null,Object? platformFeeMinor = null,Object? totalMinor = null,Object? currency = null,Object? cancellationPolicy = null,Object? createdAt = freezed,Object? confirmedAt = freezed,Object? cancelledAt = freezed,Object? cancellationReason = freezed,Object? invoiceNumber = freezed,Object? holdExpiresIn = freezed,Object? nightlyRates = null,Object? refund = freezed,}) {
  return _then(_self.copyWith(
id: null == id ? _self.id : id // ignore: cast_nullable_to_non_nullable
as String,reference: null == reference ? _self.reference : reference // ignore: cast_nullable_to_non_nullable
as String,status: null == status ? _self.status : status // ignore: cast_nullable_to_non_nullable
as String,propertyId: null == propertyId ? _self.propertyId : propertyId // ignore: cast_nullable_to_non_nullable
as String,propertyName: null == propertyName ? _self.propertyName : propertyName // ignore: cast_nullable_to_non_nullable
as String,propertyAddress: freezed == propertyAddress ? _self.propertyAddress : propertyAddress // ignore: cast_nullable_to_non_nullable
as String?,roomTypeId: null == roomTypeId ? _self.roomTypeId : roomTypeId // ignore: cast_nullable_to_non_nullable
as String,roomTypeName: null == roomTypeName ? _self.roomTypeName : roomTypeName // ignore: cast_nullable_to_non_nullable
as String,checkIn: null == checkIn ? _self.checkIn : checkIn // ignore: cast_nullable_to_non_nullable
as String,checkOut: null == checkOut ? _self.checkOut : checkOut // ignore: cast_nullable_to_non_nullable
as String,nights: null == nights ? _self.nights : nights // ignore: cast_nullable_to_non_nullable
as int,adults: null == adults ? _self.adults : adults // ignore: cast_nullable_to_non_nullable
as int,children: null == children ? _self.children : children // ignore: cast_nullable_to_non_nullable
as int,infants: null == infants ? _self.infants : infants // ignore: cast_nullable_to_non_nullable
as int,rooms: null == rooms ? _self.rooms : rooms // ignore: cast_nullable_to_non_nullable
as int,guestName: null == guestName ? _self.guestName : guestName // ignore: cast_nullable_to_non_nullable
as String,guestEmail: null == guestEmail ? _self.guestEmail : guestEmail // ignore: cast_nullable_to_non_nullable
as String,guestPhone: null == guestPhone ? _self.guestPhone : guestPhone // ignore: cast_nullable_to_non_nullable
as String,specialRequests: freezed == specialRequests ? _self.specialRequests : specialRequests // ignore: cast_nullable_to_non_nullable
as String?,accommodationMinor: null == accommodationMinor ? _self.accommodationMinor : accommodationMinor // ignore: cast_nullable_to_non_nullable
as int,extraGuestMinor: null == extraGuestMinor ? _self.extraGuestMinor : extraGuestMinor // ignore: cast_nullable_to_non_nullable
as int,cleaningFeeMinor: null == cleaningFeeMinor ? _self.cleaningFeeMinor : cleaningFeeMinor // ignore: cast_nullable_to_non_nullable
as int,taxMinor: null == taxMinor ? _self.taxMinor : taxMinor // ignore: cast_nullable_to_non_nullable
as int,platformFeeMinor: null == platformFeeMinor ? _self.platformFeeMinor : platformFeeMinor // ignore: cast_nullable_to_non_nullable
as int,totalMinor: null == totalMinor ? _self.totalMinor : totalMinor // ignore: cast_nullable_to_non_nullable
as int,currency: null == currency ? _self.currency : currency // ignore: cast_nullable_to_non_nullable
as String,cancellationPolicy: null == cancellationPolicy ? _self.cancellationPolicy : cancellationPolicy // ignore: cast_nullable_to_non_nullable
as String,createdAt: freezed == createdAt ? _self.createdAt : createdAt // ignore: cast_nullable_to_non_nullable
as String?,confirmedAt: freezed == confirmedAt ? _self.confirmedAt : confirmedAt // ignore: cast_nullable_to_non_nullable
as String?,cancelledAt: freezed == cancelledAt ? _self.cancelledAt : cancelledAt // ignore: cast_nullable_to_non_nullable
as String?,cancellationReason: freezed == cancellationReason ? _self.cancellationReason : cancellationReason // ignore: cast_nullable_to_non_nullable
as String?,invoiceNumber: freezed == invoiceNumber ? _self.invoiceNumber : invoiceNumber // ignore: cast_nullable_to_non_nullable
as String?,holdExpiresIn: freezed == holdExpiresIn ? _self.holdExpiresIn : holdExpiresIn // ignore: cast_nullable_to_non_nullable
as int?,nightlyRates: null == nightlyRates ? _self.nightlyRates : nightlyRates // ignore: cast_nullable_to_non_nullable
as List<NightlyRateDto>,refund: freezed == refund ? _self.refund : refund // ignore: cast_nullable_to_non_nullable
as BookingRefundDto?,
  ));
}
/// Create a copy of BookingDto
/// with the given fields replaced by the non-null parameter values.
@override
@pragma('vm:prefer-inline')
$BookingRefundDtoCopyWith<$Res>? get refund {
    if (_self.refund == null) {
    return null;
  }

  return $BookingRefundDtoCopyWith<$Res>(_self.refund!, (value) {
    return _then(_self.copyWith(refund: value));
  });
}
}


/// Adds pattern-matching-related methods to [BookingDto].
extension BookingDtoPatterns on BookingDto {
/// A variant of `map` that fallback to returning `orElse`.
///
/// It is equivalent to doing:
/// ```dart
/// switch (sealedClass) {
///   case final Subclass value:
///     return ...;
///   case _:
///     return orElse();
/// }
/// ```

@optionalTypeArgs TResult maybeMap<TResult extends Object?>(TResult Function( _BookingDto value)?  $default,{required TResult orElse(),}){
final _that = this;
switch (_that) {
case _BookingDto() when $default != null:
return $default(_that);case _:
  return orElse();

}
}
/// A `switch`-like method, using callbacks.
///
/// Callbacks receives the raw object, upcasted.
/// It is equivalent to doing:
/// ```dart
/// switch (sealedClass) {
///   case final Subclass value:
///     return ...;
///   case final Subclass2 value:
///     return ...;
/// }
/// ```

@optionalTypeArgs TResult map<TResult extends Object?>(TResult Function( _BookingDto value)  $default,){
final _that = this;
switch (_that) {
case _BookingDto():
return $default(_that);case _:
  throw StateError('Unexpected subclass');

}
}
/// A variant of `map` that fallback to returning `null`.
///
/// It is equivalent to doing:
/// ```dart
/// switch (sealedClass) {
///   case final Subclass value:
///     return ...;
///   case _:
///     return null;
/// }
/// ```

@optionalTypeArgs TResult? mapOrNull<TResult extends Object?>(TResult? Function( _BookingDto value)?  $default,){
final _that = this;
switch (_that) {
case _BookingDto() when $default != null:
return $default(_that);case _:
  return null;

}
}
/// A variant of `when` that fallback to an `orElse` callback.
///
/// It is equivalent to doing:
/// ```dart
/// switch (sealedClass) {
///   case Subclass(:final field):
///     return ...;
///   case _:
///     return orElse();
/// }
/// ```

@optionalTypeArgs TResult maybeWhen<TResult extends Object?>(TResult Function( String id,  String reference,  String status, @JsonKey(name: 'property_id')  String propertyId, @JsonKey(name: 'property_name')  String propertyName, @JsonKey(name: 'property_address')  String? propertyAddress, @JsonKey(name: 'room_type_id')  String roomTypeId, @JsonKey(name: 'room_type_name')  String roomTypeName, @JsonKey(name: 'check_in')  String checkIn, @JsonKey(name: 'check_out')  String checkOut,  int nights,  int adults,  int children,  int infants,  int rooms, @JsonKey(name: 'guest_name')  String guestName, @JsonKey(name: 'guest_email')  String guestEmail, @JsonKey(name: 'guest_phone')  String guestPhone, @JsonKey(name: 'special_requests')  String? specialRequests, @JsonKey(name: 'accommodation_minor')  int accommodationMinor, @JsonKey(name: 'extra_guest_minor')  int extraGuestMinor, @JsonKey(name: 'cleaning_fee_minor')  int cleaningFeeMinor, @JsonKey(name: 'tax_minor')  int taxMinor, @JsonKey(name: 'platform_fee_minor')  int platformFeeMinor, @JsonKey(name: 'total_minor')  int totalMinor,  String currency, @JsonKey(name: 'cancellation_policy')  String cancellationPolicy, @JsonKey(name: 'created_at')  String? createdAt, @JsonKey(name: 'confirmed_at')  String? confirmedAt, @JsonKey(name: 'cancelled_at')  String? cancelledAt, @JsonKey(name: 'cancellation_reason')  String? cancellationReason, @JsonKey(name: 'invoice_number')  String? invoiceNumber, @JsonKey(name: 'hold_expires_in')  int? holdExpiresIn, @JsonKey(name: 'nightly_rates')  List<NightlyRateDto> nightlyRates,  BookingRefundDto? refund)?  $default,{required TResult orElse(),}) {final _that = this;
switch (_that) {
case _BookingDto() when $default != null:
return $default(_that.id,_that.reference,_that.status,_that.propertyId,_that.propertyName,_that.propertyAddress,_that.roomTypeId,_that.roomTypeName,_that.checkIn,_that.checkOut,_that.nights,_that.adults,_that.children,_that.infants,_that.rooms,_that.guestName,_that.guestEmail,_that.guestPhone,_that.specialRequests,_that.accommodationMinor,_that.extraGuestMinor,_that.cleaningFeeMinor,_that.taxMinor,_that.platformFeeMinor,_that.totalMinor,_that.currency,_that.cancellationPolicy,_that.createdAt,_that.confirmedAt,_that.cancelledAt,_that.cancellationReason,_that.invoiceNumber,_that.holdExpiresIn,_that.nightlyRates,_that.refund);case _:
  return orElse();

}
}
/// A `switch`-like method, using callbacks.
///
/// As opposed to `map`, this offers destructuring.
/// It is equivalent to doing:
/// ```dart
/// switch (sealedClass) {
///   case Subclass(:final field):
///     return ...;
///   case Subclass2(:final field2):
///     return ...;
/// }
/// ```

@optionalTypeArgs TResult when<TResult extends Object?>(TResult Function( String id,  String reference,  String status, @JsonKey(name: 'property_id')  String propertyId, @JsonKey(name: 'property_name')  String propertyName, @JsonKey(name: 'property_address')  String? propertyAddress, @JsonKey(name: 'room_type_id')  String roomTypeId, @JsonKey(name: 'room_type_name')  String roomTypeName, @JsonKey(name: 'check_in')  String checkIn, @JsonKey(name: 'check_out')  String checkOut,  int nights,  int adults,  int children,  int infants,  int rooms, @JsonKey(name: 'guest_name')  String guestName, @JsonKey(name: 'guest_email')  String guestEmail, @JsonKey(name: 'guest_phone')  String guestPhone, @JsonKey(name: 'special_requests')  String? specialRequests, @JsonKey(name: 'accommodation_minor')  int accommodationMinor, @JsonKey(name: 'extra_guest_minor')  int extraGuestMinor, @JsonKey(name: 'cleaning_fee_minor')  int cleaningFeeMinor, @JsonKey(name: 'tax_minor')  int taxMinor, @JsonKey(name: 'platform_fee_minor')  int platformFeeMinor, @JsonKey(name: 'total_minor')  int totalMinor,  String currency, @JsonKey(name: 'cancellation_policy')  String cancellationPolicy, @JsonKey(name: 'created_at')  String? createdAt, @JsonKey(name: 'confirmed_at')  String? confirmedAt, @JsonKey(name: 'cancelled_at')  String? cancelledAt, @JsonKey(name: 'cancellation_reason')  String? cancellationReason, @JsonKey(name: 'invoice_number')  String? invoiceNumber, @JsonKey(name: 'hold_expires_in')  int? holdExpiresIn, @JsonKey(name: 'nightly_rates')  List<NightlyRateDto> nightlyRates,  BookingRefundDto? refund)  $default,) {final _that = this;
switch (_that) {
case _BookingDto():
return $default(_that.id,_that.reference,_that.status,_that.propertyId,_that.propertyName,_that.propertyAddress,_that.roomTypeId,_that.roomTypeName,_that.checkIn,_that.checkOut,_that.nights,_that.adults,_that.children,_that.infants,_that.rooms,_that.guestName,_that.guestEmail,_that.guestPhone,_that.specialRequests,_that.accommodationMinor,_that.extraGuestMinor,_that.cleaningFeeMinor,_that.taxMinor,_that.platformFeeMinor,_that.totalMinor,_that.currency,_that.cancellationPolicy,_that.createdAt,_that.confirmedAt,_that.cancelledAt,_that.cancellationReason,_that.invoiceNumber,_that.holdExpiresIn,_that.nightlyRates,_that.refund);case _:
  throw StateError('Unexpected subclass');

}
}
/// A variant of `when` that fallback to returning `null`
///
/// It is equivalent to doing:
/// ```dart
/// switch (sealedClass) {
///   case Subclass(:final field):
///     return ...;
///   case _:
///     return null;
/// }
/// ```

@optionalTypeArgs TResult? whenOrNull<TResult extends Object?>(TResult? Function( String id,  String reference,  String status, @JsonKey(name: 'property_id')  String propertyId, @JsonKey(name: 'property_name')  String propertyName, @JsonKey(name: 'property_address')  String? propertyAddress, @JsonKey(name: 'room_type_id')  String roomTypeId, @JsonKey(name: 'room_type_name')  String roomTypeName, @JsonKey(name: 'check_in')  String checkIn, @JsonKey(name: 'check_out')  String checkOut,  int nights,  int adults,  int children,  int infants,  int rooms, @JsonKey(name: 'guest_name')  String guestName, @JsonKey(name: 'guest_email')  String guestEmail, @JsonKey(name: 'guest_phone')  String guestPhone, @JsonKey(name: 'special_requests')  String? specialRequests, @JsonKey(name: 'accommodation_minor')  int accommodationMinor, @JsonKey(name: 'extra_guest_minor')  int extraGuestMinor, @JsonKey(name: 'cleaning_fee_minor')  int cleaningFeeMinor, @JsonKey(name: 'tax_minor')  int taxMinor, @JsonKey(name: 'platform_fee_minor')  int platformFeeMinor, @JsonKey(name: 'total_minor')  int totalMinor,  String currency, @JsonKey(name: 'cancellation_policy')  String cancellationPolicy, @JsonKey(name: 'created_at')  String? createdAt, @JsonKey(name: 'confirmed_at')  String? confirmedAt, @JsonKey(name: 'cancelled_at')  String? cancelledAt, @JsonKey(name: 'cancellation_reason')  String? cancellationReason, @JsonKey(name: 'invoice_number')  String? invoiceNumber, @JsonKey(name: 'hold_expires_in')  int? holdExpiresIn, @JsonKey(name: 'nightly_rates')  List<NightlyRateDto> nightlyRates,  BookingRefundDto? refund)?  $default,) {final _that = this;
switch (_that) {
case _BookingDto() when $default != null:
return $default(_that.id,_that.reference,_that.status,_that.propertyId,_that.propertyName,_that.propertyAddress,_that.roomTypeId,_that.roomTypeName,_that.checkIn,_that.checkOut,_that.nights,_that.adults,_that.children,_that.infants,_that.rooms,_that.guestName,_that.guestEmail,_that.guestPhone,_that.specialRequests,_that.accommodationMinor,_that.extraGuestMinor,_that.cleaningFeeMinor,_that.taxMinor,_that.platformFeeMinor,_that.totalMinor,_that.currency,_that.cancellationPolicy,_that.createdAt,_that.confirmedAt,_that.cancelledAt,_that.cancellationReason,_that.invoiceNumber,_that.holdExpiresIn,_that.nightlyRates,_that.refund);case _:
  return null;

}
}

}

/// @nodoc
@JsonSerializable()

class _BookingDto implements BookingDto {
  const _BookingDto({required this.id, required this.reference, required this.status, @JsonKey(name: 'property_id') this.propertyId = '', @JsonKey(name: 'property_name') this.propertyName = '', @JsonKey(name: 'property_address') this.propertyAddress, @JsonKey(name: 'room_type_id') this.roomTypeId = '', @JsonKey(name: 'room_type_name') this.roomTypeName = '', @JsonKey(name: 'check_in') required this.checkIn, @JsonKey(name: 'check_out') required this.checkOut, this.nights = 0, this.adults = 1, this.children = 0, this.infants = 0, this.rooms = 1, @JsonKey(name: 'guest_name') this.guestName = '', @JsonKey(name: 'guest_email') this.guestEmail = '', @JsonKey(name: 'guest_phone') this.guestPhone = '', @JsonKey(name: 'special_requests') this.specialRequests, @JsonKey(name: 'accommodation_minor') this.accommodationMinor = 0, @JsonKey(name: 'extra_guest_minor') this.extraGuestMinor = 0, @JsonKey(name: 'cleaning_fee_minor') this.cleaningFeeMinor = 0, @JsonKey(name: 'tax_minor') this.taxMinor = 0, @JsonKey(name: 'platform_fee_minor') this.platformFeeMinor = 0, @JsonKey(name: 'total_minor') this.totalMinor = 0, this.currency = 'INR', @JsonKey(name: 'cancellation_policy') this.cancellationPolicy = 'moderate', @JsonKey(name: 'created_at') this.createdAt, @JsonKey(name: 'confirmed_at') this.confirmedAt, @JsonKey(name: 'cancelled_at') this.cancelledAt, @JsonKey(name: 'cancellation_reason') this.cancellationReason, @JsonKey(name: 'invoice_number') this.invoiceNumber, @JsonKey(name: 'hold_expires_in') this.holdExpiresIn, @JsonKey(name: 'nightly_rates') final  List<NightlyRateDto> nightlyRates = const <NightlyRateDto>[], this.refund}): _nightlyRates = nightlyRates;
  factory _BookingDto.fromJson(Map<String, dynamic> json) => _$BookingDtoFromJson(json);

@override final  String id;
@override final  String reference;
@override final  String status;
@override@JsonKey(name: 'property_id') final  String propertyId;
@override@JsonKey(name: 'property_name') final  String propertyName;
@override@JsonKey(name: 'property_address') final  String? propertyAddress;
@override@JsonKey(name: 'room_type_id') final  String roomTypeId;
@override@JsonKey(name: 'room_type_name') final  String roomTypeName;
@override@JsonKey(name: 'check_in') final  String checkIn;
@override@JsonKey(name: 'check_out') final  String checkOut;
@override@JsonKey() final  int nights;
@override@JsonKey() final  int adults;
@override@JsonKey() final  int children;
@override@JsonKey() final  int infants;
@override@JsonKey() final  int rooms;
@override@JsonKey(name: 'guest_name') final  String guestName;
@override@JsonKey(name: 'guest_email') final  String guestEmail;
@override@JsonKey(name: 'guest_phone') final  String guestPhone;
@override@JsonKey(name: 'special_requests') final  String? specialRequests;
@override@JsonKey(name: 'accommodation_minor') final  int accommodationMinor;
@override@JsonKey(name: 'extra_guest_minor') final  int extraGuestMinor;
@override@JsonKey(name: 'cleaning_fee_minor') final  int cleaningFeeMinor;
@override@JsonKey(name: 'tax_minor') final  int taxMinor;
@override@JsonKey(name: 'platform_fee_minor') final  int platformFeeMinor;
@override@JsonKey(name: 'total_minor') final  int totalMinor;
@override@JsonKey() final  String currency;
@override@JsonKey(name: 'cancellation_policy') final  String cancellationPolicy;
@override@JsonKey(name: 'created_at') final  String? createdAt;
@override@JsonKey(name: 'confirmed_at') final  String? confirmedAt;
@override@JsonKey(name: 'cancelled_at') final  String? cancelledAt;
@override@JsonKey(name: 'cancellation_reason') final  String? cancellationReason;
@override@JsonKey(name: 'invoice_number') final  String? invoiceNumber;
/// Seconds until the hold lapses and the rooms go back on sale. Present
/// only while `pending_payment`. Not decoration: a guest who misses it
/// loses the room.
@override@JsonKey(name: 'hold_expires_in') final  int? holdExpiresIn;
 final  List<NightlyRateDto> _nightlyRates;
@override@JsonKey(name: 'nightly_rates') List<NightlyRateDto> get nightlyRates {
  if (_nightlyRates is EqualUnmodifiableListView) return _nightlyRates;
  // ignore: implicit_dynamic_type
  return EqualUnmodifiableListView(_nightlyRates);
}

@override final  BookingRefundDto? refund;

/// Create a copy of BookingDto
/// with the given fields replaced by the non-null parameter values.
@override @JsonKey(includeFromJson: false, includeToJson: false)
@pragma('vm:prefer-inline')
_$BookingDtoCopyWith<_BookingDto> get copyWith => __$BookingDtoCopyWithImpl<_BookingDto>(this, _$identity);

@override
Map<String, dynamic> toJson() {
  return _$BookingDtoToJson(this, );
}

@override
bool operator ==(Object other) {
  return identical(this, other) || (other.runtimeType == runtimeType&&other is _BookingDto&&(identical(other.id, id) || other.id == id)&&(identical(other.reference, reference) || other.reference == reference)&&(identical(other.status, status) || other.status == status)&&(identical(other.propertyId, propertyId) || other.propertyId == propertyId)&&(identical(other.propertyName, propertyName) || other.propertyName == propertyName)&&(identical(other.propertyAddress, propertyAddress) || other.propertyAddress == propertyAddress)&&(identical(other.roomTypeId, roomTypeId) || other.roomTypeId == roomTypeId)&&(identical(other.roomTypeName, roomTypeName) || other.roomTypeName == roomTypeName)&&(identical(other.checkIn, checkIn) || other.checkIn == checkIn)&&(identical(other.checkOut, checkOut) || other.checkOut == checkOut)&&(identical(other.nights, nights) || other.nights == nights)&&(identical(other.adults, adults) || other.adults == adults)&&(identical(other.children, children) || other.children == children)&&(identical(other.infants, infants) || other.infants == infants)&&(identical(other.rooms, rooms) || other.rooms == rooms)&&(identical(other.guestName, guestName) || other.guestName == guestName)&&(identical(other.guestEmail, guestEmail) || other.guestEmail == guestEmail)&&(identical(other.guestPhone, guestPhone) || other.guestPhone == guestPhone)&&(identical(other.specialRequests, specialRequests) || other.specialRequests == specialRequests)&&(identical(other.accommodationMinor, accommodationMinor) || other.accommodationMinor == accommodationMinor)&&(identical(other.extraGuestMinor, extraGuestMinor) || other.extraGuestMinor == extraGuestMinor)&&(identical(other.cleaningFeeMinor, cleaningFeeMinor) || other.cleaningFeeMinor == cleaningFeeMinor)&&(identical(other.taxMinor, taxMinor) || other.taxMinor == taxMinor)&&(identical(other.platformFeeMinor, platformFeeMinor) || other.platformFeeMinor == platformFeeMinor)&&(identical(other.totalMinor, totalMinor) || other.totalMinor == totalMinor)&&(identical(other.currency, currency) || other.currency == currency)&&(identical(other.cancellationPolicy, cancellationPolicy) || other.cancellationPolicy == cancellationPolicy)&&(identical(other.createdAt, createdAt) || other.createdAt == createdAt)&&(identical(other.confirmedAt, confirmedAt) || other.confirmedAt == confirmedAt)&&(identical(other.cancelledAt, cancelledAt) || other.cancelledAt == cancelledAt)&&(identical(other.cancellationReason, cancellationReason) || other.cancellationReason == cancellationReason)&&(identical(other.invoiceNumber, invoiceNumber) || other.invoiceNumber == invoiceNumber)&&(identical(other.holdExpiresIn, holdExpiresIn) || other.holdExpiresIn == holdExpiresIn)&&const DeepCollectionEquality().equals(other._nightlyRates, _nightlyRates)&&(identical(other.refund, refund) || other.refund == refund));
}

@JsonKey(includeFromJson: false, includeToJson: false)
@override
int get hashCode => Object.hashAll([runtimeType,id,reference,status,propertyId,propertyName,propertyAddress,roomTypeId,roomTypeName,checkIn,checkOut,nights,adults,children,infants,rooms,guestName,guestEmail,guestPhone,specialRequests,accommodationMinor,extraGuestMinor,cleaningFeeMinor,taxMinor,platformFeeMinor,totalMinor,currency,cancellationPolicy,createdAt,confirmedAt,cancelledAt,cancellationReason,invoiceNumber,holdExpiresIn,const DeepCollectionEquality().hash(_nightlyRates),refund]);

@override
String toString() {
  return 'BookingDto(id: $id, reference: $reference, status: $status, propertyId: $propertyId, propertyName: $propertyName, propertyAddress: $propertyAddress, roomTypeId: $roomTypeId, roomTypeName: $roomTypeName, checkIn: $checkIn, checkOut: $checkOut, nights: $nights, adults: $adults, children: $children, infants: $infants, rooms: $rooms, guestName: $guestName, guestEmail: $guestEmail, guestPhone: $guestPhone, specialRequests: $specialRequests, accommodationMinor: $accommodationMinor, extraGuestMinor: $extraGuestMinor, cleaningFeeMinor: $cleaningFeeMinor, taxMinor: $taxMinor, platformFeeMinor: $platformFeeMinor, totalMinor: $totalMinor, currency: $currency, cancellationPolicy: $cancellationPolicy, createdAt: $createdAt, confirmedAt: $confirmedAt, cancelledAt: $cancelledAt, cancellationReason: $cancellationReason, invoiceNumber: $invoiceNumber, holdExpiresIn: $holdExpiresIn, nightlyRates: $nightlyRates, refund: $refund)';
}


}

/// @nodoc
abstract mixin class _$BookingDtoCopyWith<$Res> implements $BookingDtoCopyWith<$Res> {
  factory _$BookingDtoCopyWith(_BookingDto value, $Res Function(_BookingDto) _then) = __$BookingDtoCopyWithImpl;
@override @useResult
$Res call({
 String id, String reference, String status,@JsonKey(name: 'property_id') String propertyId,@JsonKey(name: 'property_name') String propertyName,@JsonKey(name: 'property_address') String? propertyAddress,@JsonKey(name: 'room_type_id') String roomTypeId,@JsonKey(name: 'room_type_name') String roomTypeName,@JsonKey(name: 'check_in') String checkIn,@JsonKey(name: 'check_out') String checkOut, int nights, int adults, int children, int infants, int rooms,@JsonKey(name: 'guest_name') String guestName,@JsonKey(name: 'guest_email') String guestEmail,@JsonKey(name: 'guest_phone') String guestPhone,@JsonKey(name: 'special_requests') String? specialRequests,@JsonKey(name: 'accommodation_minor') int accommodationMinor,@JsonKey(name: 'extra_guest_minor') int extraGuestMinor,@JsonKey(name: 'cleaning_fee_minor') int cleaningFeeMinor,@JsonKey(name: 'tax_minor') int taxMinor,@JsonKey(name: 'platform_fee_minor') int platformFeeMinor,@JsonKey(name: 'total_minor') int totalMinor, String currency,@JsonKey(name: 'cancellation_policy') String cancellationPolicy,@JsonKey(name: 'created_at') String? createdAt,@JsonKey(name: 'confirmed_at') String? confirmedAt,@JsonKey(name: 'cancelled_at') String? cancelledAt,@JsonKey(name: 'cancellation_reason') String? cancellationReason,@JsonKey(name: 'invoice_number') String? invoiceNumber,@JsonKey(name: 'hold_expires_in') int? holdExpiresIn,@JsonKey(name: 'nightly_rates') List<NightlyRateDto> nightlyRates, BookingRefundDto? refund
});


@override $BookingRefundDtoCopyWith<$Res>? get refund;

}
/// @nodoc
class __$BookingDtoCopyWithImpl<$Res>
    implements _$BookingDtoCopyWith<$Res> {
  __$BookingDtoCopyWithImpl(this._self, this._then);

  final _BookingDto _self;
  final $Res Function(_BookingDto) _then;

/// Create a copy of BookingDto
/// with the given fields replaced by the non-null parameter values.
@override @pragma('vm:prefer-inline') $Res call({Object? id = null,Object? reference = null,Object? status = null,Object? propertyId = null,Object? propertyName = null,Object? propertyAddress = freezed,Object? roomTypeId = null,Object? roomTypeName = null,Object? checkIn = null,Object? checkOut = null,Object? nights = null,Object? adults = null,Object? children = null,Object? infants = null,Object? rooms = null,Object? guestName = null,Object? guestEmail = null,Object? guestPhone = null,Object? specialRequests = freezed,Object? accommodationMinor = null,Object? extraGuestMinor = null,Object? cleaningFeeMinor = null,Object? taxMinor = null,Object? platformFeeMinor = null,Object? totalMinor = null,Object? currency = null,Object? cancellationPolicy = null,Object? createdAt = freezed,Object? confirmedAt = freezed,Object? cancelledAt = freezed,Object? cancellationReason = freezed,Object? invoiceNumber = freezed,Object? holdExpiresIn = freezed,Object? nightlyRates = null,Object? refund = freezed,}) {
  return _then(_BookingDto(
id: null == id ? _self.id : id // ignore: cast_nullable_to_non_nullable
as String,reference: null == reference ? _self.reference : reference // ignore: cast_nullable_to_non_nullable
as String,status: null == status ? _self.status : status // ignore: cast_nullable_to_non_nullable
as String,propertyId: null == propertyId ? _self.propertyId : propertyId // ignore: cast_nullable_to_non_nullable
as String,propertyName: null == propertyName ? _self.propertyName : propertyName // ignore: cast_nullable_to_non_nullable
as String,propertyAddress: freezed == propertyAddress ? _self.propertyAddress : propertyAddress // ignore: cast_nullable_to_non_nullable
as String?,roomTypeId: null == roomTypeId ? _self.roomTypeId : roomTypeId // ignore: cast_nullable_to_non_nullable
as String,roomTypeName: null == roomTypeName ? _self.roomTypeName : roomTypeName // ignore: cast_nullable_to_non_nullable
as String,checkIn: null == checkIn ? _self.checkIn : checkIn // ignore: cast_nullable_to_non_nullable
as String,checkOut: null == checkOut ? _self.checkOut : checkOut // ignore: cast_nullable_to_non_nullable
as String,nights: null == nights ? _self.nights : nights // ignore: cast_nullable_to_non_nullable
as int,adults: null == adults ? _self.adults : adults // ignore: cast_nullable_to_non_nullable
as int,children: null == children ? _self.children : children // ignore: cast_nullable_to_non_nullable
as int,infants: null == infants ? _self.infants : infants // ignore: cast_nullable_to_non_nullable
as int,rooms: null == rooms ? _self.rooms : rooms // ignore: cast_nullable_to_non_nullable
as int,guestName: null == guestName ? _self.guestName : guestName // ignore: cast_nullable_to_non_nullable
as String,guestEmail: null == guestEmail ? _self.guestEmail : guestEmail // ignore: cast_nullable_to_non_nullable
as String,guestPhone: null == guestPhone ? _self.guestPhone : guestPhone // ignore: cast_nullable_to_non_nullable
as String,specialRequests: freezed == specialRequests ? _self.specialRequests : specialRequests // ignore: cast_nullable_to_non_nullable
as String?,accommodationMinor: null == accommodationMinor ? _self.accommodationMinor : accommodationMinor // ignore: cast_nullable_to_non_nullable
as int,extraGuestMinor: null == extraGuestMinor ? _self.extraGuestMinor : extraGuestMinor // ignore: cast_nullable_to_non_nullable
as int,cleaningFeeMinor: null == cleaningFeeMinor ? _self.cleaningFeeMinor : cleaningFeeMinor // ignore: cast_nullable_to_non_nullable
as int,taxMinor: null == taxMinor ? _self.taxMinor : taxMinor // ignore: cast_nullable_to_non_nullable
as int,platformFeeMinor: null == platformFeeMinor ? _self.platformFeeMinor : platformFeeMinor // ignore: cast_nullable_to_non_nullable
as int,totalMinor: null == totalMinor ? _self.totalMinor : totalMinor // ignore: cast_nullable_to_non_nullable
as int,currency: null == currency ? _self.currency : currency // ignore: cast_nullable_to_non_nullable
as String,cancellationPolicy: null == cancellationPolicy ? _self.cancellationPolicy : cancellationPolicy // ignore: cast_nullable_to_non_nullable
as String,createdAt: freezed == createdAt ? _self.createdAt : createdAt // ignore: cast_nullable_to_non_nullable
as String?,confirmedAt: freezed == confirmedAt ? _self.confirmedAt : confirmedAt // ignore: cast_nullable_to_non_nullable
as String?,cancelledAt: freezed == cancelledAt ? _self.cancelledAt : cancelledAt // ignore: cast_nullable_to_non_nullable
as String?,cancellationReason: freezed == cancellationReason ? _self.cancellationReason : cancellationReason // ignore: cast_nullable_to_non_nullable
as String?,invoiceNumber: freezed == invoiceNumber ? _self.invoiceNumber : invoiceNumber // ignore: cast_nullable_to_non_nullable
as String?,holdExpiresIn: freezed == holdExpiresIn ? _self.holdExpiresIn : holdExpiresIn // ignore: cast_nullable_to_non_nullable
as int?,nightlyRates: null == nightlyRates ? _self._nightlyRates : nightlyRates // ignore: cast_nullable_to_non_nullable
as List<NightlyRateDto>,refund: freezed == refund ? _self.refund : refund // ignore: cast_nullable_to_non_nullable
as BookingRefundDto?,
  ));
}

/// Create a copy of BookingDto
/// with the given fields replaced by the non-null parameter values.
@override
@pragma('vm:prefer-inline')
$BookingRefundDtoCopyWith<$Res>? get refund {
    if (_self.refund == null) {
    return null;
  }

  return $BookingRefundDtoCopyWith<$Res>(_self.refund!, (value) {
    return _then(_self.copyWith(refund: value));
  });
}
}


/// @nodoc
mixin _$BookingListDto {

 List<BookingDto> get items;@JsonKey(name: 'next_cursor') String? get nextCursor; int? get total;
/// Create a copy of BookingListDto
/// with the given fields replaced by the non-null parameter values.
@JsonKey(includeFromJson: false, includeToJson: false)
@pragma('vm:prefer-inline')
$BookingListDtoCopyWith<BookingListDto> get copyWith => _$BookingListDtoCopyWithImpl<BookingListDto>(this as BookingListDto, _$identity);

  /// Serializes this BookingListDto to a JSON map.
  Map<String, dynamic> toJson();


@override
bool operator ==(Object other) {
  return identical(this, other) || (other.runtimeType == runtimeType&&other is BookingListDto&&const DeepCollectionEquality().equals(other.items, items)&&(identical(other.nextCursor, nextCursor) || other.nextCursor == nextCursor)&&(identical(other.total, total) || other.total == total));
}

@JsonKey(includeFromJson: false, includeToJson: false)
@override
int get hashCode => Object.hash(runtimeType,const DeepCollectionEquality().hash(items),nextCursor,total);

@override
String toString() {
  return 'BookingListDto(items: $items, nextCursor: $nextCursor, total: $total)';
}


}

/// @nodoc
abstract mixin class $BookingListDtoCopyWith<$Res>  {
  factory $BookingListDtoCopyWith(BookingListDto value, $Res Function(BookingListDto) _then) = _$BookingListDtoCopyWithImpl;
@useResult
$Res call({
 List<BookingDto> items,@JsonKey(name: 'next_cursor') String? nextCursor, int? total
});




}
/// @nodoc
class _$BookingListDtoCopyWithImpl<$Res>
    implements $BookingListDtoCopyWith<$Res> {
  _$BookingListDtoCopyWithImpl(this._self, this._then);

  final BookingListDto _self;
  final $Res Function(BookingListDto) _then;

/// Create a copy of BookingListDto
/// with the given fields replaced by the non-null parameter values.
@pragma('vm:prefer-inline') @override $Res call({Object? items = null,Object? nextCursor = freezed,Object? total = freezed,}) {
  return _then(_self.copyWith(
items: null == items ? _self.items : items // ignore: cast_nullable_to_non_nullable
as List<BookingDto>,nextCursor: freezed == nextCursor ? _self.nextCursor : nextCursor // ignore: cast_nullable_to_non_nullable
as String?,total: freezed == total ? _self.total : total // ignore: cast_nullable_to_non_nullable
as int?,
  ));
}

}


/// Adds pattern-matching-related methods to [BookingListDto].
extension BookingListDtoPatterns on BookingListDto {
/// A variant of `map` that fallback to returning `orElse`.
///
/// It is equivalent to doing:
/// ```dart
/// switch (sealedClass) {
///   case final Subclass value:
///     return ...;
///   case _:
///     return orElse();
/// }
/// ```

@optionalTypeArgs TResult maybeMap<TResult extends Object?>(TResult Function( _BookingListDto value)?  $default,{required TResult orElse(),}){
final _that = this;
switch (_that) {
case _BookingListDto() when $default != null:
return $default(_that);case _:
  return orElse();

}
}
/// A `switch`-like method, using callbacks.
///
/// Callbacks receives the raw object, upcasted.
/// It is equivalent to doing:
/// ```dart
/// switch (sealedClass) {
///   case final Subclass value:
///     return ...;
///   case final Subclass2 value:
///     return ...;
/// }
/// ```

@optionalTypeArgs TResult map<TResult extends Object?>(TResult Function( _BookingListDto value)  $default,){
final _that = this;
switch (_that) {
case _BookingListDto():
return $default(_that);case _:
  throw StateError('Unexpected subclass');

}
}
/// A variant of `map` that fallback to returning `null`.
///
/// It is equivalent to doing:
/// ```dart
/// switch (sealedClass) {
///   case final Subclass value:
///     return ...;
///   case _:
///     return null;
/// }
/// ```

@optionalTypeArgs TResult? mapOrNull<TResult extends Object?>(TResult? Function( _BookingListDto value)?  $default,){
final _that = this;
switch (_that) {
case _BookingListDto() when $default != null:
return $default(_that);case _:
  return null;

}
}
/// A variant of `when` that fallback to an `orElse` callback.
///
/// It is equivalent to doing:
/// ```dart
/// switch (sealedClass) {
///   case Subclass(:final field):
///     return ...;
///   case _:
///     return orElse();
/// }
/// ```

@optionalTypeArgs TResult maybeWhen<TResult extends Object?>(TResult Function( List<BookingDto> items, @JsonKey(name: 'next_cursor')  String? nextCursor,  int? total)?  $default,{required TResult orElse(),}) {final _that = this;
switch (_that) {
case _BookingListDto() when $default != null:
return $default(_that.items,_that.nextCursor,_that.total);case _:
  return orElse();

}
}
/// A `switch`-like method, using callbacks.
///
/// As opposed to `map`, this offers destructuring.
/// It is equivalent to doing:
/// ```dart
/// switch (sealedClass) {
///   case Subclass(:final field):
///     return ...;
///   case Subclass2(:final field2):
///     return ...;
/// }
/// ```

@optionalTypeArgs TResult when<TResult extends Object?>(TResult Function( List<BookingDto> items, @JsonKey(name: 'next_cursor')  String? nextCursor,  int? total)  $default,) {final _that = this;
switch (_that) {
case _BookingListDto():
return $default(_that.items,_that.nextCursor,_that.total);case _:
  throw StateError('Unexpected subclass');

}
}
/// A variant of `when` that fallback to returning `null`
///
/// It is equivalent to doing:
/// ```dart
/// switch (sealedClass) {
///   case Subclass(:final field):
///     return ...;
///   case _:
///     return null;
/// }
/// ```

@optionalTypeArgs TResult? whenOrNull<TResult extends Object?>(TResult? Function( List<BookingDto> items, @JsonKey(name: 'next_cursor')  String? nextCursor,  int? total)?  $default,) {final _that = this;
switch (_that) {
case _BookingListDto() when $default != null:
return $default(_that.items,_that.nextCursor,_that.total);case _:
  return null;

}
}

}

/// @nodoc
@JsonSerializable()

class _BookingListDto implements BookingListDto {
  const _BookingListDto({final  List<BookingDto> items = const <BookingDto>[], @JsonKey(name: 'next_cursor') this.nextCursor, this.total}): _items = items;
  factory _BookingListDto.fromJson(Map<String, dynamic> json) => _$BookingListDtoFromJson(json);

 final  List<BookingDto> _items;
@override@JsonKey() List<BookingDto> get items {
  if (_items is EqualUnmodifiableListView) return _items;
  // ignore: implicit_dynamic_type
  return EqualUnmodifiableListView(_items);
}

@override@JsonKey(name: 'next_cursor') final  String? nextCursor;
@override final  int? total;

/// Create a copy of BookingListDto
/// with the given fields replaced by the non-null parameter values.
@override @JsonKey(includeFromJson: false, includeToJson: false)
@pragma('vm:prefer-inline')
_$BookingListDtoCopyWith<_BookingListDto> get copyWith => __$BookingListDtoCopyWithImpl<_BookingListDto>(this, _$identity);

@override
Map<String, dynamic> toJson() {
  return _$BookingListDtoToJson(this, );
}

@override
bool operator ==(Object other) {
  return identical(this, other) || (other.runtimeType == runtimeType&&other is _BookingListDto&&const DeepCollectionEquality().equals(other._items, _items)&&(identical(other.nextCursor, nextCursor) || other.nextCursor == nextCursor)&&(identical(other.total, total) || other.total == total));
}

@JsonKey(includeFromJson: false, includeToJson: false)
@override
int get hashCode => Object.hash(runtimeType,const DeepCollectionEquality().hash(_items),nextCursor,total);

@override
String toString() {
  return 'BookingListDto(items: $items, nextCursor: $nextCursor, total: $total)';
}


}

/// @nodoc
abstract mixin class _$BookingListDtoCopyWith<$Res> implements $BookingListDtoCopyWith<$Res> {
  factory _$BookingListDtoCopyWith(_BookingListDto value, $Res Function(_BookingListDto) _then) = __$BookingListDtoCopyWithImpl;
@override @useResult
$Res call({
 List<BookingDto> items,@JsonKey(name: 'next_cursor') String? nextCursor, int? total
});




}
/// @nodoc
class __$BookingListDtoCopyWithImpl<$Res>
    implements _$BookingListDtoCopyWith<$Res> {
  __$BookingListDtoCopyWithImpl(this._self, this._then);

  final _BookingListDto _self;
  final $Res Function(_BookingListDto) _then;

/// Create a copy of BookingListDto
/// with the given fields replaced by the non-null parameter values.
@override @pragma('vm:prefer-inline') $Res call({Object? items = null,Object? nextCursor = freezed,Object? total = freezed,}) {
  return _then(_BookingListDto(
items: null == items ? _self._items : items // ignore: cast_nullable_to_non_nullable
as List<BookingDto>,nextCursor: freezed == nextCursor ? _self.nextCursor : nextCursor // ignore: cast_nullable_to_non_nullable
as String?,total: freezed == total ? _self.total : total // ignore: cast_nullable_to_non_nullable
as int?,
  ));
}


}


/// @nodoc
mixin _$RefundPreviewDto {

 String get policy;@JsonKey(name: 'hours_before_check_in') double get hoursBeforeCheckIn;@JsonKey(name: 'applied_percent') String get appliedPercent;@JsonKey(name: 'accommodation_minor') int get accommodationMinor;@JsonKey(name: 'cleaning_fee_minor') int get cleaningFeeMinor;@JsonKey(name: 'tax_minor') int get taxMinor;@JsonKey(name: 'total_minor') int get totalMinor;@JsonKey(name: 'vendor_retains_minor') int get vendorRetainsMinor; String get reason; String get currency; bool get cancellable;
/// Create a copy of RefundPreviewDto
/// with the given fields replaced by the non-null parameter values.
@JsonKey(includeFromJson: false, includeToJson: false)
@pragma('vm:prefer-inline')
$RefundPreviewDtoCopyWith<RefundPreviewDto> get copyWith => _$RefundPreviewDtoCopyWithImpl<RefundPreviewDto>(this as RefundPreviewDto, _$identity);

  /// Serializes this RefundPreviewDto to a JSON map.
  Map<String, dynamic> toJson();


@override
bool operator ==(Object other) {
  return identical(this, other) || (other.runtimeType == runtimeType&&other is RefundPreviewDto&&(identical(other.policy, policy) || other.policy == policy)&&(identical(other.hoursBeforeCheckIn, hoursBeforeCheckIn) || other.hoursBeforeCheckIn == hoursBeforeCheckIn)&&(identical(other.appliedPercent, appliedPercent) || other.appliedPercent == appliedPercent)&&(identical(other.accommodationMinor, accommodationMinor) || other.accommodationMinor == accommodationMinor)&&(identical(other.cleaningFeeMinor, cleaningFeeMinor) || other.cleaningFeeMinor == cleaningFeeMinor)&&(identical(other.taxMinor, taxMinor) || other.taxMinor == taxMinor)&&(identical(other.totalMinor, totalMinor) || other.totalMinor == totalMinor)&&(identical(other.vendorRetainsMinor, vendorRetainsMinor) || other.vendorRetainsMinor == vendorRetainsMinor)&&(identical(other.reason, reason) || other.reason == reason)&&(identical(other.currency, currency) || other.currency == currency)&&(identical(other.cancellable, cancellable) || other.cancellable == cancellable));
}

@JsonKey(includeFromJson: false, includeToJson: false)
@override
int get hashCode => Object.hash(runtimeType,policy,hoursBeforeCheckIn,appliedPercent,accommodationMinor,cleaningFeeMinor,taxMinor,totalMinor,vendorRetainsMinor,reason,currency,cancellable);

@override
String toString() {
  return 'RefundPreviewDto(policy: $policy, hoursBeforeCheckIn: $hoursBeforeCheckIn, appliedPercent: $appliedPercent, accommodationMinor: $accommodationMinor, cleaningFeeMinor: $cleaningFeeMinor, taxMinor: $taxMinor, totalMinor: $totalMinor, vendorRetainsMinor: $vendorRetainsMinor, reason: $reason, currency: $currency, cancellable: $cancellable)';
}


}

/// @nodoc
abstract mixin class $RefundPreviewDtoCopyWith<$Res>  {
  factory $RefundPreviewDtoCopyWith(RefundPreviewDto value, $Res Function(RefundPreviewDto) _then) = _$RefundPreviewDtoCopyWithImpl;
@useResult
$Res call({
 String policy,@JsonKey(name: 'hours_before_check_in') double hoursBeforeCheckIn,@JsonKey(name: 'applied_percent') String appliedPercent,@JsonKey(name: 'accommodation_minor') int accommodationMinor,@JsonKey(name: 'cleaning_fee_minor') int cleaningFeeMinor,@JsonKey(name: 'tax_minor') int taxMinor,@JsonKey(name: 'total_minor') int totalMinor,@JsonKey(name: 'vendor_retains_minor') int vendorRetainsMinor, String reason, String currency, bool cancellable
});




}
/// @nodoc
class _$RefundPreviewDtoCopyWithImpl<$Res>
    implements $RefundPreviewDtoCopyWith<$Res> {
  _$RefundPreviewDtoCopyWithImpl(this._self, this._then);

  final RefundPreviewDto _self;
  final $Res Function(RefundPreviewDto) _then;

/// Create a copy of RefundPreviewDto
/// with the given fields replaced by the non-null parameter values.
@pragma('vm:prefer-inline') @override $Res call({Object? policy = null,Object? hoursBeforeCheckIn = null,Object? appliedPercent = null,Object? accommodationMinor = null,Object? cleaningFeeMinor = null,Object? taxMinor = null,Object? totalMinor = null,Object? vendorRetainsMinor = null,Object? reason = null,Object? currency = null,Object? cancellable = null,}) {
  return _then(_self.copyWith(
policy: null == policy ? _self.policy : policy // ignore: cast_nullable_to_non_nullable
as String,hoursBeforeCheckIn: null == hoursBeforeCheckIn ? _self.hoursBeforeCheckIn : hoursBeforeCheckIn // ignore: cast_nullable_to_non_nullable
as double,appliedPercent: null == appliedPercent ? _self.appliedPercent : appliedPercent // ignore: cast_nullable_to_non_nullable
as String,accommodationMinor: null == accommodationMinor ? _self.accommodationMinor : accommodationMinor // ignore: cast_nullable_to_non_nullable
as int,cleaningFeeMinor: null == cleaningFeeMinor ? _self.cleaningFeeMinor : cleaningFeeMinor // ignore: cast_nullable_to_non_nullable
as int,taxMinor: null == taxMinor ? _self.taxMinor : taxMinor // ignore: cast_nullable_to_non_nullable
as int,totalMinor: null == totalMinor ? _self.totalMinor : totalMinor // ignore: cast_nullable_to_non_nullable
as int,vendorRetainsMinor: null == vendorRetainsMinor ? _self.vendorRetainsMinor : vendorRetainsMinor // ignore: cast_nullable_to_non_nullable
as int,reason: null == reason ? _self.reason : reason // ignore: cast_nullable_to_non_nullable
as String,currency: null == currency ? _self.currency : currency // ignore: cast_nullable_to_non_nullable
as String,cancellable: null == cancellable ? _self.cancellable : cancellable // ignore: cast_nullable_to_non_nullable
as bool,
  ));
}

}


/// Adds pattern-matching-related methods to [RefundPreviewDto].
extension RefundPreviewDtoPatterns on RefundPreviewDto {
/// A variant of `map` that fallback to returning `orElse`.
///
/// It is equivalent to doing:
/// ```dart
/// switch (sealedClass) {
///   case final Subclass value:
///     return ...;
///   case _:
///     return orElse();
/// }
/// ```

@optionalTypeArgs TResult maybeMap<TResult extends Object?>(TResult Function( _RefundPreviewDto value)?  $default,{required TResult orElse(),}){
final _that = this;
switch (_that) {
case _RefundPreviewDto() when $default != null:
return $default(_that);case _:
  return orElse();

}
}
/// A `switch`-like method, using callbacks.
///
/// Callbacks receives the raw object, upcasted.
/// It is equivalent to doing:
/// ```dart
/// switch (sealedClass) {
///   case final Subclass value:
///     return ...;
///   case final Subclass2 value:
///     return ...;
/// }
/// ```

@optionalTypeArgs TResult map<TResult extends Object?>(TResult Function( _RefundPreviewDto value)  $default,){
final _that = this;
switch (_that) {
case _RefundPreviewDto():
return $default(_that);case _:
  throw StateError('Unexpected subclass');

}
}
/// A variant of `map` that fallback to returning `null`.
///
/// It is equivalent to doing:
/// ```dart
/// switch (sealedClass) {
///   case final Subclass value:
///     return ...;
///   case _:
///     return null;
/// }
/// ```

@optionalTypeArgs TResult? mapOrNull<TResult extends Object?>(TResult? Function( _RefundPreviewDto value)?  $default,){
final _that = this;
switch (_that) {
case _RefundPreviewDto() when $default != null:
return $default(_that);case _:
  return null;

}
}
/// A variant of `when` that fallback to an `orElse` callback.
///
/// It is equivalent to doing:
/// ```dart
/// switch (sealedClass) {
///   case Subclass(:final field):
///     return ...;
///   case _:
///     return orElse();
/// }
/// ```

@optionalTypeArgs TResult maybeWhen<TResult extends Object?>(TResult Function( String policy, @JsonKey(name: 'hours_before_check_in')  double hoursBeforeCheckIn, @JsonKey(name: 'applied_percent')  String appliedPercent, @JsonKey(name: 'accommodation_minor')  int accommodationMinor, @JsonKey(name: 'cleaning_fee_minor')  int cleaningFeeMinor, @JsonKey(name: 'tax_minor')  int taxMinor, @JsonKey(name: 'total_minor')  int totalMinor, @JsonKey(name: 'vendor_retains_minor')  int vendorRetainsMinor,  String reason,  String currency,  bool cancellable)?  $default,{required TResult orElse(),}) {final _that = this;
switch (_that) {
case _RefundPreviewDto() when $default != null:
return $default(_that.policy,_that.hoursBeforeCheckIn,_that.appliedPercent,_that.accommodationMinor,_that.cleaningFeeMinor,_that.taxMinor,_that.totalMinor,_that.vendorRetainsMinor,_that.reason,_that.currency,_that.cancellable);case _:
  return orElse();

}
}
/// A `switch`-like method, using callbacks.
///
/// As opposed to `map`, this offers destructuring.
/// It is equivalent to doing:
/// ```dart
/// switch (sealedClass) {
///   case Subclass(:final field):
///     return ...;
///   case Subclass2(:final field2):
///     return ...;
/// }
/// ```

@optionalTypeArgs TResult when<TResult extends Object?>(TResult Function( String policy, @JsonKey(name: 'hours_before_check_in')  double hoursBeforeCheckIn, @JsonKey(name: 'applied_percent')  String appliedPercent, @JsonKey(name: 'accommodation_minor')  int accommodationMinor, @JsonKey(name: 'cleaning_fee_minor')  int cleaningFeeMinor, @JsonKey(name: 'tax_minor')  int taxMinor, @JsonKey(name: 'total_minor')  int totalMinor, @JsonKey(name: 'vendor_retains_minor')  int vendorRetainsMinor,  String reason,  String currency,  bool cancellable)  $default,) {final _that = this;
switch (_that) {
case _RefundPreviewDto():
return $default(_that.policy,_that.hoursBeforeCheckIn,_that.appliedPercent,_that.accommodationMinor,_that.cleaningFeeMinor,_that.taxMinor,_that.totalMinor,_that.vendorRetainsMinor,_that.reason,_that.currency,_that.cancellable);case _:
  throw StateError('Unexpected subclass');

}
}
/// A variant of `when` that fallback to returning `null`
///
/// It is equivalent to doing:
/// ```dart
/// switch (sealedClass) {
///   case Subclass(:final field):
///     return ...;
///   case _:
///     return null;
/// }
/// ```

@optionalTypeArgs TResult? whenOrNull<TResult extends Object?>(TResult? Function( String policy, @JsonKey(name: 'hours_before_check_in')  double hoursBeforeCheckIn, @JsonKey(name: 'applied_percent')  String appliedPercent, @JsonKey(name: 'accommodation_minor')  int accommodationMinor, @JsonKey(name: 'cleaning_fee_minor')  int cleaningFeeMinor, @JsonKey(name: 'tax_minor')  int taxMinor, @JsonKey(name: 'total_minor')  int totalMinor, @JsonKey(name: 'vendor_retains_minor')  int vendorRetainsMinor,  String reason,  String currency,  bool cancellable)?  $default,) {final _that = this;
switch (_that) {
case _RefundPreviewDto() when $default != null:
return $default(_that.policy,_that.hoursBeforeCheckIn,_that.appliedPercent,_that.accommodationMinor,_that.cleaningFeeMinor,_that.taxMinor,_that.totalMinor,_that.vendorRetainsMinor,_that.reason,_that.currency,_that.cancellable);case _:
  return null;

}
}

}

/// @nodoc
@JsonSerializable()

class _RefundPreviewDto implements RefundPreviewDto {
  const _RefundPreviewDto({this.policy = '', @JsonKey(name: 'hours_before_check_in') this.hoursBeforeCheckIn = 0.0, @JsonKey(name: 'applied_percent') this.appliedPercent = '0%', @JsonKey(name: 'accommodation_minor') this.accommodationMinor = 0, @JsonKey(name: 'cleaning_fee_minor') this.cleaningFeeMinor = 0, @JsonKey(name: 'tax_minor') this.taxMinor = 0, @JsonKey(name: 'total_minor') this.totalMinor = 0, @JsonKey(name: 'vendor_retains_minor') this.vendorRetainsMinor = 0, this.reason = '', this.currency = 'INR', this.cancellable = false});
  factory _RefundPreviewDto.fromJson(Map<String, dynamic> json) => _$RefundPreviewDtoFromJson(json);

@override@JsonKey() final  String policy;
@override@JsonKey(name: 'hours_before_check_in') final  double hoursBeforeCheckIn;
@override@JsonKey(name: 'applied_percent') final  String appliedPercent;
@override@JsonKey(name: 'accommodation_minor') final  int accommodationMinor;
@override@JsonKey(name: 'cleaning_fee_minor') final  int cleaningFeeMinor;
@override@JsonKey(name: 'tax_minor') final  int taxMinor;
@override@JsonKey(name: 'total_minor') final  int totalMinor;
@override@JsonKey(name: 'vendor_retains_minor') final  int vendorRetainsMinor;
@override@JsonKey() final  String reason;
@override@JsonKey() final  String currency;
@override@JsonKey() final  bool cancellable;

/// Create a copy of RefundPreviewDto
/// with the given fields replaced by the non-null parameter values.
@override @JsonKey(includeFromJson: false, includeToJson: false)
@pragma('vm:prefer-inline')
_$RefundPreviewDtoCopyWith<_RefundPreviewDto> get copyWith => __$RefundPreviewDtoCopyWithImpl<_RefundPreviewDto>(this, _$identity);

@override
Map<String, dynamic> toJson() {
  return _$RefundPreviewDtoToJson(this, );
}

@override
bool operator ==(Object other) {
  return identical(this, other) || (other.runtimeType == runtimeType&&other is _RefundPreviewDto&&(identical(other.policy, policy) || other.policy == policy)&&(identical(other.hoursBeforeCheckIn, hoursBeforeCheckIn) || other.hoursBeforeCheckIn == hoursBeforeCheckIn)&&(identical(other.appliedPercent, appliedPercent) || other.appliedPercent == appliedPercent)&&(identical(other.accommodationMinor, accommodationMinor) || other.accommodationMinor == accommodationMinor)&&(identical(other.cleaningFeeMinor, cleaningFeeMinor) || other.cleaningFeeMinor == cleaningFeeMinor)&&(identical(other.taxMinor, taxMinor) || other.taxMinor == taxMinor)&&(identical(other.totalMinor, totalMinor) || other.totalMinor == totalMinor)&&(identical(other.vendorRetainsMinor, vendorRetainsMinor) || other.vendorRetainsMinor == vendorRetainsMinor)&&(identical(other.reason, reason) || other.reason == reason)&&(identical(other.currency, currency) || other.currency == currency)&&(identical(other.cancellable, cancellable) || other.cancellable == cancellable));
}

@JsonKey(includeFromJson: false, includeToJson: false)
@override
int get hashCode => Object.hash(runtimeType,policy,hoursBeforeCheckIn,appliedPercent,accommodationMinor,cleaningFeeMinor,taxMinor,totalMinor,vendorRetainsMinor,reason,currency,cancellable);

@override
String toString() {
  return 'RefundPreviewDto(policy: $policy, hoursBeforeCheckIn: $hoursBeforeCheckIn, appliedPercent: $appliedPercent, accommodationMinor: $accommodationMinor, cleaningFeeMinor: $cleaningFeeMinor, taxMinor: $taxMinor, totalMinor: $totalMinor, vendorRetainsMinor: $vendorRetainsMinor, reason: $reason, currency: $currency, cancellable: $cancellable)';
}


}

/// @nodoc
abstract mixin class _$RefundPreviewDtoCopyWith<$Res> implements $RefundPreviewDtoCopyWith<$Res> {
  factory _$RefundPreviewDtoCopyWith(_RefundPreviewDto value, $Res Function(_RefundPreviewDto) _then) = __$RefundPreviewDtoCopyWithImpl;
@override @useResult
$Res call({
 String policy,@JsonKey(name: 'hours_before_check_in') double hoursBeforeCheckIn,@JsonKey(name: 'applied_percent') String appliedPercent,@JsonKey(name: 'accommodation_minor') int accommodationMinor,@JsonKey(name: 'cleaning_fee_minor') int cleaningFeeMinor,@JsonKey(name: 'tax_minor') int taxMinor,@JsonKey(name: 'total_minor') int totalMinor,@JsonKey(name: 'vendor_retains_minor') int vendorRetainsMinor, String reason, String currency, bool cancellable
});




}
/// @nodoc
class __$RefundPreviewDtoCopyWithImpl<$Res>
    implements _$RefundPreviewDtoCopyWith<$Res> {
  __$RefundPreviewDtoCopyWithImpl(this._self, this._then);

  final _RefundPreviewDto _self;
  final $Res Function(_RefundPreviewDto) _then;

/// Create a copy of RefundPreviewDto
/// with the given fields replaced by the non-null parameter values.
@override @pragma('vm:prefer-inline') $Res call({Object? policy = null,Object? hoursBeforeCheckIn = null,Object? appliedPercent = null,Object? accommodationMinor = null,Object? cleaningFeeMinor = null,Object? taxMinor = null,Object? totalMinor = null,Object? vendorRetainsMinor = null,Object? reason = null,Object? currency = null,Object? cancellable = null,}) {
  return _then(_RefundPreviewDto(
policy: null == policy ? _self.policy : policy // ignore: cast_nullable_to_non_nullable
as String,hoursBeforeCheckIn: null == hoursBeforeCheckIn ? _self.hoursBeforeCheckIn : hoursBeforeCheckIn // ignore: cast_nullable_to_non_nullable
as double,appliedPercent: null == appliedPercent ? _self.appliedPercent : appliedPercent // ignore: cast_nullable_to_non_nullable
as String,accommodationMinor: null == accommodationMinor ? _self.accommodationMinor : accommodationMinor // ignore: cast_nullable_to_non_nullable
as int,cleaningFeeMinor: null == cleaningFeeMinor ? _self.cleaningFeeMinor : cleaningFeeMinor // ignore: cast_nullable_to_non_nullable
as int,taxMinor: null == taxMinor ? _self.taxMinor : taxMinor // ignore: cast_nullable_to_non_nullable
as int,totalMinor: null == totalMinor ? _self.totalMinor : totalMinor // ignore: cast_nullable_to_non_nullable
as int,vendorRetainsMinor: null == vendorRetainsMinor ? _self.vendorRetainsMinor : vendorRetainsMinor // ignore: cast_nullable_to_non_nullable
as int,reason: null == reason ? _self.reason : reason // ignore: cast_nullable_to_non_nullable
as String,currency: null == currency ? _self.currency : currency // ignore: cast_nullable_to_non_nullable
as String,cancellable: null == cancellable ? _self.cancellable : cancellable // ignore: cast_nullable_to_non_nullable
as bool,
  ));
}


}


/// @nodoc
mixin _$CheckoutSessionDto {

@JsonKey(name: 'payment_id') String get paymentId;@JsonKey(name: 'gateway_order_id') String get gatewayOrderId;/// Razorpay's **public** merchant key. Authorises nothing on its own.
@JsonKey(name: 'key_id') String get keyId;@JsonKey(name: 'amount_minor') int get amountMinor; String get currency;@JsonKey(name: 'booking_reference') String get bookingReference;@JsonKey(name: 'prefill_name') String get prefillName;@JsonKey(name: 'prefill_email') String get prefillEmail;@JsonKey(name: 'prefill_contact') String get prefillContact;@JsonKey(name: 'property_name') String get propertyName;@JsonKey(name: 'expires_in') int? get expiresIn;
/// Create a copy of CheckoutSessionDto
/// with the given fields replaced by the non-null parameter values.
@JsonKey(includeFromJson: false, includeToJson: false)
@pragma('vm:prefer-inline')
$CheckoutSessionDtoCopyWith<CheckoutSessionDto> get copyWith => _$CheckoutSessionDtoCopyWithImpl<CheckoutSessionDto>(this as CheckoutSessionDto, _$identity);

  /// Serializes this CheckoutSessionDto to a JSON map.
  Map<String, dynamic> toJson();


@override
bool operator ==(Object other) {
  return identical(this, other) || (other.runtimeType == runtimeType&&other is CheckoutSessionDto&&(identical(other.paymentId, paymentId) || other.paymentId == paymentId)&&(identical(other.gatewayOrderId, gatewayOrderId) || other.gatewayOrderId == gatewayOrderId)&&(identical(other.keyId, keyId) || other.keyId == keyId)&&(identical(other.amountMinor, amountMinor) || other.amountMinor == amountMinor)&&(identical(other.currency, currency) || other.currency == currency)&&(identical(other.bookingReference, bookingReference) || other.bookingReference == bookingReference)&&(identical(other.prefillName, prefillName) || other.prefillName == prefillName)&&(identical(other.prefillEmail, prefillEmail) || other.prefillEmail == prefillEmail)&&(identical(other.prefillContact, prefillContact) || other.prefillContact == prefillContact)&&(identical(other.propertyName, propertyName) || other.propertyName == propertyName)&&(identical(other.expiresIn, expiresIn) || other.expiresIn == expiresIn));
}

@JsonKey(includeFromJson: false, includeToJson: false)
@override
int get hashCode => Object.hash(runtimeType,paymentId,gatewayOrderId,keyId,amountMinor,currency,bookingReference,prefillName,prefillEmail,prefillContact,propertyName,expiresIn);

@override
String toString() {
  return 'CheckoutSessionDto(paymentId: $paymentId, gatewayOrderId: $gatewayOrderId, keyId: $keyId, amountMinor: $amountMinor, currency: $currency, bookingReference: $bookingReference, prefillName: $prefillName, prefillEmail: $prefillEmail, prefillContact: $prefillContact, propertyName: $propertyName, expiresIn: $expiresIn)';
}


}

/// @nodoc
abstract mixin class $CheckoutSessionDtoCopyWith<$Res>  {
  factory $CheckoutSessionDtoCopyWith(CheckoutSessionDto value, $Res Function(CheckoutSessionDto) _then) = _$CheckoutSessionDtoCopyWithImpl;
@useResult
$Res call({
@JsonKey(name: 'payment_id') String paymentId,@JsonKey(name: 'gateway_order_id') String gatewayOrderId,@JsonKey(name: 'key_id') String keyId,@JsonKey(name: 'amount_minor') int amountMinor, String currency,@JsonKey(name: 'booking_reference') String bookingReference,@JsonKey(name: 'prefill_name') String prefillName,@JsonKey(name: 'prefill_email') String prefillEmail,@JsonKey(name: 'prefill_contact') String prefillContact,@JsonKey(name: 'property_name') String propertyName,@JsonKey(name: 'expires_in') int? expiresIn
});




}
/// @nodoc
class _$CheckoutSessionDtoCopyWithImpl<$Res>
    implements $CheckoutSessionDtoCopyWith<$Res> {
  _$CheckoutSessionDtoCopyWithImpl(this._self, this._then);

  final CheckoutSessionDto _self;
  final $Res Function(CheckoutSessionDto) _then;

/// Create a copy of CheckoutSessionDto
/// with the given fields replaced by the non-null parameter values.
@pragma('vm:prefer-inline') @override $Res call({Object? paymentId = null,Object? gatewayOrderId = null,Object? keyId = null,Object? amountMinor = null,Object? currency = null,Object? bookingReference = null,Object? prefillName = null,Object? prefillEmail = null,Object? prefillContact = null,Object? propertyName = null,Object? expiresIn = freezed,}) {
  return _then(_self.copyWith(
paymentId: null == paymentId ? _self.paymentId : paymentId // ignore: cast_nullable_to_non_nullable
as String,gatewayOrderId: null == gatewayOrderId ? _self.gatewayOrderId : gatewayOrderId // ignore: cast_nullable_to_non_nullable
as String,keyId: null == keyId ? _self.keyId : keyId // ignore: cast_nullable_to_non_nullable
as String,amountMinor: null == amountMinor ? _self.amountMinor : amountMinor // ignore: cast_nullable_to_non_nullable
as int,currency: null == currency ? _self.currency : currency // ignore: cast_nullable_to_non_nullable
as String,bookingReference: null == bookingReference ? _self.bookingReference : bookingReference // ignore: cast_nullable_to_non_nullable
as String,prefillName: null == prefillName ? _self.prefillName : prefillName // ignore: cast_nullable_to_non_nullable
as String,prefillEmail: null == prefillEmail ? _self.prefillEmail : prefillEmail // ignore: cast_nullable_to_non_nullable
as String,prefillContact: null == prefillContact ? _self.prefillContact : prefillContact // ignore: cast_nullable_to_non_nullable
as String,propertyName: null == propertyName ? _self.propertyName : propertyName // ignore: cast_nullable_to_non_nullable
as String,expiresIn: freezed == expiresIn ? _self.expiresIn : expiresIn // ignore: cast_nullable_to_non_nullable
as int?,
  ));
}

}


/// Adds pattern-matching-related methods to [CheckoutSessionDto].
extension CheckoutSessionDtoPatterns on CheckoutSessionDto {
/// A variant of `map` that fallback to returning `orElse`.
///
/// It is equivalent to doing:
/// ```dart
/// switch (sealedClass) {
///   case final Subclass value:
///     return ...;
///   case _:
///     return orElse();
/// }
/// ```

@optionalTypeArgs TResult maybeMap<TResult extends Object?>(TResult Function( _CheckoutSessionDto value)?  $default,{required TResult orElse(),}){
final _that = this;
switch (_that) {
case _CheckoutSessionDto() when $default != null:
return $default(_that);case _:
  return orElse();

}
}
/// A `switch`-like method, using callbacks.
///
/// Callbacks receives the raw object, upcasted.
/// It is equivalent to doing:
/// ```dart
/// switch (sealedClass) {
///   case final Subclass value:
///     return ...;
///   case final Subclass2 value:
///     return ...;
/// }
/// ```

@optionalTypeArgs TResult map<TResult extends Object?>(TResult Function( _CheckoutSessionDto value)  $default,){
final _that = this;
switch (_that) {
case _CheckoutSessionDto():
return $default(_that);case _:
  throw StateError('Unexpected subclass');

}
}
/// A variant of `map` that fallback to returning `null`.
///
/// It is equivalent to doing:
/// ```dart
/// switch (sealedClass) {
///   case final Subclass value:
///     return ...;
///   case _:
///     return null;
/// }
/// ```

@optionalTypeArgs TResult? mapOrNull<TResult extends Object?>(TResult? Function( _CheckoutSessionDto value)?  $default,){
final _that = this;
switch (_that) {
case _CheckoutSessionDto() when $default != null:
return $default(_that);case _:
  return null;

}
}
/// A variant of `when` that fallback to an `orElse` callback.
///
/// It is equivalent to doing:
/// ```dart
/// switch (sealedClass) {
///   case Subclass(:final field):
///     return ...;
///   case _:
///     return orElse();
/// }
/// ```

@optionalTypeArgs TResult maybeWhen<TResult extends Object?>(TResult Function(@JsonKey(name: 'payment_id')  String paymentId, @JsonKey(name: 'gateway_order_id')  String gatewayOrderId, @JsonKey(name: 'key_id')  String keyId, @JsonKey(name: 'amount_minor')  int amountMinor,  String currency, @JsonKey(name: 'booking_reference')  String bookingReference, @JsonKey(name: 'prefill_name')  String prefillName, @JsonKey(name: 'prefill_email')  String prefillEmail, @JsonKey(name: 'prefill_contact')  String prefillContact, @JsonKey(name: 'property_name')  String propertyName, @JsonKey(name: 'expires_in')  int? expiresIn)?  $default,{required TResult orElse(),}) {final _that = this;
switch (_that) {
case _CheckoutSessionDto() when $default != null:
return $default(_that.paymentId,_that.gatewayOrderId,_that.keyId,_that.amountMinor,_that.currency,_that.bookingReference,_that.prefillName,_that.prefillEmail,_that.prefillContact,_that.propertyName,_that.expiresIn);case _:
  return orElse();

}
}
/// A `switch`-like method, using callbacks.
///
/// As opposed to `map`, this offers destructuring.
/// It is equivalent to doing:
/// ```dart
/// switch (sealedClass) {
///   case Subclass(:final field):
///     return ...;
///   case Subclass2(:final field2):
///     return ...;
/// }
/// ```

@optionalTypeArgs TResult when<TResult extends Object?>(TResult Function(@JsonKey(name: 'payment_id')  String paymentId, @JsonKey(name: 'gateway_order_id')  String gatewayOrderId, @JsonKey(name: 'key_id')  String keyId, @JsonKey(name: 'amount_minor')  int amountMinor,  String currency, @JsonKey(name: 'booking_reference')  String bookingReference, @JsonKey(name: 'prefill_name')  String prefillName, @JsonKey(name: 'prefill_email')  String prefillEmail, @JsonKey(name: 'prefill_contact')  String prefillContact, @JsonKey(name: 'property_name')  String propertyName, @JsonKey(name: 'expires_in')  int? expiresIn)  $default,) {final _that = this;
switch (_that) {
case _CheckoutSessionDto():
return $default(_that.paymentId,_that.gatewayOrderId,_that.keyId,_that.amountMinor,_that.currency,_that.bookingReference,_that.prefillName,_that.prefillEmail,_that.prefillContact,_that.propertyName,_that.expiresIn);case _:
  throw StateError('Unexpected subclass');

}
}
/// A variant of `when` that fallback to returning `null`
///
/// It is equivalent to doing:
/// ```dart
/// switch (sealedClass) {
///   case Subclass(:final field):
///     return ...;
///   case _:
///     return null;
/// }
/// ```

@optionalTypeArgs TResult? whenOrNull<TResult extends Object?>(TResult? Function(@JsonKey(name: 'payment_id')  String paymentId, @JsonKey(name: 'gateway_order_id')  String gatewayOrderId, @JsonKey(name: 'key_id')  String keyId, @JsonKey(name: 'amount_minor')  int amountMinor,  String currency, @JsonKey(name: 'booking_reference')  String bookingReference, @JsonKey(name: 'prefill_name')  String prefillName, @JsonKey(name: 'prefill_email')  String prefillEmail, @JsonKey(name: 'prefill_contact')  String prefillContact, @JsonKey(name: 'property_name')  String propertyName, @JsonKey(name: 'expires_in')  int? expiresIn)?  $default,) {final _that = this;
switch (_that) {
case _CheckoutSessionDto() when $default != null:
return $default(_that.paymentId,_that.gatewayOrderId,_that.keyId,_that.amountMinor,_that.currency,_that.bookingReference,_that.prefillName,_that.prefillEmail,_that.prefillContact,_that.propertyName,_that.expiresIn);case _:
  return null;

}
}

}

/// @nodoc
@JsonSerializable()

class _CheckoutSessionDto implements CheckoutSessionDto {
  const _CheckoutSessionDto({@JsonKey(name: 'payment_id') required this.paymentId, @JsonKey(name: 'gateway_order_id') required this.gatewayOrderId, @JsonKey(name: 'key_id') this.keyId = '', @JsonKey(name: 'amount_minor') this.amountMinor = 0, this.currency = 'INR', @JsonKey(name: 'booking_reference') this.bookingReference = '', @JsonKey(name: 'prefill_name') this.prefillName = '', @JsonKey(name: 'prefill_email') this.prefillEmail = '', @JsonKey(name: 'prefill_contact') this.prefillContact = '', @JsonKey(name: 'property_name') this.propertyName = '', @JsonKey(name: 'expires_in') this.expiresIn});
  factory _CheckoutSessionDto.fromJson(Map<String, dynamic> json) => _$CheckoutSessionDtoFromJson(json);

@override@JsonKey(name: 'payment_id') final  String paymentId;
@override@JsonKey(name: 'gateway_order_id') final  String gatewayOrderId;
/// Razorpay's **public** merchant key. Authorises nothing on its own.
@override@JsonKey(name: 'key_id') final  String keyId;
@override@JsonKey(name: 'amount_minor') final  int amountMinor;
@override@JsonKey() final  String currency;
@override@JsonKey(name: 'booking_reference') final  String bookingReference;
@override@JsonKey(name: 'prefill_name') final  String prefillName;
@override@JsonKey(name: 'prefill_email') final  String prefillEmail;
@override@JsonKey(name: 'prefill_contact') final  String prefillContact;
@override@JsonKey(name: 'property_name') final  String propertyName;
@override@JsonKey(name: 'expires_in') final  int? expiresIn;

/// Create a copy of CheckoutSessionDto
/// with the given fields replaced by the non-null parameter values.
@override @JsonKey(includeFromJson: false, includeToJson: false)
@pragma('vm:prefer-inline')
_$CheckoutSessionDtoCopyWith<_CheckoutSessionDto> get copyWith => __$CheckoutSessionDtoCopyWithImpl<_CheckoutSessionDto>(this, _$identity);

@override
Map<String, dynamic> toJson() {
  return _$CheckoutSessionDtoToJson(this, );
}

@override
bool operator ==(Object other) {
  return identical(this, other) || (other.runtimeType == runtimeType&&other is _CheckoutSessionDto&&(identical(other.paymentId, paymentId) || other.paymentId == paymentId)&&(identical(other.gatewayOrderId, gatewayOrderId) || other.gatewayOrderId == gatewayOrderId)&&(identical(other.keyId, keyId) || other.keyId == keyId)&&(identical(other.amountMinor, amountMinor) || other.amountMinor == amountMinor)&&(identical(other.currency, currency) || other.currency == currency)&&(identical(other.bookingReference, bookingReference) || other.bookingReference == bookingReference)&&(identical(other.prefillName, prefillName) || other.prefillName == prefillName)&&(identical(other.prefillEmail, prefillEmail) || other.prefillEmail == prefillEmail)&&(identical(other.prefillContact, prefillContact) || other.prefillContact == prefillContact)&&(identical(other.propertyName, propertyName) || other.propertyName == propertyName)&&(identical(other.expiresIn, expiresIn) || other.expiresIn == expiresIn));
}

@JsonKey(includeFromJson: false, includeToJson: false)
@override
int get hashCode => Object.hash(runtimeType,paymentId,gatewayOrderId,keyId,amountMinor,currency,bookingReference,prefillName,prefillEmail,prefillContact,propertyName,expiresIn);

@override
String toString() {
  return 'CheckoutSessionDto(paymentId: $paymentId, gatewayOrderId: $gatewayOrderId, keyId: $keyId, amountMinor: $amountMinor, currency: $currency, bookingReference: $bookingReference, prefillName: $prefillName, prefillEmail: $prefillEmail, prefillContact: $prefillContact, propertyName: $propertyName, expiresIn: $expiresIn)';
}


}

/// @nodoc
abstract mixin class _$CheckoutSessionDtoCopyWith<$Res> implements $CheckoutSessionDtoCopyWith<$Res> {
  factory _$CheckoutSessionDtoCopyWith(_CheckoutSessionDto value, $Res Function(_CheckoutSessionDto) _then) = __$CheckoutSessionDtoCopyWithImpl;
@override @useResult
$Res call({
@JsonKey(name: 'payment_id') String paymentId,@JsonKey(name: 'gateway_order_id') String gatewayOrderId,@JsonKey(name: 'key_id') String keyId,@JsonKey(name: 'amount_minor') int amountMinor, String currency,@JsonKey(name: 'booking_reference') String bookingReference,@JsonKey(name: 'prefill_name') String prefillName,@JsonKey(name: 'prefill_email') String prefillEmail,@JsonKey(name: 'prefill_contact') String prefillContact,@JsonKey(name: 'property_name') String propertyName,@JsonKey(name: 'expires_in') int? expiresIn
});




}
/// @nodoc
class __$CheckoutSessionDtoCopyWithImpl<$Res>
    implements _$CheckoutSessionDtoCopyWith<$Res> {
  __$CheckoutSessionDtoCopyWithImpl(this._self, this._then);

  final _CheckoutSessionDto _self;
  final $Res Function(_CheckoutSessionDto) _then;

/// Create a copy of CheckoutSessionDto
/// with the given fields replaced by the non-null parameter values.
@override @pragma('vm:prefer-inline') $Res call({Object? paymentId = null,Object? gatewayOrderId = null,Object? keyId = null,Object? amountMinor = null,Object? currency = null,Object? bookingReference = null,Object? prefillName = null,Object? prefillEmail = null,Object? prefillContact = null,Object? propertyName = null,Object? expiresIn = freezed,}) {
  return _then(_CheckoutSessionDto(
paymentId: null == paymentId ? _self.paymentId : paymentId // ignore: cast_nullable_to_non_nullable
as String,gatewayOrderId: null == gatewayOrderId ? _self.gatewayOrderId : gatewayOrderId // ignore: cast_nullable_to_non_nullable
as String,keyId: null == keyId ? _self.keyId : keyId // ignore: cast_nullable_to_non_nullable
as String,amountMinor: null == amountMinor ? _self.amountMinor : amountMinor // ignore: cast_nullable_to_non_nullable
as int,currency: null == currency ? _self.currency : currency // ignore: cast_nullable_to_non_nullable
as String,bookingReference: null == bookingReference ? _self.bookingReference : bookingReference // ignore: cast_nullable_to_non_nullable
as String,prefillName: null == prefillName ? _self.prefillName : prefillName // ignore: cast_nullable_to_non_nullable
as String,prefillEmail: null == prefillEmail ? _self.prefillEmail : prefillEmail // ignore: cast_nullable_to_non_nullable
as String,prefillContact: null == prefillContact ? _self.prefillContact : prefillContact // ignore: cast_nullable_to_non_nullable
as String,propertyName: null == propertyName ? _self.propertyName : propertyName // ignore: cast_nullable_to_non_nullable
as String,expiresIn: freezed == expiresIn ? _self.expiresIn : expiresIn // ignore: cast_nullable_to_non_nullable
as int?,
  ));
}


}


/// @nodoc
mixin _$PaymentResultDto {

@JsonKey(name: 'payment_id') String get paymentId; String get status;@JsonKey(name: 'booking_id') String get bookingId;@JsonKey(name: 'booking_reference') String get bookingReference;@JsonKey(name: 'amount_minor') int get amountMinor; String get currency; String get method;@JsonKey(name: 'invoice_number') String? get invoiceNumber;@JsonKey(name: 'booking_status') String? get bookingStatus;
/// Create a copy of PaymentResultDto
/// with the given fields replaced by the non-null parameter values.
@JsonKey(includeFromJson: false, includeToJson: false)
@pragma('vm:prefer-inline')
$PaymentResultDtoCopyWith<PaymentResultDto> get copyWith => _$PaymentResultDtoCopyWithImpl<PaymentResultDto>(this as PaymentResultDto, _$identity);

  /// Serializes this PaymentResultDto to a JSON map.
  Map<String, dynamic> toJson();


@override
bool operator ==(Object other) {
  return identical(this, other) || (other.runtimeType == runtimeType&&other is PaymentResultDto&&(identical(other.paymentId, paymentId) || other.paymentId == paymentId)&&(identical(other.status, status) || other.status == status)&&(identical(other.bookingId, bookingId) || other.bookingId == bookingId)&&(identical(other.bookingReference, bookingReference) || other.bookingReference == bookingReference)&&(identical(other.amountMinor, amountMinor) || other.amountMinor == amountMinor)&&(identical(other.currency, currency) || other.currency == currency)&&(identical(other.method, method) || other.method == method)&&(identical(other.invoiceNumber, invoiceNumber) || other.invoiceNumber == invoiceNumber)&&(identical(other.bookingStatus, bookingStatus) || other.bookingStatus == bookingStatus));
}

@JsonKey(includeFromJson: false, includeToJson: false)
@override
int get hashCode => Object.hash(runtimeType,paymentId,status,bookingId,bookingReference,amountMinor,currency,method,invoiceNumber,bookingStatus);

@override
String toString() {
  return 'PaymentResultDto(paymentId: $paymentId, status: $status, bookingId: $bookingId, bookingReference: $bookingReference, amountMinor: $amountMinor, currency: $currency, method: $method, invoiceNumber: $invoiceNumber, bookingStatus: $bookingStatus)';
}


}

/// @nodoc
abstract mixin class $PaymentResultDtoCopyWith<$Res>  {
  factory $PaymentResultDtoCopyWith(PaymentResultDto value, $Res Function(PaymentResultDto) _then) = _$PaymentResultDtoCopyWithImpl;
@useResult
$Res call({
@JsonKey(name: 'payment_id') String paymentId, String status,@JsonKey(name: 'booking_id') String bookingId,@JsonKey(name: 'booking_reference') String bookingReference,@JsonKey(name: 'amount_minor') int amountMinor, String currency, String method,@JsonKey(name: 'invoice_number') String? invoiceNumber,@JsonKey(name: 'booking_status') String? bookingStatus
});




}
/// @nodoc
class _$PaymentResultDtoCopyWithImpl<$Res>
    implements $PaymentResultDtoCopyWith<$Res> {
  _$PaymentResultDtoCopyWithImpl(this._self, this._then);

  final PaymentResultDto _self;
  final $Res Function(PaymentResultDto) _then;

/// Create a copy of PaymentResultDto
/// with the given fields replaced by the non-null parameter values.
@pragma('vm:prefer-inline') @override $Res call({Object? paymentId = null,Object? status = null,Object? bookingId = null,Object? bookingReference = null,Object? amountMinor = null,Object? currency = null,Object? method = null,Object? invoiceNumber = freezed,Object? bookingStatus = freezed,}) {
  return _then(_self.copyWith(
paymentId: null == paymentId ? _self.paymentId : paymentId // ignore: cast_nullable_to_non_nullable
as String,status: null == status ? _self.status : status // ignore: cast_nullable_to_non_nullable
as String,bookingId: null == bookingId ? _self.bookingId : bookingId // ignore: cast_nullable_to_non_nullable
as String,bookingReference: null == bookingReference ? _self.bookingReference : bookingReference // ignore: cast_nullable_to_non_nullable
as String,amountMinor: null == amountMinor ? _self.amountMinor : amountMinor // ignore: cast_nullable_to_non_nullable
as int,currency: null == currency ? _self.currency : currency // ignore: cast_nullable_to_non_nullable
as String,method: null == method ? _self.method : method // ignore: cast_nullable_to_non_nullable
as String,invoiceNumber: freezed == invoiceNumber ? _self.invoiceNumber : invoiceNumber // ignore: cast_nullable_to_non_nullable
as String?,bookingStatus: freezed == bookingStatus ? _self.bookingStatus : bookingStatus // ignore: cast_nullable_to_non_nullable
as String?,
  ));
}

}


/// Adds pattern-matching-related methods to [PaymentResultDto].
extension PaymentResultDtoPatterns on PaymentResultDto {
/// A variant of `map` that fallback to returning `orElse`.
///
/// It is equivalent to doing:
/// ```dart
/// switch (sealedClass) {
///   case final Subclass value:
///     return ...;
///   case _:
///     return orElse();
/// }
/// ```

@optionalTypeArgs TResult maybeMap<TResult extends Object?>(TResult Function( _PaymentResultDto value)?  $default,{required TResult orElse(),}){
final _that = this;
switch (_that) {
case _PaymentResultDto() when $default != null:
return $default(_that);case _:
  return orElse();

}
}
/// A `switch`-like method, using callbacks.
///
/// Callbacks receives the raw object, upcasted.
/// It is equivalent to doing:
/// ```dart
/// switch (sealedClass) {
///   case final Subclass value:
///     return ...;
///   case final Subclass2 value:
///     return ...;
/// }
/// ```

@optionalTypeArgs TResult map<TResult extends Object?>(TResult Function( _PaymentResultDto value)  $default,){
final _that = this;
switch (_that) {
case _PaymentResultDto():
return $default(_that);case _:
  throw StateError('Unexpected subclass');

}
}
/// A variant of `map` that fallback to returning `null`.
///
/// It is equivalent to doing:
/// ```dart
/// switch (sealedClass) {
///   case final Subclass value:
///     return ...;
///   case _:
///     return null;
/// }
/// ```

@optionalTypeArgs TResult? mapOrNull<TResult extends Object?>(TResult? Function( _PaymentResultDto value)?  $default,){
final _that = this;
switch (_that) {
case _PaymentResultDto() when $default != null:
return $default(_that);case _:
  return null;

}
}
/// A variant of `when` that fallback to an `orElse` callback.
///
/// It is equivalent to doing:
/// ```dart
/// switch (sealedClass) {
///   case Subclass(:final field):
///     return ...;
///   case _:
///     return orElse();
/// }
/// ```

@optionalTypeArgs TResult maybeWhen<TResult extends Object?>(TResult Function(@JsonKey(name: 'payment_id')  String paymentId,  String status, @JsonKey(name: 'booking_id')  String bookingId, @JsonKey(name: 'booking_reference')  String bookingReference, @JsonKey(name: 'amount_minor')  int amountMinor,  String currency,  String method, @JsonKey(name: 'invoice_number')  String? invoiceNumber, @JsonKey(name: 'booking_status')  String? bookingStatus)?  $default,{required TResult orElse(),}) {final _that = this;
switch (_that) {
case _PaymentResultDto() when $default != null:
return $default(_that.paymentId,_that.status,_that.bookingId,_that.bookingReference,_that.amountMinor,_that.currency,_that.method,_that.invoiceNumber,_that.bookingStatus);case _:
  return orElse();

}
}
/// A `switch`-like method, using callbacks.
///
/// As opposed to `map`, this offers destructuring.
/// It is equivalent to doing:
/// ```dart
/// switch (sealedClass) {
///   case Subclass(:final field):
///     return ...;
///   case Subclass2(:final field2):
///     return ...;
/// }
/// ```

@optionalTypeArgs TResult when<TResult extends Object?>(TResult Function(@JsonKey(name: 'payment_id')  String paymentId,  String status, @JsonKey(name: 'booking_id')  String bookingId, @JsonKey(name: 'booking_reference')  String bookingReference, @JsonKey(name: 'amount_minor')  int amountMinor,  String currency,  String method, @JsonKey(name: 'invoice_number')  String? invoiceNumber, @JsonKey(name: 'booking_status')  String? bookingStatus)  $default,) {final _that = this;
switch (_that) {
case _PaymentResultDto():
return $default(_that.paymentId,_that.status,_that.bookingId,_that.bookingReference,_that.amountMinor,_that.currency,_that.method,_that.invoiceNumber,_that.bookingStatus);case _:
  throw StateError('Unexpected subclass');

}
}
/// A variant of `when` that fallback to returning `null`
///
/// It is equivalent to doing:
/// ```dart
/// switch (sealedClass) {
///   case Subclass(:final field):
///     return ...;
///   case _:
///     return null;
/// }
/// ```

@optionalTypeArgs TResult? whenOrNull<TResult extends Object?>(TResult? Function(@JsonKey(name: 'payment_id')  String paymentId,  String status, @JsonKey(name: 'booking_id')  String bookingId, @JsonKey(name: 'booking_reference')  String bookingReference, @JsonKey(name: 'amount_minor')  int amountMinor,  String currency,  String method, @JsonKey(name: 'invoice_number')  String? invoiceNumber, @JsonKey(name: 'booking_status')  String? bookingStatus)?  $default,) {final _that = this;
switch (_that) {
case _PaymentResultDto() when $default != null:
return $default(_that.paymentId,_that.status,_that.bookingId,_that.bookingReference,_that.amountMinor,_that.currency,_that.method,_that.invoiceNumber,_that.bookingStatus);case _:
  return null;

}
}

}

/// @nodoc
@JsonSerializable()

class _PaymentResultDto implements PaymentResultDto {
  const _PaymentResultDto({@JsonKey(name: 'payment_id') this.paymentId = '', this.status = '', @JsonKey(name: 'booking_id') this.bookingId = '', @JsonKey(name: 'booking_reference') this.bookingReference = '', @JsonKey(name: 'amount_minor') this.amountMinor = 0, this.currency = 'INR', this.method = 'unknown', @JsonKey(name: 'invoice_number') this.invoiceNumber, @JsonKey(name: 'booking_status') this.bookingStatus});
  factory _PaymentResultDto.fromJson(Map<String, dynamic> json) => _$PaymentResultDtoFromJson(json);

@override@JsonKey(name: 'payment_id') final  String paymentId;
@override@JsonKey() final  String status;
@override@JsonKey(name: 'booking_id') final  String bookingId;
@override@JsonKey(name: 'booking_reference') final  String bookingReference;
@override@JsonKey(name: 'amount_minor') final  int amountMinor;
@override@JsonKey() final  String currency;
@override@JsonKey() final  String method;
@override@JsonKey(name: 'invoice_number') final  String? invoiceNumber;
@override@JsonKey(name: 'booking_status') final  String? bookingStatus;

/// Create a copy of PaymentResultDto
/// with the given fields replaced by the non-null parameter values.
@override @JsonKey(includeFromJson: false, includeToJson: false)
@pragma('vm:prefer-inline')
_$PaymentResultDtoCopyWith<_PaymentResultDto> get copyWith => __$PaymentResultDtoCopyWithImpl<_PaymentResultDto>(this, _$identity);

@override
Map<String, dynamic> toJson() {
  return _$PaymentResultDtoToJson(this, );
}

@override
bool operator ==(Object other) {
  return identical(this, other) || (other.runtimeType == runtimeType&&other is _PaymentResultDto&&(identical(other.paymentId, paymentId) || other.paymentId == paymentId)&&(identical(other.status, status) || other.status == status)&&(identical(other.bookingId, bookingId) || other.bookingId == bookingId)&&(identical(other.bookingReference, bookingReference) || other.bookingReference == bookingReference)&&(identical(other.amountMinor, amountMinor) || other.amountMinor == amountMinor)&&(identical(other.currency, currency) || other.currency == currency)&&(identical(other.method, method) || other.method == method)&&(identical(other.invoiceNumber, invoiceNumber) || other.invoiceNumber == invoiceNumber)&&(identical(other.bookingStatus, bookingStatus) || other.bookingStatus == bookingStatus));
}

@JsonKey(includeFromJson: false, includeToJson: false)
@override
int get hashCode => Object.hash(runtimeType,paymentId,status,bookingId,bookingReference,amountMinor,currency,method,invoiceNumber,bookingStatus);

@override
String toString() {
  return 'PaymentResultDto(paymentId: $paymentId, status: $status, bookingId: $bookingId, bookingReference: $bookingReference, amountMinor: $amountMinor, currency: $currency, method: $method, invoiceNumber: $invoiceNumber, bookingStatus: $bookingStatus)';
}


}

/// @nodoc
abstract mixin class _$PaymentResultDtoCopyWith<$Res> implements $PaymentResultDtoCopyWith<$Res> {
  factory _$PaymentResultDtoCopyWith(_PaymentResultDto value, $Res Function(_PaymentResultDto) _then) = __$PaymentResultDtoCopyWithImpl;
@override @useResult
$Res call({
@JsonKey(name: 'payment_id') String paymentId, String status,@JsonKey(name: 'booking_id') String bookingId,@JsonKey(name: 'booking_reference') String bookingReference,@JsonKey(name: 'amount_minor') int amountMinor, String currency, String method,@JsonKey(name: 'invoice_number') String? invoiceNumber,@JsonKey(name: 'booking_status') String? bookingStatus
});




}
/// @nodoc
class __$PaymentResultDtoCopyWithImpl<$Res>
    implements _$PaymentResultDtoCopyWith<$Res> {
  __$PaymentResultDtoCopyWithImpl(this._self, this._then);

  final _PaymentResultDto _self;
  final $Res Function(_PaymentResultDto) _then;

/// Create a copy of PaymentResultDto
/// with the given fields replaced by the non-null parameter values.
@override @pragma('vm:prefer-inline') $Res call({Object? paymentId = null,Object? status = null,Object? bookingId = null,Object? bookingReference = null,Object? amountMinor = null,Object? currency = null,Object? method = null,Object? invoiceNumber = freezed,Object? bookingStatus = freezed,}) {
  return _then(_PaymentResultDto(
paymentId: null == paymentId ? _self.paymentId : paymentId // ignore: cast_nullable_to_non_nullable
as String,status: null == status ? _self.status : status // ignore: cast_nullable_to_non_nullable
as String,bookingId: null == bookingId ? _self.bookingId : bookingId // ignore: cast_nullable_to_non_nullable
as String,bookingReference: null == bookingReference ? _self.bookingReference : bookingReference // ignore: cast_nullable_to_non_nullable
as String,amountMinor: null == amountMinor ? _self.amountMinor : amountMinor // ignore: cast_nullable_to_non_nullable
as int,currency: null == currency ? _self.currency : currency // ignore: cast_nullable_to_non_nullable
as String,method: null == method ? _self.method : method // ignore: cast_nullable_to_non_nullable
as String,invoiceNumber: freezed == invoiceNumber ? _self.invoiceNumber : invoiceNumber // ignore: cast_nullable_to_non_nullable
as String?,bookingStatus: freezed == bookingStatus ? _self.bookingStatus : bookingStatus // ignore: cast_nullable_to_non_nullable
as String?,
  ));
}


}

// dart format on
