// GENERATED CODE - DO NOT MODIFY BY HAND
// coverage:ignore-file
// ignore_for_file: type=lint
// ignore_for_file: unused_element, deprecated_member_use, deprecated_member_use_from_same_package, use_function_type_syntax_for_parameters, unnecessary_const, avoid_init_to_null, invalid_override_different_default_values_named, prefer_expression_function_bodies, annotate_overrides, invalid_annotation_target, unnecessary_question_mark

part of 'property_models.dart';

// **************************************************************************
// FreezedGenerator
// **************************************************************************

// dart format off
T _$identity<T>(T value) => value;

/// @nodoc
mixin _$ImageDto {

 String get id; String get url; int get position;@JsonKey(name: 'is_cover') bool get isCover;@JsonKey(name: 'alt_text') String? get altText; String? get caption;
/// Create a copy of ImageDto
/// with the given fields replaced by the non-null parameter values.
@JsonKey(includeFromJson: false, includeToJson: false)
@pragma('vm:prefer-inline')
$ImageDtoCopyWith<ImageDto> get copyWith => _$ImageDtoCopyWithImpl<ImageDto>(this as ImageDto, _$identity);

  /// Serializes this ImageDto to a JSON map.
  Map<String, dynamic> toJson();


@override
bool operator ==(Object other) {
  return identical(this, other) || (other.runtimeType == runtimeType&&other is ImageDto&&(identical(other.id, id) || other.id == id)&&(identical(other.url, url) || other.url == url)&&(identical(other.position, position) || other.position == position)&&(identical(other.isCover, isCover) || other.isCover == isCover)&&(identical(other.altText, altText) || other.altText == altText)&&(identical(other.caption, caption) || other.caption == caption));
}

@JsonKey(includeFromJson: false, includeToJson: false)
@override
int get hashCode => Object.hash(runtimeType,id,url,position,isCover,altText,caption);

@override
String toString() {
  return 'ImageDto(id: $id, url: $url, position: $position, isCover: $isCover, altText: $altText, caption: $caption)';
}


}

/// @nodoc
abstract mixin class $ImageDtoCopyWith<$Res>  {
  factory $ImageDtoCopyWith(ImageDto value, $Res Function(ImageDto) _then) = _$ImageDtoCopyWithImpl;
@useResult
$Res call({
 String id, String url, int position,@JsonKey(name: 'is_cover') bool isCover,@JsonKey(name: 'alt_text') String? altText, String? caption
});




}
/// @nodoc
class _$ImageDtoCopyWithImpl<$Res>
    implements $ImageDtoCopyWith<$Res> {
  _$ImageDtoCopyWithImpl(this._self, this._then);

  final ImageDto _self;
  final $Res Function(ImageDto) _then;

/// Create a copy of ImageDto
/// with the given fields replaced by the non-null parameter values.
@pragma('vm:prefer-inline') @override $Res call({Object? id = null,Object? url = null,Object? position = null,Object? isCover = null,Object? altText = freezed,Object? caption = freezed,}) {
  return _then(_self.copyWith(
id: null == id ? _self.id : id // ignore: cast_nullable_to_non_nullable
as String,url: null == url ? _self.url : url // ignore: cast_nullable_to_non_nullable
as String,position: null == position ? _self.position : position // ignore: cast_nullable_to_non_nullable
as int,isCover: null == isCover ? _self.isCover : isCover // ignore: cast_nullable_to_non_nullable
as bool,altText: freezed == altText ? _self.altText : altText // ignore: cast_nullable_to_non_nullable
as String?,caption: freezed == caption ? _self.caption : caption // ignore: cast_nullable_to_non_nullable
as String?,
  ));
}

}


/// Adds pattern-matching-related methods to [ImageDto].
extension ImageDtoPatterns on ImageDto {
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

@optionalTypeArgs TResult maybeMap<TResult extends Object?>(TResult Function( _ImageDto value)?  $default,{required TResult orElse(),}){
final _that = this;
switch (_that) {
case _ImageDto() when $default != null:
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

@optionalTypeArgs TResult map<TResult extends Object?>(TResult Function( _ImageDto value)  $default,){
final _that = this;
switch (_that) {
case _ImageDto():
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

@optionalTypeArgs TResult? mapOrNull<TResult extends Object?>(TResult? Function( _ImageDto value)?  $default,){
final _that = this;
switch (_that) {
case _ImageDto() when $default != null:
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

@optionalTypeArgs TResult maybeWhen<TResult extends Object?>(TResult Function( String id,  String url,  int position, @JsonKey(name: 'is_cover')  bool isCover, @JsonKey(name: 'alt_text')  String? altText,  String? caption)?  $default,{required TResult orElse(),}) {final _that = this;
switch (_that) {
case _ImageDto() when $default != null:
return $default(_that.id,_that.url,_that.position,_that.isCover,_that.altText,_that.caption);case _:
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

@optionalTypeArgs TResult when<TResult extends Object?>(TResult Function( String id,  String url,  int position, @JsonKey(name: 'is_cover')  bool isCover, @JsonKey(name: 'alt_text')  String? altText,  String? caption)  $default,) {final _that = this;
switch (_that) {
case _ImageDto():
return $default(_that.id,_that.url,_that.position,_that.isCover,_that.altText,_that.caption);case _:
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

@optionalTypeArgs TResult? whenOrNull<TResult extends Object?>(TResult? Function( String id,  String url,  int position, @JsonKey(name: 'is_cover')  bool isCover, @JsonKey(name: 'alt_text')  String? altText,  String? caption)?  $default,) {final _that = this;
switch (_that) {
case _ImageDto() when $default != null:
return $default(_that.id,_that.url,_that.position,_that.isCover,_that.altText,_that.caption);case _:
  return null;

}
}

}

/// @nodoc
@JsonSerializable()

class _ImageDto implements ImageDto {
  const _ImageDto({required this.id, required this.url, this.position = 0, @JsonKey(name: 'is_cover') this.isCover = false, @JsonKey(name: 'alt_text') this.altText, this.caption});
  factory _ImageDto.fromJson(Map<String, dynamic> json) => _$ImageDtoFromJson(json);

@override final  String id;
@override final  String url;
@override@JsonKey() final  int position;
@override@JsonKey(name: 'is_cover') final  bool isCover;
@override@JsonKey(name: 'alt_text') final  String? altText;
@override final  String? caption;

/// Create a copy of ImageDto
/// with the given fields replaced by the non-null parameter values.
@override @JsonKey(includeFromJson: false, includeToJson: false)
@pragma('vm:prefer-inline')
_$ImageDtoCopyWith<_ImageDto> get copyWith => __$ImageDtoCopyWithImpl<_ImageDto>(this, _$identity);

@override
Map<String, dynamic> toJson() {
  return _$ImageDtoToJson(this, );
}

@override
bool operator ==(Object other) {
  return identical(this, other) || (other.runtimeType == runtimeType&&other is _ImageDto&&(identical(other.id, id) || other.id == id)&&(identical(other.url, url) || other.url == url)&&(identical(other.position, position) || other.position == position)&&(identical(other.isCover, isCover) || other.isCover == isCover)&&(identical(other.altText, altText) || other.altText == altText)&&(identical(other.caption, caption) || other.caption == caption));
}

@JsonKey(includeFromJson: false, includeToJson: false)
@override
int get hashCode => Object.hash(runtimeType,id,url,position,isCover,altText,caption);

@override
String toString() {
  return 'ImageDto(id: $id, url: $url, position: $position, isCover: $isCover, altText: $altText, caption: $caption)';
}


}

/// @nodoc
abstract mixin class _$ImageDtoCopyWith<$Res> implements $ImageDtoCopyWith<$Res> {
  factory _$ImageDtoCopyWith(_ImageDto value, $Res Function(_ImageDto) _then) = __$ImageDtoCopyWithImpl;
@override @useResult
$Res call({
 String id, String url, int position,@JsonKey(name: 'is_cover') bool isCover,@JsonKey(name: 'alt_text') String? altText, String? caption
});




}
/// @nodoc
class __$ImageDtoCopyWithImpl<$Res>
    implements _$ImageDtoCopyWith<$Res> {
  __$ImageDtoCopyWithImpl(this._self, this._then);

  final _ImageDto _self;
  final $Res Function(_ImageDto) _then;

/// Create a copy of ImageDto
/// with the given fields replaced by the non-null parameter values.
@override @pragma('vm:prefer-inline') $Res call({Object? id = null,Object? url = null,Object? position = null,Object? isCover = null,Object? altText = freezed,Object? caption = freezed,}) {
  return _then(_ImageDto(
id: null == id ? _self.id : id // ignore: cast_nullable_to_non_nullable
as String,url: null == url ? _self.url : url // ignore: cast_nullable_to_non_nullable
as String,position: null == position ? _self.position : position // ignore: cast_nullable_to_non_nullable
as int,isCover: null == isCover ? _self.isCover : isCover // ignore: cast_nullable_to_non_nullable
as bool,altText: freezed == altText ? _self.altText : altText // ignore: cast_nullable_to_non_nullable
as String?,caption: freezed == caption ? _self.caption : caption // ignore: cast_nullable_to_non_nullable
as String?,
  ));
}


}


/// @nodoc
mixin _$RoomTypeDto {

 String get id; String get name; String? get description;@JsonKey(name: 'bed_type') String get bedType;@JsonKey(name: 'max_adults') int get maxAdults;@JsonKey(name: 'max_children') int get maxChildren;@JsonKey(name: 'total_units') int get totalUnits;@JsonKey(name: 'size_sqft') int? get sizeSqft;@JsonKey(name: 'amenity_codes') List<String> get amenityCodes;@JsonKey(name: 'base_rate_minor') int get baseRateMinor; String get currency;@JsonKey(name: 'min_nights') int get minNights;/// Present only when the request carried dates. `null` means "not asked",
/// which is a different thing from "none left" and must not render as 0.
@JsonKey(name: 'units_available') int? get unitsAvailable;@JsonKey(name: 'quote_total_minor') int? get quoteTotalMinor;
/// Create a copy of RoomTypeDto
/// with the given fields replaced by the non-null parameter values.
@JsonKey(includeFromJson: false, includeToJson: false)
@pragma('vm:prefer-inline')
$RoomTypeDtoCopyWith<RoomTypeDto> get copyWith => _$RoomTypeDtoCopyWithImpl<RoomTypeDto>(this as RoomTypeDto, _$identity);

  /// Serializes this RoomTypeDto to a JSON map.
  Map<String, dynamic> toJson();


@override
bool operator ==(Object other) {
  return identical(this, other) || (other.runtimeType == runtimeType&&other is RoomTypeDto&&(identical(other.id, id) || other.id == id)&&(identical(other.name, name) || other.name == name)&&(identical(other.description, description) || other.description == description)&&(identical(other.bedType, bedType) || other.bedType == bedType)&&(identical(other.maxAdults, maxAdults) || other.maxAdults == maxAdults)&&(identical(other.maxChildren, maxChildren) || other.maxChildren == maxChildren)&&(identical(other.totalUnits, totalUnits) || other.totalUnits == totalUnits)&&(identical(other.sizeSqft, sizeSqft) || other.sizeSqft == sizeSqft)&&const DeepCollectionEquality().equals(other.amenityCodes, amenityCodes)&&(identical(other.baseRateMinor, baseRateMinor) || other.baseRateMinor == baseRateMinor)&&(identical(other.currency, currency) || other.currency == currency)&&(identical(other.minNights, minNights) || other.minNights == minNights)&&(identical(other.unitsAvailable, unitsAvailable) || other.unitsAvailable == unitsAvailable)&&(identical(other.quoteTotalMinor, quoteTotalMinor) || other.quoteTotalMinor == quoteTotalMinor));
}

@JsonKey(includeFromJson: false, includeToJson: false)
@override
int get hashCode => Object.hash(runtimeType,id,name,description,bedType,maxAdults,maxChildren,totalUnits,sizeSqft,const DeepCollectionEquality().hash(amenityCodes),baseRateMinor,currency,minNights,unitsAvailable,quoteTotalMinor);

@override
String toString() {
  return 'RoomTypeDto(id: $id, name: $name, description: $description, bedType: $bedType, maxAdults: $maxAdults, maxChildren: $maxChildren, totalUnits: $totalUnits, sizeSqft: $sizeSqft, amenityCodes: $amenityCodes, baseRateMinor: $baseRateMinor, currency: $currency, minNights: $minNights, unitsAvailable: $unitsAvailable, quoteTotalMinor: $quoteTotalMinor)';
}


}

/// @nodoc
abstract mixin class $RoomTypeDtoCopyWith<$Res>  {
  factory $RoomTypeDtoCopyWith(RoomTypeDto value, $Res Function(RoomTypeDto) _then) = _$RoomTypeDtoCopyWithImpl;
@useResult
$Res call({
 String id, String name, String? description,@JsonKey(name: 'bed_type') String bedType,@JsonKey(name: 'max_adults') int maxAdults,@JsonKey(name: 'max_children') int maxChildren,@JsonKey(name: 'total_units') int totalUnits,@JsonKey(name: 'size_sqft') int? sizeSqft,@JsonKey(name: 'amenity_codes') List<String> amenityCodes,@JsonKey(name: 'base_rate_minor') int baseRateMinor, String currency,@JsonKey(name: 'min_nights') int minNights,@JsonKey(name: 'units_available') int? unitsAvailable,@JsonKey(name: 'quote_total_minor') int? quoteTotalMinor
});




}
/// @nodoc
class _$RoomTypeDtoCopyWithImpl<$Res>
    implements $RoomTypeDtoCopyWith<$Res> {
  _$RoomTypeDtoCopyWithImpl(this._self, this._then);

  final RoomTypeDto _self;
  final $Res Function(RoomTypeDto) _then;

/// Create a copy of RoomTypeDto
/// with the given fields replaced by the non-null parameter values.
@pragma('vm:prefer-inline') @override $Res call({Object? id = null,Object? name = null,Object? description = freezed,Object? bedType = null,Object? maxAdults = null,Object? maxChildren = null,Object? totalUnits = null,Object? sizeSqft = freezed,Object? amenityCodes = null,Object? baseRateMinor = null,Object? currency = null,Object? minNights = null,Object? unitsAvailable = freezed,Object? quoteTotalMinor = freezed,}) {
  return _then(_self.copyWith(
id: null == id ? _self.id : id // ignore: cast_nullable_to_non_nullable
as String,name: null == name ? _self.name : name // ignore: cast_nullable_to_non_nullable
as String,description: freezed == description ? _self.description : description // ignore: cast_nullable_to_non_nullable
as String?,bedType: null == bedType ? _self.bedType : bedType // ignore: cast_nullable_to_non_nullable
as String,maxAdults: null == maxAdults ? _self.maxAdults : maxAdults // ignore: cast_nullable_to_non_nullable
as int,maxChildren: null == maxChildren ? _self.maxChildren : maxChildren // ignore: cast_nullable_to_non_nullable
as int,totalUnits: null == totalUnits ? _self.totalUnits : totalUnits // ignore: cast_nullable_to_non_nullable
as int,sizeSqft: freezed == sizeSqft ? _self.sizeSqft : sizeSqft // ignore: cast_nullable_to_non_nullable
as int?,amenityCodes: null == amenityCodes ? _self.amenityCodes : amenityCodes // ignore: cast_nullable_to_non_nullable
as List<String>,baseRateMinor: null == baseRateMinor ? _self.baseRateMinor : baseRateMinor // ignore: cast_nullable_to_non_nullable
as int,currency: null == currency ? _self.currency : currency // ignore: cast_nullable_to_non_nullable
as String,minNights: null == minNights ? _self.minNights : minNights // ignore: cast_nullable_to_non_nullable
as int,unitsAvailable: freezed == unitsAvailable ? _self.unitsAvailable : unitsAvailable // ignore: cast_nullable_to_non_nullable
as int?,quoteTotalMinor: freezed == quoteTotalMinor ? _self.quoteTotalMinor : quoteTotalMinor // ignore: cast_nullable_to_non_nullable
as int?,
  ));
}

}


/// Adds pattern-matching-related methods to [RoomTypeDto].
extension RoomTypeDtoPatterns on RoomTypeDto {
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

@optionalTypeArgs TResult maybeMap<TResult extends Object?>(TResult Function( _RoomTypeDto value)?  $default,{required TResult orElse(),}){
final _that = this;
switch (_that) {
case _RoomTypeDto() when $default != null:
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

@optionalTypeArgs TResult map<TResult extends Object?>(TResult Function( _RoomTypeDto value)  $default,){
final _that = this;
switch (_that) {
case _RoomTypeDto():
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

@optionalTypeArgs TResult? mapOrNull<TResult extends Object?>(TResult? Function( _RoomTypeDto value)?  $default,){
final _that = this;
switch (_that) {
case _RoomTypeDto() when $default != null:
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

@optionalTypeArgs TResult maybeWhen<TResult extends Object?>(TResult Function( String id,  String name,  String? description, @JsonKey(name: 'bed_type')  String bedType, @JsonKey(name: 'max_adults')  int maxAdults, @JsonKey(name: 'max_children')  int maxChildren, @JsonKey(name: 'total_units')  int totalUnits, @JsonKey(name: 'size_sqft')  int? sizeSqft, @JsonKey(name: 'amenity_codes')  List<String> amenityCodes, @JsonKey(name: 'base_rate_minor')  int baseRateMinor,  String currency, @JsonKey(name: 'min_nights')  int minNights, @JsonKey(name: 'units_available')  int? unitsAvailable, @JsonKey(name: 'quote_total_minor')  int? quoteTotalMinor)?  $default,{required TResult orElse(),}) {final _that = this;
switch (_that) {
case _RoomTypeDto() when $default != null:
return $default(_that.id,_that.name,_that.description,_that.bedType,_that.maxAdults,_that.maxChildren,_that.totalUnits,_that.sizeSqft,_that.amenityCodes,_that.baseRateMinor,_that.currency,_that.minNights,_that.unitsAvailable,_that.quoteTotalMinor);case _:
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

@optionalTypeArgs TResult when<TResult extends Object?>(TResult Function( String id,  String name,  String? description, @JsonKey(name: 'bed_type')  String bedType, @JsonKey(name: 'max_adults')  int maxAdults, @JsonKey(name: 'max_children')  int maxChildren, @JsonKey(name: 'total_units')  int totalUnits, @JsonKey(name: 'size_sqft')  int? sizeSqft, @JsonKey(name: 'amenity_codes')  List<String> amenityCodes, @JsonKey(name: 'base_rate_minor')  int baseRateMinor,  String currency, @JsonKey(name: 'min_nights')  int minNights, @JsonKey(name: 'units_available')  int? unitsAvailable, @JsonKey(name: 'quote_total_minor')  int? quoteTotalMinor)  $default,) {final _that = this;
switch (_that) {
case _RoomTypeDto():
return $default(_that.id,_that.name,_that.description,_that.bedType,_that.maxAdults,_that.maxChildren,_that.totalUnits,_that.sizeSqft,_that.amenityCodes,_that.baseRateMinor,_that.currency,_that.minNights,_that.unitsAvailable,_that.quoteTotalMinor);case _:
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

@optionalTypeArgs TResult? whenOrNull<TResult extends Object?>(TResult? Function( String id,  String name,  String? description, @JsonKey(name: 'bed_type')  String bedType, @JsonKey(name: 'max_adults')  int maxAdults, @JsonKey(name: 'max_children')  int maxChildren, @JsonKey(name: 'total_units')  int totalUnits, @JsonKey(name: 'size_sqft')  int? sizeSqft, @JsonKey(name: 'amenity_codes')  List<String> amenityCodes, @JsonKey(name: 'base_rate_minor')  int baseRateMinor,  String currency, @JsonKey(name: 'min_nights')  int minNights, @JsonKey(name: 'units_available')  int? unitsAvailable, @JsonKey(name: 'quote_total_minor')  int? quoteTotalMinor)?  $default,) {final _that = this;
switch (_that) {
case _RoomTypeDto() when $default != null:
return $default(_that.id,_that.name,_that.description,_that.bedType,_that.maxAdults,_that.maxChildren,_that.totalUnits,_that.sizeSqft,_that.amenityCodes,_that.baseRateMinor,_that.currency,_that.minNights,_that.unitsAvailable,_that.quoteTotalMinor);case _:
  return null;

}
}

}

/// @nodoc
@JsonSerializable()

class _RoomTypeDto implements RoomTypeDto {
  const _RoomTypeDto({required this.id, required this.name, this.description, @JsonKey(name: 'bed_type') this.bedType = '', @JsonKey(name: 'max_adults') this.maxAdults = 2, @JsonKey(name: 'max_children') this.maxChildren = 0, @JsonKey(name: 'total_units') this.totalUnits = 1, @JsonKey(name: 'size_sqft') this.sizeSqft, @JsonKey(name: 'amenity_codes') final  List<String> amenityCodes = const <String>[], @JsonKey(name: 'base_rate_minor') this.baseRateMinor = 0, this.currency = 'INR', @JsonKey(name: 'min_nights') this.minNights = 1, @JsonKey(name: 'units_available') this.unitsAvailable, @JsonKey(name: 'quote_total_minor') this.quoteTotalMinor}): _amenityCodes = amenityCodes;
  factory _RoomTypeDto.fromJson(Map<String, dynamic> json) => _$RoomTypeDtoFromJson(json);

@override final  String id;
@override final  String name;
@override final  String? description;
@override@JsonKey(name: 'bed_type') final  String bedType;
@override@JsonKey(name: 'max_adults') final  int maxAdults;
@override@JsonKey(name: 'max_children') final  int maxChildren;
@override@JsonKey(name: 'total_units') final  int totalUnits;
@override@JsonKey(name: 'size_sqft') final  int? sizeSqft;
 final  List<String> _amenityCodes;
@override@JsonKey(name: 'amenity_codes') List<String> get amenityCodes {
  if (_amenityCodes is EqualUnmodifiableListView) return _amenityCodes;
  // ignore: implicit_dynamic_type
  return EqualUnmodifiableListView(_amenityCodes);
}

@override@JsonKey(name: 'base_rate_minor') final  int baseRateMinor;
@override@JsonKey() final  String currency;
@override@JsonKey(name: 'min_nights') final  int minNights;
/// Present only when the request carried dates. `null` means "not asked",
/// which is a different thing from "none left" and must not render as 0.
@override@JsonKey(name: 'units_available') final  int? unitsAvailable;
@override@JsonKey(name: 'quote_total_minor') final  int? quoteTotalMinor;

/// Create a copy of RoomTypeDto
/// with the given fields replaced by the non-null parameter values.
@override @JsonKey(includeFromJson: false, includeToJson: false)
@pragma('vm:prefer-inline')
_$RoomTypeDtoCopyWith<_RoomTypeDto> get copyWith => __$RoomTypeDtoCopyWithImpl<_RoomTypeDto>(this, _$identity);

@override
Map<String, dynamic> toJson() {
  return _$RoomTypeDtoToJson(this, );
}

@override
bool operator ==(Object other) {
  return identical(this, other) || (other.runtimeType == runtimeType&&other is _RoomTypeDto&&(identical(other.id, id) || other.id == id)&&(identical(other.name, name) || other.name == name)&&(identical(other.description, description) || other.description == description)&&(identical(other.bedType, bedType) || other.bedType == bedType)&&(identical(other.maxAdults, maxAdults) || other.maxAdults == maxAdults)&&(identical(other.maxChildren, maxChildren) || other.maxChildren == maxChildren)&&(identical(other.totalUnits, totalUnits) || other.totalUnits == totalUnits)&&(identical(other.sizeSqft, sizeSqft) || other.sizeSqft == sizeSqft)&&const DeepCollectionEquality().equals(other._amenityCodes, _amenityCodes)&&(identical(other.baseRateMinor, baseRateMinor) || other.baseRateMinor == baseRateMinor)&&(identical(other.currency, currency) || other.currency == currency)&&(identical(other.minNights, minNights) || other.minNights == minNights)&&(identical(other.unitsAvailable, unitsAvailable) || other.unitsAvailable == unitsAvailable)&&(identical(other.quoteTotalMinor, quoteTotalMinor) || other.quoteTotalMinor == quoteTotalMinor));
}

@JsonKey(includeFromJson: false, includeToJson: false)
@override
int get hashCode => Object.hash(runtimeType,id,name,description,bedType,maxAdults,maxChildren,totalUnits,sizeSqft,const DeepCollectionEquality().hash(_amenityCodes),baseRateMinor,currency,minNights,unitsAvailable,quoteTotalMinor);

@override
String toString() {
  return 'RoomTypeDto(id: $id, name: $name, description: $description, bedType: $bedType, maxAdults: $maxAdults, maxChildren: $maxChildren, totalUnits: $totalUnits, sizeSqft: $sizeSqft, amenityCodes: $amenityCodes, baseRateMinor: $baseRateMinor, currency: $currency, minNights: $minNights, unitsAvailable: $unitsAvailable, quoteTotalMinor: $quoteTotalMinor)';
}


}

/// @nodoc
abstract mixin class _$RoomTypeDtoCopyWith<$Res> implements $RoomTypeDtoCopyWith<$Res> {
  factory _$RoomTypeDtoCopyWith(_RoomTypeDto value, $Res Function(_RoomTypeDto) _then) = __$RoomTypeDtoCopyWithImpl;
@override @useResult
$Res call({
 String id, String name, String? description,@JsonKey(name: 'bed_type') String bedType,@JsonKey(name: 'max_adults') int maxAdults,@JsonKey(name: 'max_children') int maxChildren,@JsonKey(name: 'total_units') int totalUnits,@JsonKey(name: 'size_sqft') int? sizeSqft,@JsonKey(name: 'amenity_codes') List<String> amenityCodes,@JsonKey(name: 'base_rate_minor') int baseRateMinor, String currency,@JsonKey(name: 'min_nights') int minNights,@JsonKey(name: 'units_available') int? unitsAvailable,@JsonKey(name: 'quote_total_minor') int? quoteTotalMinor
});




}
/// @nodoc
class __$RoomTypeDtoCopyWithImpl<$Res>
    implements _$RoomTypeDtoCopyWith<$Res> {
  __$RoomTypeDtoCopyWithImpl(this._self, this._then);

  final _RoomTypeDto _self;
  final $Res Function(_RoomTypeDto) _then;

/// Create a copy of RoomTypeDto
/// with the given fields replaced by the non-null parameter values.
@override @pragma('vm:prefer-inline') $Res call({Object? id = null,Object? name = null,Object? description = freezed,Object? bedType = null,Object? maxAdults = null,Object? maxChildren = null,Object? totalUnits = null,Object? sizeSqft = freezed,Object? amenityCodes = null,Object? baseRateMinor = null,Object? currency = null,Object? minNights = null,Object? unitsAvailable = freezed,Object? quoteTotalMinor = freezed,}) {
  return _then(_RoomTypeDto(
id: null == id ? _self.id : id // ignore: cast_nullable_to_non_nullable
as String,name: null == name ? _self.name : name // ignore: cast_nullable_to_non_nullable
as String,description: freezed == description ? _self.description : description // ignore: cast_nullable_to_non_nullable
as String?,bedType: null == bedType ? _self.bedType : bedType // ignore: cast_nullable_to_non_nullable
as String,maxAdults: null == maxAdults ? _self.maxAdults : maxAdults // ignore: cast_nullable_to_non_nullable
as int,maxChildren: null == maxChildren ? _self.maxChildren : maxChildren // ignore: cast_nullable_to_non_nullable
as int,totalUnits: null == totalUnits ? _self.totalUnits : totalUnits // ignore: cast_nullable_to_non_nullable
as int,sizeSqft: freezed == sizeSqft ? _self.sizeSqft : sizeSqft // ignore: cast_nullable_to_non_nullable
as int?,amenityCodes: null == amenityCodes ? _self._amenityCodes : amenityCodes // ignore: cast_nullable_to_non_nullable
as List<String>,baseRateMinor: null == baseRateMinor ? _self.baseRateMinor : baseRateMinor // ignore: cast_nullable_to_non_nullable
as int,currency: null == currency ? _self.currency : currency // ignore: cast_nullable_to_non_nullable
as String,minNights: null == minNights ? _self.minNights : minNights // ignore: cast_nullable_to_non_nullable
as int,unitsAvailable: freezed == unitsAvailable ? _self.unitsAvailable : unitsAvailable // ignore: cast_nullable_to_non_nullable
as int?,quoteTotalMinor: freezed == quoteTotalMinor ? _self.quoteTotalMinor : quoteTotalMinor // ignore: cast_nullable_to_non_nullable
as int?,
  ));
}


}


/// @nodoc
mixin _$PropertyDto {

 String get id; String get slug; String get name;@JsonKey(name: 'property_type') String get propertyType; String get description; String get address; String get city; String? get state;@JsonKey(name: 'country_code') String get countryCode; double? get latitude; double? get longitude;/// The pin is fuzzed until a booking is confirmed. Not a bug to "fix":
/// publishing an exact address tells anyone where an unoccupied home is.
@JsonKey(name: 'location_is_approximate') bool get locationIsApproximate;@JsonKey(name: 'amenity_codes') List<String> get amenityCodes; List<ImageDto> get images;@JsonKey(name: 'room_types') List<RoomTypeDto> get roomTypes;@JsonKey(name: 'cancellation_policy') String get cancellationPolicy;@JsonKey(name: 'check_in_from') String get checkInFrom;@JsonKey(name: 'check_out_by') String get checkOutBy;@JsonKey(name: 'house_rules') List<String> get houseRules;@JsonKey(name: 'instant_booking') bool get instantBooking;@JsonKey(name: 'review_average') double get reviewAverage;@JsonKey(name: 'review_count') int get reviewCount; String get currency;@JsonKey(name: 'vendor_id') String get vendorId;
/// Create a copy of PropertyDto
/// with the given fields replaced by the non-null parameter values.
@JsonKey(includeFromJson: false, includeToJson: false)
@pragma('vm:prefer-inline')
$PropertyDtoCopyWith<PropertyDto> get copyWith => _$PropertyDtoCopyWithImpl<PropertyDto>(this as PropertyDto, _$identity);

  /// Serializes this PropertyDto to a JSON map.
  Map<String, dynamic> toJson();


@override
bool operator ==(Object other) {
  return identical(this, other) || (other.runtimeType == runtimeType&&other is PropertyDto&&(identical(other.id, id) || other.id == id)&&(identical(other.slug, slug) || other.slug == slug)&&(identical(other.name, name) || other.name == name)&&(identical(other.propertyType, propertyType) || other.propertyType == propertyType)&&(identical(other.description, description) || other.description == description)&&(identical(other.address, address) || other.address == address)&&(identical(other.city, city) || other.city == city)&&(identical(other.state, state) || other.state == state)&&(identical(other.countryCode, countryCode) || other.countryCode == countryCode)&&(identical(other.latitude, latitude) || other.latitude == latitude)&&(identical(other.longitude, longitude) || other.longitude == longitude)&&(identical(other.locationIsApproximate, locationIsApproximate) || other.locationIsApproximate == locationIsApproximate)&&const DeepCollectionEquality().equals(other.amenityCodes, amenityCodes)&&const DeepCollectionEquality().equals(other.images, images)&&const DeepCollectionEquality().equals(other.roomTypes, roomTypes)&&(identical(other.cancellationPolicy, cancellationPolicy) || other.cancellationPolicy == cancellationPolicy)&&(identical(other.checkInFrom, checkInFrom) || other.checkInFrom == checkInFrom)&&(identical(other.checkOutBy, checkOutBy) || other.checkOutBy == checkOutBy)&&const DeepCollectionEquality().equals(other.houseRules, houseRules)&&(identical(other.instantBooking, instantBooking) || other.instantBooking == instantBooking)&&(identical(other.reviewAverage, reviewAverage) || other.reviewAverage == reviewAverage)&&(identical(other.reviewCount, reviewCount) || other.reviewCount == reviewCount)&&(identical(other.currency, currency) || other.currency == currency)&&(identical(other.vendorId, vendorId) || other.vendorId == vendorId));
}

@JsonKey(includeFromJson: false, includeToJson: false)
@override
int get hashCode => Object.hashAll([runtimeType,id,slug,name,propertyType,description,address,city,state,countryCode,latitude,longitude,locationIsApproximate,const DeepCollectionEquality().hash(amenityCodes),const DeepCollectionEquality().hash(images),const DeepCollectionEquality().hash(roomTypes),cancellationPolicy,checkInFrom,checkOutBy,const DeepCollectionEquality().hash(houseRules),instantBooking,reviewAverage,reviewCount,currency,vendorId]);

@override
String toString() {
  return 'PropertyDto(id: $id, slug: $slug, name: $name, propertyType: $propertyType, description: $description, address: $address, city: $city, state: $state, countryCode: $countryCode, latitude: $latitude, longitude: $longitude, locationIsApproximate: $locationIsApproximate, amenityCodes: $amenityCodes, images: $images, roomTypes: $roomTypes, cancellationPolicy: $cancellationPolicy, checkInFrom: $checkInFrom, checkOutBy: $checkOutBy, houseRules: $houseRules, instantBooking: $instantBooking, reviewAverage: $reviewAverage, reviewCount: $reviewCount, currency: $currency, vendorId: $vendorId)';
}


}

/// @nodoc
abstract mixin class $PropertyDtoCopyWith<$Res>  {
  factory $PropertyDtoCopyWith(PropertyDto value, $Res Function(PropertyDto) _then) = _$PropertyDtoCopyWithImpl;
@useResult
$Res call({
 String id, String slug, String name,@JsonKey(name: 'property_type') String propertyType, String description, String address, String city, String? state,@JsonKey(name: 'country_code') String countryCode, double? latitude, double? longitude,@JsonKey(name: 'location_is_approximate') bool locationIsApproximate,@JsonKey(name: 'amenity_codes') List<String> amenityCodes, List<ImageDto> images,@JsonKey(name: 'room_types') List<RoomTypeDto> roomTypes,@JsonKey(name: 'cancellation_policy') String cancellationPolicy,@JsonKey(name: 'check_in_from') String checkInFrom,@JsonKey(name: 'check_out_by') String checkOutBy,@JsonKey(name: 'house_rules') List<String> houseRules,@JsonKey(name: 'instant_booking') bool instantBooking,@JsonKey(name: 'review_average') double reviewAverage,@JsonKey(name: 'review_count') int reviewCount, String currency,@JsonKey(name: 'vendor_id') String vendorId
});




}
/// @nodoc
class _$PropertyDtoCopyWithImpl<$Res>
    implements $PropertyDtoCopyWith<$Res> {
  _$PropertyDtoCopyWithImpl(this._self, this._then);

  final PropertyDto _self;
  final $Res Function(PropertyDto) _then;

/// Create a copy of PropertyDto
/// with the given fields replaced by the non-null parameter values.
@pragma('vm:prefer-inline') @override $Res call({Object? id = null,Object? slug = null,Object? name = null,Object? propertyType = null,Object? description = null,Object? address = null,Object? city = null,Object? state = freezed,Object? countryCode = null,Object? latitude = freezed,Object? longitude = freezed,Object? locationIsApproximate = null,Object? amenityCodes = null,Object? images = null,Object? roomTypes = null,Object? cancellationPolicy = null,Object? checkInFrom = null,Object? checkOutBy = null,Object? houseRules = null,Object? instantBooking = null,Object? reviewAverage = null,Object? reviewCount = null,Object? currency = null,Object? vendorId = null,}) {
  return _then(_self.copyWith(
id: null == id ? _self.id : id // ignore: cast_nullable_to_non_nullable
as String,slug: null == slug ? _self.slug : slug // ignore: cast_nullable_to_non_nullable
as String,name: null == name ? _self.name : name // ignore: cast_nullable_to_non_nullable
as String,propertyType: null == propertyType ? _self.propertyType : propertyType // ignore: cast_nullable_to_non_nullable
as String,description: null == description ? _self.description : description // ignore: cast_nullable_to_non_nullable
as String,address: null == address ? _self.address : address // ignore: cast_nullable_to_non_nullable
as String,city: null == city ? _self.city : city // ignore: cast_nullable_to_non_nullable
as String,state: freezed == state ? _self.state : state // ignore: cast_nullable_to_non_nullable
as String?,countryCode: null == countryCode ? _self.countryCode : countryCode // ignore: cast_nullable_to_non_nullable
as String,latitude: freezed == latitude ? _self.latitude : latitude // ignore: cast_nullable_to_non_nullable
as double?,longitude: freezed == longitude ? _self.longitude : longitude // ignore: cast_nullable_to_non_nullable
as double?,locationIsApproximate: null == locationIsApproximate ? _self.locationIsApproximate : locationIsApproximate // ignore: cast_nullable_to_non_nullable
as bool,amenityCodes: null == amenityCodes ? _self.amenityCodes : amenityCodes // ignore: cast_nullable_to_non_nullable
as List<String>,images: null == images ? _self.images : images // ignore: cast_nullable_to_non_nullable
as List<ImageDto>,roomTypes: null == roomTypes ? _self.roomTypes : roomTypes // ignore: cast_nullable_to_non_nullable
as List<RoomTypeDto>,cancellationPolicy: null == cancellationPolicy ? _self.cancellationPolicy : cancellationPolicy // ignore: cast_nullable_to_non_nullable
as String,checkInFrom: null == checkInFrom ? _self.checkInFrom : checkInFrom // ignore: cast_nullable_to_non_nullable
as String,checkOutBy: null == checkOutBy ? _self.checkOutBy : checkOutBy // ignore: cast_nullable_to_non_nullable
as String,houseRules: null == houseRules ? _self.houseRules : houseRules // ignore: cast_nullable_to_non_nullable
as List<String>,instantBooking: null == instantBooking ? _self.instantBooking : instantBooking // ignore: cast_nullable_to_non_nullable
as bool,reviewAverage: null == reviewAverage ? _self.reviewAverage : reviewAverage // ignore: cast_nullable_to_non_nullable
as double,reviewCount: null == reviewCount ? _self.reviewCount : reviewCount // ignore: cast_nullable_to_non_nullable
as int,currency: null == currency ? _self.currency : currency // ignore: cast_nullable_to_non_nullable
as String,vendorId: null == vendorId ? _self.vendorId : vendorId // ignore: cast_nullable_to_non_nullable
as String,
  ));
}

}


/// Adds pattern-matching-related methods to [PropertyDto].
extension PropertyDtoPatterns on PropertyDto {
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

@optionalTypeArgs TResult maybeMap<TResult extends Object?>(TResult Function( _PropertyDto value)?  $default,{required TResult orElse(),}){
final _that = this;
switch (_that) {
case _PropertyDto() when $default != null:
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

@optionalTypeArgs TResult map<TResult extends Object?>(TResult Function( _PropertyDto value)  $default,){
final _that = this;
switch (_that) {
case _PropertyDto():
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

@optionalTypeArgs TResult? mapOrNull<TResult extends Object?>(TResult? Function( _PropertyDto value)?  $default,){
final _that = this;
switch (_that) {
case _PropertyDto() when $default != null:
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

@optionalTypeArgs TResult maybeWhen<TResult extends Object?>(TResult Function( String id,  String slug,  String name, @JsonKey(name: 'property_type')  String propertyType,  String description,  String address,  String city,  String? state, @JsonKey(name: 'country_code')  String countryCode,  double? latitude,  double? longitude, @JsonKey(name: 'location_is_approximate')  bool locationIsApproximate, @JsonKey(name: 'amenity_codes')  List<String> amenityCodes,  List<ImageDto> images, @JsonKey(name: 'room_types')  List<RoomTypeDto> roomTypes, @JsonKey(name: 'cancellation_policy')  String cancellationPolicy, @JsonKey(name: 'check_in_from')  String checkInFrom, @JsonKey(name: 'check_out_by')  String checkOutBy, @JsonKey(name: 'house_rules')  List<String> houseRules, @JsonKey(name: 'instant_booking')  bool instantBooking, @JsonKey(name: 'review_average')  double reviewAverage, @JsonKey(name: 'review_count')  int reviewCount,  String currency, @JsonKey(name: 'vendor_id')  String vendorId)?  $default,{required TResult orElse(),}) {final _that = this;
switch (_that) {
case _PropertyDto() when $default != null:
return $default(_that.id,_that.slug,_that.name,_that.propertyType,_that.description,_that.address,_that.city,_that.state,_that.countryCode,_that.latitude,_that.longitude,_that.locationIsApproximate,_that.amenityCodes,_that.images,_that.roomTypes,_that.cancellationPolicy,_that.checkInFrom,_that.checkOutBy,_that.houseRules,_that.instantBooking,_that.reviewAverage,_that.reviewCount,_that.currency,_that.vendorId);case _:
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

@optionalTypeArgs TResult when<TResult extends Object?>(TResult Function( String id,  String slug,  String name, @JsonKey(name: 'property_type')  String propertyType,  String description,  String address,  String city,  String? state, @JsonKey(name: 'country_code')  String countryCode,  double? latitude,  double? longitude, @JsonKey(name: 'location_is_approximate')  bool locationIsApproximate, @JsonKey(name: 'amenity_codes')  List<String> amenityCodes,  List<ImageDto> images, @JsonKey(name: 'room_types')  List<RoomTypeDto> roomTypes, @JsonKey(name: 'cancellation_policy')  String cancellationPolicy, @JsonKey(name: 'check_in_from')  String checkInFrom, @JsonKey(name: 'check_out_by')  String checkOutBy, @JsonKey(name: 'house_rules')  List<String> houseRules, @JsonKey(name: 'instant_booking')  bool instantBooking, @JsonKey(name: 'review_average')  double reviewAverage, @JsonKey(name: 'review_count')  int reviewCount,  String currency, @JsonKey(name: 'vendor_id')  String vendorId)  $default,) {final _that = this;
switch (_that) {
case _PropertyDto():
return $default(_that.id,_that.slug,_that.name,_that.propertyType,_that.description,_that.address,_that.city,_that.state,_that.countryCode,_that.latitude,_that.longitude,_that.locationIsApproximate,_that.amenityCodes,_that.images,_that.roomTypes,_that.cancellationPolicy,_that.checkInFrom,_that.checkOutBy,_that.houseRules,_that.instantBooking,_that.reviewAverage,_that.reviewCount,_that.currency,_that.vendorId);case _:
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

@optionalTypeArgs TResult? whenOrNull<TResult extends Object?>(TResult? Function( String id,  String slug,  String name, @JsonKey(name: 'property_type')  String propertyType,  String description,  String address,  String city,  String? state, @JsonKey(name: 'country_code')  String countryCode,  double? latitude,  double? longitude, @JsonKey(name: 'location_is_approximate')  bool locationIsApproximate, @JsonKey(name: 'amenity_codes')  List<String> amenityCodes,  List<ImageDto> images, @JsonKey(name: 'room_types')  List<RoomTypeDto> roomTypes, @JsonKey(name: 'cancellation_policy')  String cancellationPolicy, @JsonKey(name: 'check_in_from')  String checkInFrom, @JsonKey(name: 'check_out_by')  String checkOutBy, @JsonKey(name: 'house_rules')  List<String> houseRules, @JsonKey(name: 'instant_booking')  bool instantBooking, @JsonKey(name: 'review_average')  double reviewAverage, @JsonKey(name: 'review_count')  int reviewCount,  String currency, @JsonKey(name: 'vendor_id')  String vendorId)?  $default,) {final _that = this;
switch (_that) {
case _PropertyDto() when $default != null:
return $default(_that.id,_that.slug,_that.name,_that.propertyType,_that.description,_that.address,_that.city,_that.state,_that.countryCode,_that.latitude,_that.longitude,_that.locationIsApproximate,_that.amenityCodes,_that.images,_that.roomTypes,_that.cancellationPolicy,_that.checkInFrom,_that.checkOutBy,_that.houseRules,_that.instantBooking,_that.reviewAverage,_that.reviewCount,_that.currency,_that.vendorId);case _:
  return null;

}
}

}

/// @nodoc
@JsonSerializable()

class _PropertyDto implements PropertyDto {
  const _PropertyDto({required this.id, required this.slug, required this.name, @JsonKey(name: 'property_type') this.propertyType = '', this.description = '', this.address = '', this.city = '', this.state, @JsonKey(name: 'country_code') this.countryCode = 'IN', this.latitude, this.longitude, @JsonKey(name: 'location_is_approximate') this.locationIsApproximate = true, @JsonKey(name: 'amenity_codes') final  List<String> amenityCodes = const <String>[], final  List<ImageDto> images = const <ImageDto>[], @JsonKey(name: 'room_types') final  List<RoomTypeDto> roomTypes = const <RoomTypeDto>[], @JsonKey(name: 'cancellation_policy') this.cancellationPolicy = 'moderate', @JsonKey(name: 'check_in_from') this.checkInFrom = '', @JsonKey(name: 'check_out_by') this.checkOutBy = '', @JsonKey(name: 'house_rules') final  List<String> houseRules = const <String>[], @JsonKey(name: 'instant_booking') this.instantBooking = false, @JsonKey(name: 'review_average') this.reviewAverage = 0.0, @JsonKey(name: 'review_count') this.reviewCount = 0, this.currency = 'INR', @JsonKey(name: 'vendor_id') this.vendorId = ''}): _amenityCodes = amenityCodes,_images = images,_roomTypes = roomTypes,_houseRules = houseRules;
  factory _PropertyDto.fromJson(Map<String, dynamic> json) => _$PropertyDtoFromJson(json);

@override final  String id;
@override final  String slug;
@override final  String name;
@override@JsonKey(name: 'property_type') final  String propertyType;
@override@JsonKey() final  String description;
@override@JsonKey() final  String address;
@override@JsonKey() final  String city;
@override final  String? state;
@override@JsonKey(name: 'country_code') final  String countryCode;
@override final  double? latitude;
@override final  double? longitude;
/// The pin is fuzzed until a booking is confirmed. Not a bug to "fix":
/// publishing an exact address tells anyone where an unoccupied home is.
@override@JsonKey(name: 'location_is_approximate') final  bool locationIsApproximate;
 final  List<String> _amenityCodes;
@override@JsonKey(name: 'amenity_codes') List<String> get amenityCodes {
  if (_amenityCodes is EqualUnmodifiableListView) return _amenityCodes;
  // ignore: implicit_dynamic_type
  return EqualUnmodifiableListView(_amenityCodes);
}

 final  List<ImageDto> _images;
@override@JsonKey() List<ImageDto> get images {
  if (_images is EqualUnmodifiableListView) return _images;
  // ignore: implicit_dynamic_type
  return EqualUnmodifiableListView(_images);
}

 final  List<RoomTypeDto> _roomTypes;
@override@JsonKey(name: 'room_types') List<RoomTypeDto> get roomTypes {
  if (_roomTypes is EqualUnmodifiableListView) return _roomTypes;
  // ignore: implicit_dynamic_type
  return EqualUnmodifiableListView(_roomTypes);
}

@override@JsonKey(name: 'cancellation_policy') final  String cancellationPolicy;
@override@JsonKey(name: 'check_in_from') final  String checkInFrom;
@override@JsonKey(name: 'check_out_by') final  String checkOutBy;
 final  List<String> _houseRules;
@override@JsonKey(name: 'house_rules') List<String> get houseRules {
  if (_houseRules is EqualUnmodifiableListView) return _houseRules;
  // ignore: implicit_dynamic_type
  return EqualUnmodifiableListView(_houseRules);
}

@override@JsonKey(name: 'instant_booking') final  bool instantBooking;
@override@JsonKey(name: 'review_average') final  double reviewAverage;
@override@JsonKey(name: 'review_count') final  int reviewCount;
@override@JsonKey() final  String currency;
@override@JsonKey(name: 'vendor_id') final  String vendorId;

/// Create a copy of PropertyDto
/// with the given fields replaced by the non-null parameter values.
@override @JsonKey(includeFromJson: false, includeToJson: false)
@pragma('vm:prefer-inline')
_$PropertyDtoCopyWith<_PropertyDto> get copyWith => __$PropertyDtoCopyWithImpl<_PropertyDto>(this, _$identity);

@override
Map<String, dynamic> toJson() {
  return _$PropertyDtoToJson(this, );
}

@override
bool operator ==(Object other) {
  return identical(this, other) || (other.runtimeType == runtimeType&&other is _PropertyDto&&(identical(other.id, id) || other.id == id)&&(identical(other.slug, slug) || other.slug == slug)&&(identical(other.name, name) || other.name == name)&&(identical(other.propertyType, propertyType) || other.propertyType == propertyType)&&(identical(other.description, description) || other.description == description)&&(identical(other.address, address) || other.address == address)&&(identical(other.city, city) || other.city == city)&&(identical(other.state, state) || other.state == state)&&(identical(other.countryCode, countryCode) || other.countryCode == countryCode)&&(identical(other.latitude, latitude) || other.latitude == latitude)&&(identical(other.longitude, longitude) || other.longitude == longitude)&&(identical(other.locationIsApproximate, locationIsApproximate) || other.locationIsApproximate == locationIsApproximate)&&const DeepCollectionEquality().equals(other._amenityCodes, _amenityCodes)&&const DeepCollectionEquality().equals(other._images, _images)&&const DeepCollectionEquality().equals(other._roomTypes, _roomTypes)&&(identical(other.cancellationPolicy, cancellationPolicy) || other.cancellationPolicy == cancellationPolicy)&&(identical(other.checkInFrom, checkInFrom) || other.checkInFrom == checkInFrom)&&(identical(other.checkOutBy, checkOutBy) || other.checkOutBy == checkOutBy)&&const DeepCollectionEquality().equals(other._houseRules, _houseRules)&&(identical(other.instantBooking, instantBooking) || other.instantBooking == instantBooking)&&(identical(other.reviewAverage, reviewAverage) || other.reviewAverage == reviewAverage)&&(identical(other.reviewCount, reviewCount) || other.reviewCount == reviewCount)&&(identical(other.currency, currency) || other.currency == currency)&&(identical(other.vendorId, vendorId) || other.vendorId == vendorId));
}

@JsonKey(includeFromJson: false, includeToJson: false)
@override
int get hashCode => Object.hashAll([runtimeType,id,slug,name,propertyType,description,address,city,state,countryCode,latitude,longitude,locationIsApproximate,const DeepCollectionEquality().hash(_amenityCodes),const DeepCollectionEquality().hash(_images),const DeepCollectionEquality().hash(_roomTypes),cancellationPolicy,checkInFrom,checkOutBy,const DeepCollectionEquality().hash(_houseRules),instantBooking,reviewAverage,reviewCount,currency,vendorId]);

@override
String toString() {
  return 'PropertyDto(id: $id, slug: $slug, name: $name, propertyType: $propertyType, description: $description, address: $address, city: $city, state: $state, countryCode: $countryCode, latitude: $latitude, longitude: $longitude, locationIsApproximate: $locationIsApproximate, amenityCodes: $amenityCodes, images: $images, roomTypes: $roomTypes, cancellationPolicy: $cancellationPolicy, checkInFrom: $checkInFrom, checkOutBy: $checkOutBy, houseRules: $houseRules, instantBooking: $instantBooking, reviewAverage: $reviewAverage, reviewCount: $reviewCount, currency: $currency, vendorId: $vendorId)';
}


}

/// @nodoc
abstract mixin class _$PropertyDtoCopyWith<$Res> implements $PropertyDtoCopyWith<$Res> {
  factory _$PropertyDtoCopyWith(_PropertyDto value, $Res Function(_PropertyDto) _then) = __$PropertyDtoCopyWithImpl;
@override @useResult
$Res call({
 String id, String slug, String name,@JsonKey(name: 'property_type') String propertyType, String description, String address, String city, String? state,@JsonKey(name: 'country_code') String countryCode, double? latitude, double? longitude,@JsonKey(name: 'location_is_approximate') bool locationIsApproximate,@JsonKey(name: 'amenity_codes') List<String> amenityCodes, List<ImageDto> images,@JsonKey(name: 'room_types') List<RoomTypeDto> roomTypes,@JsonKey(name: 'cancellation_policy') String cancellationPolicy,@JsonKey(name: 'check_in_from') String checkInFrom,@JsonKey(name: 'check_out_by') String checkOutBy,@JsonKey(name: 'house_rules') List<String> houseRules,@JsonKey(name: 'instant_booking') bool instantBooking,@JsonKey(name: 'review_average') double reviewAverage,@JsonKey(name: 'review_count') int reviewCount, String currency,@JsonKey(name: 'vendor_id') String vendorId
});




}
/// @nodoc
class __$PropertyDtoCopyWithImpl<$Res>
    implements _$PropertyDtoCopyWith<$Res> {
  __$PropertyDtoCopyWithImpl(this._self, this._then);

  final _PropertyDto _self;
  final $Res Function(_PropertyDto) _then;

/// Create a copy of PropertyDto
/// with the given fields replaced by the non-null parameter values.
@override @pragma('vm:prefer-inline') $Res call({Object? id = null,Object? slug = null,Object? name = null,Object? propertyType = null,Object? description = null,Object? address = null,Object? city = null,Object? state = freezed,Object? countryCode = null,Object? latitude = freezed,Object? longitude = freezed,Object? locationIsApproximate = null,Object? amenityCodes = null,Object? images = null,Object? roomTypes = null,Object? cancellationPolicy = null,Object? checkInFrom = null,Object? checkOutBy = null,Object? houseRules = null,Object? instantBooking = null,Object? reviewAverage = null,Object? reviewCount = null,Object? currency = null,Object? vendorId = null,}) {
  return _then(_PropertyDto(
id: null == id ? _self.id : id // ignore: cast_nullable_to_non_nullable
as String,slug: null == slug ? _self.slug : slug // ignore: cast_nullable_to_non_nullable
as String,name: null == name ? _self.name : name // ignore: cast_nullable_to_non_nullable
as String,propertyType: null == propertyType ? _self.propertyType : propertyType // ignore: cast_nullable_to_non_nullable
as String,description: null == description ? _self.description : description // ignore: cast_nullable_to_non_nullable
as String,address: null == address ? _self.address : address // ignore: cast_nullable_to_non_nullable
as String,city: null == city ? _self.city : city // ignore: cast_nullable_to_non_nullable
as String,state: freezed == state ? _self.state : state // ignore: cast_nullable_to_non_nullable
as String?,countryCode: null == countryCode ? _self.countryCode : countryCode // ignore: cast_nullable_to_non_nullable
as String,latitude: freezed == latitude ? _self.latitude : latitude // ignore: cast_nullable_to_non_nullable
as double?,longitude: freezed == longitude ? _self.longitude : longitude // ignore: cast_nullable_to_non_nullable
as double?,locationIsApproximate: null == locationIsApproximate ? _self.locationIsApproximate : locationIsApproximate // ignore: cast_nullable_to_non_nullable
as bool,amenityCodes: null == amenityCodes ? _self._amenityCodes : amenityCodes // ignore: cast_nullable_to_non_nullable
as List<String>,images: null == images ? _self._images : images // ignore: cast_nullable_to_non_nullable
as List<ImageDto>,roomTypes: null == roomTypes ? _self._roomTypes : roomTypes // ignore: cast_nullable_to_non_nullable
as List<RoomTypeDto>,cancellationPolicy: null == cancellationPolicy ? _self.cancellationPolicy : cancellationPolicy // ignore: cast_nullable_to_non_nullable
as String,checkInFrom: null == checkInFrom ? _self.checkInFrom : checkInFrom // ignore: cast_nullable_to_non_nullable
as String,checkOutBy: null == checkOutBy ? _self.checkOutBy : checkOutBy // ignore: cast_nullable_to_non_nullable
as String,houseRules: null == houseRules ? _self._houseRules : houseRules // ignore: cast_nullable_to_non_nullable
as List<String>,instantBooking: null == instantBooking ? _self.instantBooking : instantBooking // ignore: cast_nullable_to_non_nullable
as bool,reviewAverage: null == reviewAverage ? _self.reviewAverage : reviewAverage // ignore: cast_nullable_to_non_nullable
as double,reviewCount: null == reviewCount ? _self.reviewCount : reviewCount // ignore: cast_nullable_to_non_nullable
as int,currency: null == currency ? _self.currency : currency // ignore: cast_nullable_to_non_nullable
as String,vendorId: null == vendorId ? _self.vendorId : vendorId // ignore: cast_nullable_to_non_nullable
as String,
  ));
}


}


/// @nodoc
mixin _$SearchItemDto {

 String get id; String get slug; String get name;@JsonKey(name: 'property_type') String get propertyType; String get city;@JsonKey(name: 'country_code') String get countryCode; double? get latitude; double? get longitude;@JsonKey(name: 'distance_m') double? get distanceM;@JsonKey(name: 'cover_image_url') String? get coverImageUrl;@JsonKey(name: 'review_average') double get reviewAverage;@JsonKey(name: 'review_count') int get reviewCount;@JsonKey(name: 'amenity_codes') List<String> get amenityCodes;@JsonKey(name: 'instant_booking') bool get instantBooking;@JsonKey(name: 'cancellation_policy') String get cancellationPolicy;@JsonKey(name: 'max_occupancy') int get maxOccupancy;/// Nightly "from" price. Shown only when there are no dates.
@JsonKey(name: 'from_price_minor') int? get fromPriceMinor;/// The total for the searched dates. Never interchanged with the above:
/// showing a nightly rate where a total is expected is the oldest dark
/// pattern in travel.
@JsonKey(name: 'total_price_minor') int? get totalPriceMinor; String get currency;@JsonKey(name: 'is_available') bool get isAvailable;
/// Create a copy of SearchItemDto
/// with the given fields replaced by the non-null parameter values.
@JsonKey(includeFromJson: false, includeToJson: false)
@pragma('vm:prefer-inline')
$SearchItemDtoCopyWith<SearchItemDto> get copyWith => _$SearchItemDtoCopyWithImpl<SearchItemDto>(this as SearchItemDto, _$identity);

  /// Serializes this SearchItemDto to a JSON map.
  Map<String, dynamic> toJson();


@override
bool operator ==(Object other) {
  return identical(this, other) || (other.runtimeType == runtimeType&&other is SearchItemDto&&(identical(other.id, id) || other.id == id)&&(identical(other.slug, slug) || other.slug == slug)&&(identical(other.name, name) || other.name == name)&&(identical(other.propertyType, propertyType) || other.propertyType == propertyType)&&(identical(other.city, city) || other.city == city)&&(identical(other.countryCode, countryCode) || other.countryCode == countryCode)&&(identical(other.latitude, latitude) || other.latitude == latitude)&&(identical(other.longitude, longitude) || other.longitude == longitude)&&(identical(other.distanceM, distanceM) || other.distanceM == distanceM)&&(identical(other.coverImageUrl, coverImageUrl) || other.coverImageUrl == coverImageUrl)&&(identical(other.reviewAverage, reviewAverage) || other.reviewAverage == reviewAverage)&&(identical(other.reviewCount, reviewCount) || other.reviewCount == reviewCount)&&const DeepCollectionEquality().equals(other.amenityCodes, amenityCodes)&&(identical(other.instantBooking, instantBooking) || other.instantBooking == instantBooking)&&(identical(other.cancellationPolicy, cancellationPolicy) || other.cancellationPolicy == cancellationPolicy)&&(identical(other.maxOccupancy, maxOccupancy) || other.maxOccupancy == maxOccupancy)&&(identical(other.fromPriceMinor, fromPriceMinor) || other.fromPriceMinor == fromPriceMinor)&&(identical(other.totalPriceMinor, totalPriceMinor) || other.totalPriceMinor == totalPriceMinor)&&(identical(other.currency, currency) || other.currency == currency)&&(identical(other.isAvailable, isAvailable) || other.isAvailable == isAvailable));
}

@JsonKey(includeFromJson: false, includeToJson: false)
@override
int get hashCode => Object.hashAll([runtimeType,id,slug,name,propertyType,city,countryCode,latitude,longitude,distanceM,coverImageUrl,reviewAverage,reviewCount,const DeepCollectionEquality().hash(amenityCodes),instantBooking,cancellationPolicy,maxOccupancy,fromPriceMinor,totalPriceMinor,currency,isAvailable]);

@override
String toString() {
  return 'SearchItemDto(id: $id, slug: $slug, name: $name, propertyType: $propertyType, city: $city, countryCode: $countryCode, latitude: $latitude, longitude: $longitude, distanceM: $distanceM, coverImageUrl: $coverImageUrl, reviewAverage: $reviewAverage, reviewCount: $reviewCount, amenityCodes: $amenityCodes, instantBooking: $instantBooking, cancellationPolicy: $cancellationPolicy, maxOccupancy: $maxOccupancy, fromPriceMinor: $fromPriceMinor, totalPriceMinor: $totalPriceMinor, currency: $currency, isAvailable: $isAvailable)';
}


}

/// @nodoc
abstract mixin class $SearchItemDtoCopyWith<$Res>  {
  factory $SearchItemDtoCopyWith(SearchItemDto value, $Res Function(SearchItemDto) _then) = _$SearchItemDtoCopyWithImpl;
@useResult
$Res call({
 String id, String slug, String name,@JsonKey(name: 'property_type') String propertyType, String city,@JsonKey(name: 'country_code') String countryCode, double? latitude, double? longitude,@JsonKey(name: 'distance_m') double? distanceM,@JsonKey(name: 'cover_image_url') String? coverImageUrl,@JsonKey(name: 'review_average') double reviewAverage,@JsonKey(name: 'review_count') int reviewCount,@JsonKey(name: 'amenity_codes') List<String> amenityCodes,@JsonKey(name: 'instant_booking') bool instantBooking,@JsonKey(name: 'cancellation_policy') String cancellationPolicy,@JsonKey(name: 'max_occupancy') int maxOccupancy,@JsonKey(name: 'from_price_minor') int? fromPriceMinor,@JsonKey(name: 'total_price_minor') int? totalPriceMinor, String currency,@JsonKey(name: 'is_available') bool isAvailable
});




}
/// @nodoc
class _$SearchItemDtoCopyWithImpl<$Res>
    implements $SearchItemDtoCopyWith<$Res> {
  _$SearchItemDtoCopyWithImpl(this._self, this._then);

  final SearchItemDto _self;
  final $Res Function(SearchItemDto) _then;

/// Create a copy of SearchItemDto
/// with the given fields replaced by the non-null parameter values.
@pragma('vm:prefer-inline') @override $Res call({Object? id = null,Object? slug = null,Object? name = null,Object? propertyType = null,Object? city = null,Object? countryCode = null,Object? latitude = freezed,Object? longitude = freezed,Object? distanceM = freezed,Object? coverImageUrl = freezed,Object? reviewAverage = null,Object? reviewCount = null,Object? amenityCodes = null,Object? instantBooking = null,Object? cancellationPolicy = null,Object? maxOccupancy = null,Object? fromPriceMinor = freezed,Object? totalPriceMinor = freezed,Object? currency = null,Object? isAvailable = null,}) {
  return _then(_self.copyWith(
id: null == id ? _self.id : id // ignore: cast_nullable_to_non_nullable
as String,slug: null == slug ? _self.slug : slug // ignore: cast_nullable_to_non_nullable
as String,name: null == name ? _self.name : name // ignore: cast_nullable_to_non_nullable
as String,propertyType: null == propertyType ? _self.propertyType : propertyType // ignore: cast_nullable_to_non_nullable
as String,city: null == city ? _self.city : city // ignore: cast_nullable_to_non_nullable
as String,countryCode: null == countryCode ? _self.countryCode : countryCode // ignore: cast_nullable_to_non_nullable
as String,latitude: freezed == latitude ? _self.latitude : latitude // ignore: cast_nullable_to_non_nullable
as double?,longitude: freezed == longitude ? _self.longitude : longitude // ignore: cast_nullable_to_non_nullable
as double?,distanceM: freezed == distanceM ? _self.distanceM : distanceM // ignore: cast_nullable_to_non_nullable
as double?,coverImageUrl: freezed == coverImageUrl ? _self.coverImageUrl : coverImageUrl // ignore: cast_nullable_to_non_nullable
as String?,reviewAverage: null == reviewAverage ? _self.reviewAverage : reviewAverage // ignore: cast_nullable_to_non_nullable
as double,reviewCount: null == reviewCount ? _self.reviewCount : reviewCount // ignore: cast_nullable_to_non_nullable
as int,amenityCodes: null == amenityCodes ? _self.amenityCodes : amenityCodes // ignore: cast_nullable_to_non_nullable
as List<String>,instantBooking: null == instantBooking ? _self.instantBooking : instantBooking // ignore: cast_nullable_to_non_nullable
as bool,cancellationPolicy: null == cancellationPolicy ? _self.cancellationPolicy : cancellationPolicy // ignore: cast_nullable_to_non_nullable
as String,maxOccupancy: null == maxOccupancy ? _self.maxOccupancy : maxOccupancy // ignore: cast_nullable_to_non_nullable
as int,fromPriceMinor: freezed == fromPriceMinor ? _self.fromPriceMinor : fromPriceMinor // ignore: cast_nullable_to_non_nullable
as int?,totalPriceMinor: freezed == totalPriceMinor ? _self.totalPriceMinor : totalPriceMinor // ignore: cast_nullable_to_non_nullable
as int?,currency: null == currency ? _self.currency : currency // ignore: cast_nullable_to_non_nullable
as String,isAvailable: null == isAvailable ? _self.isAvailable : isAvailable // ignore: cast_nullable_to_non_nullable
as bool,
  ));
}

}


/// Adds pattern-matching-related methods to [SearchItemDto].
extension SearchItemDtoPatterns on SearchItemDto {
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

@optionalTypeArgs TResult maybeMap<TResult extends Object?>(TResult Function( _SearchItemDto value)?  $default,{required TResult orElse(),}){
final _that = this;
switch (_that) {
case _SearchItemDto() when $default != null:
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

@optionalTypeArgs TResult map<TResult extends Object?>(TResult Function( _SearchItemDto value)  $default,){
final _that = this;
switch (_that) {
case _SearchItemDto():
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

@optionalTypeArgs TResult? mapOrNull<TResult extends Object?>(TResult? Function( _SearchItemDto value)?  $default,){
final _that = this;
switch (_that) {
case _SearchItemDto() when $default != null:
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

@optionalTypeArgs TResult maybeWhen<TResult extends Object?>(TResult Function( String id,  String slug,  String name, @JsonKey(name: 'property_type')  String propertyType,  String city, @JsonKey(name: 'country_code')  String countryCode,  double? latitude,  double? longitude, @JsonKey(name: 'distance_m')  double? distanceM, @JsonKey(name: 'cover_image_url')  String? coverImageUrl, @JsonKey(name: 'review_average')  double reviewAverage, @JsonKey(name: 'review_count')  int reviewCount, @JsonKey(name: 'amenity_codes')  List<String> amenityCodes, @JsonKey(name: 'instant_booking')  bool instantBooking, @JsonKey(name: 'cancellation_policy')  String cancellationPolicy, @JsonKey(name: 'max_occupancy')  int maxOccupancy, @JsonKey(name: 'from_price_minor')  int? fromPriceMinor, @JsonKey(name: 'total_price_minor')  int? totalPriceMinor,  String currency, @JsonKey(name: 'is_available')  bool isAvailable)?  $default,{required TResult orElse(),}) {final _that = this;
switch (_that) {
case _SearchItemDto() when $default != null:
return $default(_that.id,_that.slug,_that.name,_that.propertyType,_that.city,_that.countryCode,_that.latitude,_that.longitude,_that.distanceM,_that.coverImageUrl,_that.reviewAverage,_that.reviewCount,_that.amenityCodes,_that.instantBooking,_that.cancellationPolicy,_that.maxOccupancy,_that.fromPriceMinor,_that.totalPriceMinor,_that.currency,_that.isAvailable);case _:
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

@optionalTypeArgs TResult when<TResult extends Object?>(TResult Function( String id,  String slug,  String name, @JsonKey(name: 'property_type')  String propertyType,  String city, @JsonKey(name: 'country_code')  String countryCode,  double? latitude,  double? longitude, @JsonKey(name: 'distance_m')  double? distanceM, @JsonKey(name: 'cover_image_url')  String? coverImageUrl, @JsonKey(name: 'review_average')  double reviewAverage, @JsonKey(name: 'review_count')  int reviewCount, @JsonKey(name: 'amenity_codes')  List<String> amenityCodes, @JsonKey(name: 'instant_booking')  bool instantBooking, @JsonKey(name: 'cancellation_policy')  String cancellationPolicy, @JsonKey(name: 'max_occupancy')  int maxOccupancy, @JsonKey(name: 'from_price_minor')  int? fromPriceMinor, @JsonKey(name: 'total_price_minor')  int? totalPriceMinor,  String currency, @JsonKey(name: 'is_available')  bool isAvailable)  $default,) {final _that = this;
switch (_that) {
case _SearchItemDto():
return $default(_that.id,_that.slug,_that.name,_that.propertyType,_that.city,_that.countryCode,_that.latitude,_that.longitude,_that.distanceM,_that.coverImageUrl,_that.reviewAverage,_that.reviewCount,_that.amenityCodes,_that.instantBooking,_that.cancellationPolicy,_that.maxOccupancy,_that.fromPriceMinor,_that.totalPriceMinor,_that.currency,_that.isAvailable);case _:
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

@optionalTypeArgs TResult? whenOrNull<TResult extends Object?>(TResult? Function( String id,  String slug,  String name, @JsonKey(name: 'property_type')  String propertyType,  String city, @JsonKey(name: 'country_code')  String countryCode,  double? latitude,  double? longitude, @JsonKey(name: 'distance_m')  double? distanceM, @JsonKey(name: 'cover_image_url')  String? coverImageUrl, @JsonKey(name: 'review_average')  double reviewAverage, @JsonKey(name: 'review_count')  int reviewCount, @JsonKey(name: 'amenity_codes')  List<String> amenityCodes, @JsonKey(name: 'instant_booking')  bool instantBooking, @JsonKey(name: 'cancellation_policy')  String cancellationPolicy, @JsonKey(name: 'max_occupancy')  int maxOccupancy, @JsonKey(name: 'from_price_minor')  int? fromPriceMinor, @JsonKey(name: 'total_price_minor')  int? totalPriceMinor,  String currency, @JsonKey(name: 'is_available')  bool isAvailable)?  $default,) {final _that = this;
switch (_that) {
case _SearchItemDto() when $default != null:
return $default(_that.id,_that.slug,_that.name,_that.propertyType,_that.city,_that.countryCode,_that.latitude,_that.longitude,_that.distanceM,_that.coverImageUrl,_that.reviewAverage,_that.reviewCount,_that.amenityCodes,_that.instantBooking,_that.cancellationPolicy,_that.maxOccupancy,_that.fromPriceMinor,_that.totalPriceMinor,_that.currency,_that.isAvailable);case _:
  return null;

}
}

}

/// @nodoc
@JsonSerializable()

class _SearchItemDto implements SearchItemDto {
  const _SearchItemDto({required this.id, required this.slug, required this.name, @JsonKey(name: 'property_type') this.propertyType = '', this.city = '', @JsonKey(name: 'country_code') this.countryCode = 'IN', this.latitude, this.longitude, @JsonKey(name: 'distance_m') this.distanceM, @JsonKey(name: 'cover_image_url') this.coverImageUrl, @JsonKey(name: 'review_average') this.reviewAverage = 0.0, @JsonKey(name: 'review_count') this.reviewCount = 0, @JsonKey(name: 'amenity_codes') final  List<String> amenityCodes = const <String>[], @JsonKey(name: 'instant_booking') this.instantBooking = false, @JsonKey(name: 'cancellation_policy') this.cancellationPolicy = 'moderate', @JsonKey(name: 'max_occupancy') this.maxOccupancy = 2, @JsonKey(name: 'from_price_minor') this.fromPriceMinor, @JsonKey(name: 'total_price_minor') this.totalPriceMinor, this.currency = 'INR', @JsonKey(name: 'is_available') this.isAvailable = true}): _amenityCodes = amenityCodes;
  factory _SearchItemDto.fromJson(Map<String, dynamic> json) => _$SearchItemDtoFromJson(json);

@override final  String id;
@override final  String slug;
@override final  String name;
@override@JsonKey(name: 'property_type') final  String propertyType;
@override@JsonKey() final  String city;
@override@JsonKey(name: 'country_code') final  String countryCode;
@override final  double? latitude;
@override final  double? longitude;
@override@JsonKey(name: 'distance_m') final  double? distanceM;
@override@JsonKey(name: 'cover_image_url') final  String? coverImageUrl;
@override@JsonKey(name: 'review_average') final  double reviewAverage;
@override@JsonKey(name: 'review_count') final  int reviewCount;
 final  List<String> _amenityCodes;
@override@JsonKey(name: 'amenity_codes') List<String> get amenityCodes {
  if (_amenityCodes is EqualUnmodifiableListView) return _amenityCodes;
  // ignore: implicit_dynamic_type
  return EqualUnmodifiableListView(_amenityCodes);
}

@override@JsonKey(name: 'instant_booking') final  bool instantBooking;
@override@JsonKey(name: 'cancellation_policy') final  String cancellationPolicy;
@override@JsonKey(name: 'max_occupancy') final  int maxOccupancy;
/// Nightly "from" price. Shown only when there are no dates.
@override@JsonKey(name: 'from_price_minor') final  int? fromPriceMinor;
/// The total for the searched dates. Never interchanged with the above:
/// showing a nightly rate where a total is expected is the oldest dark
/// pattern in travel.
@override@JsonKey(name: 'total_price_minor') final  int? totalPriceMinor;
@override@JsonKey() final  String currency;
@override@JsonKey(name: 'is_available') final  bool isAvailable;

/// Create a copy of SearchItemDto
/// with the given fields replaced by the non-null parameter values.
@override @JsonKey(includeFromJson: false, includeToJson: false)
@pragma('vm:prefer-inline')
_$SearchItemDtoCopyWith<_SearchItemDto> get copyWith => __$SearchItemDtoCopyWithImpl<_SearchItemDto>(this, _$identity);

@override
Map<String, dynamic> toJson() {
  return _$SearchItemDtoToJson(this, );
}

@override
bool operator ==(Object other) {
  return identical(this, other) || (other.runtimeType == runtimeType&&other is _SearchItemDto&&(identical(other.id, id) || other.id == id)&&(identical(other.slug, slug) || other.slug == slug)&&(identical(other.name, name) || other.name == name)&&(identical(other.propertyType, propertyType) || other.propertyType == propertyType)&&(identical(other.city, city) || other.city == city)&&(identical(other.countryCode, countryCode) || other.countryCode == countryCode)&&(identical(other.latitude, latitude) || other.latitude == latitude)&&(identical(other.longitude, longitude) || other.longitude == longitude)&&(identical(other.distanceM, distanceM) || other.distanceM == distanceM)&&(identical(other.coverImageUrl, coverImageUrl) || other.coverImageUrl == coverImageUrl)&&(identical(other.reviewAverage, reviewAverage) || other.reviewAverage == reviewAverage)&&(identical(other.reviewCount, reviewCount) || other.reviewCount == reviewCount)&&const DeepCollectionEquality().equals(other._amenityCodes, _amenityCodes)&&(identical(other.instantBooking, instantBooking) || other.instantBooking == instantBooking)&&(identical(other.cancellationPolicy, cancellationPolicy) || other.cancellationPolicy == cancellationPolicy)&&(identical(other.maxOccupancy, maxOccupancy) || other.maxOccupancy == maxOccupancy)&&(identical(other.fromPriceMinor, fromPriceMinor) || other.fromPriceMinor == fromPriceMinor)&&(identical(other.totalPriceMinor, totalPriceMinor) || other.totalPriceMinor == totalPriceMinor)&&(identical(other.currency, currency) || other.currency == currency)&&(identical(other.isAvailable, isAvailable) || other.isAvailable == isAvailable));
}

@JsonKey(includeFromJson: false, includeToJson: false)
@override
int get hashCode => Object.hashAll([runtimeType,id,slug,name,propertyType,city,countryCode,latitude,longitude,distanceM,coverImageUrl,reviewAverage,reviewCount,const DeepCollectionEquality().hash(_amenityCodes),instantBooking,cancellationPolicy,maxOccupancy,fromPriceMinor,totalPriceMinor,currency,isAvailable]);

@override
String toString() {
  return 'SearchItemDto(id: $id, slug: $slug, name: $name, propertyType: $propertyType, city: $city, countryCode: $countryCode, latitude: $latitude, longitude: $longitude, distanceM: $distanceM, coverImageUrl: $coverImageUrl, reviewAverage: $reviewAverage, reviewCount: $reviewCount, amenityCodes: $amenityCodes, instantBooking: $instantBooking, cancellationPolicy: $cancellationPolicy, maxOccupancy: $maxOccupancy, fromPriceMinor: $fromPriceMinor, totalPriceMinor: $totalPriceMinor, currency: $currency, isAvailable: $isAvailable)';
}


}

/// @nodoc
abstract mixin class _$SearchItemDtoCopyWith<$Res> implements $SearchItemDtoCopyWith<$Res> {
  factory _$SearchItemDtoCopyWith(_SearchItemDto value, $Res Function(_SearchItemDto) _then) = __$SearchItemDtoCopyWithImpl;
@override @useResult
$Res call({
 String id, String slug, String name,@JsonKey(name: 'property_type') String propertyType, String city,@JsonKey(name: 'country_code') String countryCode, double? latitude, double? longitude,@JsonKey(name: 'distance_m') double? distanceM,@JsonKey(name: 'cover_image_url') String? coverImageUrl,@JsonKey(name: 'review_average') double reviewAverage,@JsonKey(name: 'review_count') int reviewCount,@JsonKey(name: 'amenity_codes') List<String> amenityCodes,@JsonKey(name: 'instant_booking') bool instantBooking,@JsonKey(name: 'cancellation_policy') String cancellationPolicy,@JsonKey(name: 'max_occupancy') int maxOccupancy,@JsonKey(name: 'from_price_minor') int? fromPriceMinor,@JsonKey(name: 'total_price_minor') int? totalPriceMinor, String currency,@JsonKey(name: 'is_available') bool isAvailable
});




}
/// @nodoc
class __$SearchItemDtoCopyWithImpl<$Res>
    implements _$SearchItemDtoCopyWith<$Res> {
  __$SearchItemDtoCopyWithImpl(this._self, this._then);

  final _SearchItemDto _self;
  final $Res Function(_SearchItemDto) _then;

/// Create a copy of SearchItemDto
/// with the given fields replaced by the non-null parameter values.
@override @pragma('vm:prefer-inline') $Res call({Object? id = null,Object? slug = null,Object? name = null,Object? propertyType = null,Object? city = null,Object? countryCode = null,Object? latitude = freezed,Object? longitude = freezed,Object? distanceM = freezed,Object? coverImageUrl = freezed,Object? reviewAverage = null,Object? reviewCount = null,Object? amenityCodes = null,Object? instantBooking = null,Object? cancellationPolicy = null,Object? maxOccupancy = null,Object? fromPriceMinor = freezed,Object? totalPriceMinor = freezed,Object? currency = null,Object? isAvailable = null,}) {
  return _then(_SearchItemDto(
id: null == id ? _self.id : id // ignore: cast_nullable_to_non_nullable
as String,slug: null == slug ? _self.slug : slug // ignore: cast_nullable_to_non_nullable
as String,name: null == name ? _self.name : name // ignore: cast_nullable_to_non_nullable
as String,propertyType: null == propertyType ? _self.propertyType : propertyType // ignore: cast_nullable_to_non_nullable
as String,city: null == city ? _self.city : city // ignore: cast_nullable_to_non_nullable
as String,countryCode: null == countryCode ? _self.countryCode : countryCode // ignore: cast_nullable_to_non_nullable
as String,latitude: freezed == latitude ? _self.latitude : latitude // ignore: cast_nullable_to_non_nullable
as double?,longitude: freezed == longitude ? _self.longitude : longitude // ignore: cast_nullable_to_non_nullable
as double?,distanceM: freezed == distanceM ? _self.distanceM : distanceM // ignore: cast_nullable_to_non_nullable
as double?,coverImageUrl: freezed == coverImageUrl ? _self.coverImageUrl : coverImageUrl // ignore: cast_nullable_to_non_nullable
as String?,reviewAverage: null == reviewAverage ? _self.reviewAverage : reviewAverage // ignore: cast_nullable_to_non_nullable
as double,reviewCount: null == reviewCount ? _self.reviewCount : reviewCount // ignore: cast_nullable_to_non_nullable
as int,amenityCodes: null == amenityCodes ? _self._amenityCodes : amenityCodes // ignore: cast_nullable_to_non_nullable
as List<String>,instantBooking: null == instantBooking ? _self.instantBooking : instantBooking // ignore: cast_nullable_to_non_nullable
as bool,cancellationPolicy: null == cancellationPolicy ? _self.cancellationPolicy : cancellationPolicy // ignore: cast_nullable_to_non_nullable
as String,maxOccupancy: null == maxOccupancy ? _self.maxOccupancy : maxOccupancy // ignore: cast_nullable_to_non_nullable
as int,fromPriceMinor: freezed == fromPriceMinor ? _self.fromPriceMinor : fromPriceMinor // ignore: cast_nullable_to_non_nullable
as int?,totalPriceMinor: freezed == totalPriceMinor ? _self.totalPriceMinor : totalPriceMinor // ignore: cast_nullable_to_non_nullable
as int?,currency: null == currency ? _self.currency : currency // ignore: cast_nullable_to_non_nullable
as String,isAvailable: null == isAvailable ? _self.isAvailable : isAvailable // ignore: cast_nullable_to_non_nullable
as bool,
  ));
}


}


/// @nodoc
mixin _$SearchPageDto {

 List<SearchItemDto> get items;@JsonKey(name: 'next_cursor') String? get nextCursor;@JsonKey(name: 'total_estimate') int? get totalEstimate;@JsonKey(name: 'applied_radius_m') int? get appliedRadiusM;
/// Create a copy of SearchPageDto
/// with the given fields replaced by the non-null parameter values.
@JsonKey(includeFromJson: false, includeToJson: false)
@pragma('vm:prefer-inline')
$SearchPageDtoCopyWith<SearchPageDto> get copyWith => _$SearchPageDtoCopyWithImpl<SearchPageDto>(this as SearchPageDto, _$identity);

  /// Serializes this SearchPageDto to a JSON map.
  Map<String, dynamic> toJson();


@override
bool operator ==(Object other) {
  return identical(this, other) || (other.runtimeType == runtimeType&&other is SearchPageDto&&const DeepCollectionEquality().equals(other.items, items)&&(identical(other.nextCursor, nextCursor) || other.nextCursor == nextCursor)&&(identical(other.totalEstimate, totalEstimate) || other.totalEstimate == totalEstimate)&&(identical(other.appliedRadiusM, appliedRadiusM) || other.appliedRadiusM == appliedRadiusM));
}

@JsonKey(includeFromJson: false, includeToJson: false)
@override
int get hashCode => Object.hash(runtimeType,const DeepCollectionEquality().hash(items),nextCursor,totalEstimate,appliedRadiusM);

@override
String toString() {
  return 'SearchPageDto(items: $items, nextCursor: $nextCursor, totalEstimate: $totalEstimate, appliedRadiusM: $appliedRadiusM)';
}


}

/// @nodoc
abstract mixin class $SearchPageDtoCopyWith<$Res>  {
  factory $SearchPageDtoCopyWith(SearchPageDto value, $Res Function(SearchPageDto) _then) = _$SearchPageDtoCopyWithImpl;
@useResult
$Res call({
 List<SearchItemDto> items,@JsonKey(name: 'next_cursor') String? nextCursor,@JsonKey(name: 'total_estimate') int? totalEstimate,@JsonKey(name: 'applied_radius_m') int? appliedRadiusM
});




}
/// @nodoc
class _$SearchPageDtoCopyWithImpl<$Res>
    implements $SearchPageDtoCopyWith<$Res> {
  _$SearchPageDtoCopyWithImpl(this._self, this._then);

  final SearchPageDto _self;
  final $Res Function(SearchPageDto) _then;

/// Create a copy of SearchPageDto
/// with the given fields replaced by the non-null parameter values.
@pragma('vm:prefer-inline') @override $Res call({Object? items = null,Object? nextCursor = freezed,Object? totalEstimate = freezed,Object? appliedRadiusM = freezed,}) {
  return _then(_self.copyWith(
items: null == items ? _self.items : items // ignore: cast_nullable_to_non_nullable
as List<SearchItemDto>,nextCursor: freezed == nextCursor ? _self.nextCursor : nextCursor // ignore: cast_nullable_to_non_nullable
as String?,totalEstimate: freezed == totalEstimate ? _self.totalEstimate : totalEstimate // ignore: cast_nullable_to_non_nullable
as int?,appliedRadiusM: freezed == appliedRadiusM ? _self.appliedRadiusM : appliedRadiusM // ignore: cast_nullable_to_non_nullable
as int?,
  ));
}

}


/// Adds pattern-matching-related methods to [SearchPageDto].
extension SearchPageDtoPatterns on SearchPageDto {
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

@optionalTypeArgs TResult maybeMap<TResult extends Object?>(TResult Function( _SearchPageDto value)?  $default,{required TResult orElse(),}){
final _that = this;
switch (_that) {
case _SearchPageDto() when $default != null:
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

@optionalTypeArgs TResult map<TResult extends Object?>(TResult Function( _SearchPageDto value)  $default,){
final _that = this;
switch (_that) {
case _SearchPageDto():
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

@optionalTypeArgs TResult? mapOrNull<TResult extends Object?>(TResult? Function( _SearchPageDto value)?  $default,){
final _that = this;
switch (_that) {
case _SearchPageDto() when $default != null:
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

@optionalTypeArgs TResult maybeWhen<TResult extends Object?>(TResult Function( List<SearchItemDto> items, @JsonKey(name: 'next_cursor')  String? nextCursor, @JsonKey(name: 'total_estimate')  int? totalEstimate, @JsonKey(name: 'applied_radius_m')  int? appliedRadiusM)?  $default,{required TResult orElse(),}) {final _that = this;
switch (_that) {
case _SearchPageDto() when $default != null:
return $default(_that.items,_that.nextCursor,_that.totalEstimate,_that.appliedRadiusM);case _:
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

@optionalTypeArgs TResult when<TResult extends Object?>(TResult Function( List<SearchItemDto> items, @JsonKey(name: 'next_cursor')  String? nextCursor, @JsonKey(name: 'total_estimate')  int? totalEstimate, @JsonKey(name: 'applied_radius_m')  int? appliedRadiusM)  $default,) {final _that = this;
switch (_that) {
case _SearchPageDto():
return $default(_that.items,_that.nextCursor,_that.totalEstimate,_that.appliedRadiusM);case _:
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

@optionalTypeArgs TResult? whenOrNull<TResult extends Object?>(TResult? Function( List<SearchItemDto> items, @JsonKey(name: 'next_cursor')  String? nextCursor, @JsonKey(name: 'total_estimate')  int? totalEstimate, @JsonKey(name: 'applied_radius_m')  int? appliedRadiusM)?  $default,) {final _that = this;
switch (_that) {
case _SearchPageDto() when $default != null:
return $default(_that.items,_that.nextCursor,_that.totalEstimate,_that.appliedRadiusM);case _:
  return null;

}
}

}

/// @nodoc
@JsonSerializable()

class _SearchPageDto implements SearchPageDto {
  const _SearchPageDto({final  List<SearchItemDto> items = const <SearchItemDto>[], @JsonKey(name: 'next_cursor') this.nextCursor, @JsonKey(name: 'total_estimate') this.totalEstimate, @JsonKey(name: 'applied_radius_m') this.appliedRadiusM}): _items = items;
  factory _SearchPageDto.fromJson(Map<String, dynamic> json) => _$SearchPageDtoFromJson(json);

 final  List<SearchItemDto> _items;
@override@JsonKey() List<SearchItemDto> get items {
  if (_items is EqualUnmodifiableListView) return _items;
  // ignore: implicit_dynamic_type
  return EqualUnmodifiableListView(_items);
}

@override@JsonKey(name: 'next_cursor') final  String? nextCursor;
@override@JsonKey(name: 'total_estimate') final  int? totalEstimate;
@override@JsonKey(name: 'applied_radius_m') final  int? appliedRadiusM;

/// Create a copy of SearchPageDto
/// with the given fields replaced by the non-null parameter values.
@override @JsonKey(includeFromJson: false, includeToJson: false)
@pragma('vm:prefer-inline')
_$SearchPageDtoCopyWith<_SearchPageDto> get copyWith => __$SearchPageDtoCopyWithImpl<_SearchPageDto>(this, _$identity);

@override
Map<String, dynamic> toJson() {
  return _$SearchPageDtoToJson(this, );
}

@override
bool operator ==(Object other) {
  return identical(this, other) || (other.runtimeType == runtimeType&&other is _SearchPageDto&&const DeepCollectionEquality().equals(other._items, _items)&&(identical(other.nextCursor, nextCursor) || other.nextCursor == nextCursor)&&(identical(other.totalEstimate, totalEstimate) || other.totalEstimate == totalEstimate)&&(identical(other.appliedRadiusM, appliedRadiusM) || other.appliedRadiusM == appliedRadiusM));
}

@JsonKey(includeFromJson: false, includeToJson: false)
@override
int get hashCode => Object.hash(runtimeType,const DeepCollectionEquality().hash(_items),nextCursor,totalEstimate,appliedRadiusM);

@override
String toString() {
  return 'SearchPageDto(items: $items, nextCursor: $nextCursor, totalEstimate: $totalEstimate, appliedRadiusM: $appliedRadiusM)';
}


}

/// @nodoc
abstract mixin class _$SearchPageDtoCopyWith<$Res> implements $SearchPageDtoCopyWith<$Res> {
  factory _$SearchPageDtoCopyWith(_SearchPageDto value, $Res Function(_SearchPageDto) _then) = __$SearchPageDtoCopyWithImpl;
@override @useResult
$Res call({
 List<SearchItemDto> items,@JsonKey(name: 'next_cursor') String? nextCursor,@JsonKey(name: 'total_estimate') int? totalEstimate,@JsonKey(name: 'applied_radius_m') int? appliedRadiusM
});




}
/// @nodoc
class __$SearchPageDtoCopyWithImpl<$Res>
    implements _$SearchPageDtoCopyWith<$Res> {
  __$SearchPageDtoCopyWithImpl(this._self, this._then);

  final _SearchPageDto _self;
  final $Res Function(_SearchPageDto) _then;

/// Create a copy of SearchPageDto
/// with the given fields replaced by the non-null parameter values.
@override @pragma('vm:prefer-inline') $Res call({Object? items = null,Object? nextCursor = freezed,Object? totalEstimate = freezed,Object? appliedRadiusM = freezed,}) {
  return _then(_SearchPageDto(
items: null == items ? _self._items : items // ignore: cast_nullable_to_non_nullable
as List<SearchItemDto>,nextCursor: freezed == nextCursor ? _self.nextCursor : nextCursor // ignore: cast_nullable_to_non_nullable
as String?,totalEstimate: freezed == totalEstimate ? _self.totalEstimate : totalEstimate // ignore: cast_nullable_to_non_nullable
as int?,appliedRadiusM: freezed == appliedRadiusM ? _self.appliedRadiusM : appliedRadiusM // ignore: cast_nullable_to_non_nullable
as int?,
  ));
}


}


/// @nodoc
mixin _$SuggestionDto {

 String get kind; String get id; String get label; String? get sublabel; String get slug;
/// Create a copy of SuggestionDto
/// with the given fields replaced by the non-null parameter values.
@JsonKey(includeFromJson: false, includeToJson: false)
@pragma('vm:prefer-inline')
$SuggestionDtoCopyWith<SuggestionDto> get copyWith => _$SuggestionDtoCopyWithImpl<SuggestionDto>(this as SuggestionDto, _$identity);

  /// Serializes this SuggestionDto to a JSON map.
  Map<String, dynamic> toJson();


@override
bool operator ==(Object other) {
  return identical(this, other) || (other.runtimeType == runtimeType&&other is SuggestionDto&&(identical(other.kind, kind) || other.kind == kind)&&(identical(other.id, id) || other.id == id)&&(identical(other.label, label) || other.label == label)&&(identical(other.sublabel, sublabel) || other.sublabel == sublabel)&&(identical(other.slug, slug) || other.slug == slug));
}

@JsonKey(includeFromJson: false, includeToJson: false)
@override
int get hashCode => Object.hash(runtimeType,kind,id,label,sublabel,slug);

@override
String toString() {
  return 'SuggestionDto(kind: $kind, id: $id, label: $label, sublabel: $sublabel, slug: $slug)';
}


}

/// @nodoc
abstract mixin class $SuggestionDtoCopyWith<$Res>  {
  factory $SuggestionDtoCopyWith(SuggestionDto value, $Res Function(SuggestionDto) _then) = _$SuggestionDtoCopyWithImpl;
@useResult
$Res call({
 String kind, String id, String label, String? sublabel, String slug
});




}
/// @nodoc
class _$SuggestionDtoCopyWithImpl<$Res>
    implements $SuggestionDtoCopyWith<$Res> {
  _$SuggestionDtoCopyWithImpl(this._self, this._then);

  final SuggestionDto _self;
  final $Res Function(SuggestionDto) _then;

/// Create a copy of SuggestionDto
/// with the given fields replaced by the non-null parameter values.
@pragma('vm:prefer-inline') @override $Res call({Object? kind = null,Object? id = null,Object? label = null,Object? sublabel = freezed,Object? slug = null,}) {
  return _then(_self.copyWith(
kind: null == kind ? _self.kind : kind // ignore: cast_nullable_to_non_nullable
as String,id: null == id ? _self.id : id // ignore: cast_nullable_to_non_nullable
as String,label: null == label ? _self.label : label // ignore: cast_nullable_to_non_nullable
as String,sublabel: freezed == sublabel ? _self.sublabel : sublabel // ignore: cast_nullable_to_non_nullable
as String?,slug: null == slug ? _self.slug : slug // ignore: cast_nullable_to_non_nullable
as String,
  ));
}

}


/// Adds pattern-matching-related methods to [SuggestionDto].
extension SuggestionDtoPatterns on SuggestionDto {
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

@optionalTypeArgs TResult maybeMap<TResult extends Object?>(TResult Function( _SuggestionDto value)?  $default,{required TResult orElse(),}){
final _that = this;
switch (_that) {
case _SuggestionDto() when $default != null:
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

@optionalTypeArgs TResult map<TResult extends Object?>(TResult Function( _SuggestionDto value)  $default,){
final _that = this;
switch (_that) {
case _SuggestionDto():
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

@optionalTypeArgs TResult? mapOrNull<TResult extends Object?>(TResult? Function( _SuggestionDto value)?  $default,){
final _that = this;
switch (_that) {
case _SuggestionDto() when $default != null:
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

@optionalTypeArgs TResult maybeWhen<TResult extends Object?>(TResult Function( String kind,  String id,  String label,  String? sublabel,  String slug)?  $default,{required TResult orElse(),}) {final _that = this;
switch (_that) {
case _SuggestionDto() when $default != null:
return $default(_that.kind,_that.id,_that.label,_that.sublabel,_that.slug);case _:
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

@optionalTypeArgs TResult when<TResult extends Object?>(TResult Function( String kind,  String id,  String label,  String? sublabel,  String slug)  $default,) {final _that = this;
switch (_that) {
case _SuggestionDto():
return $default(_that.kind,_that.id,_that.label,_that.sublabel,_that.slug);case _:
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

@optionalTypeArgs TResult? whenOrNull<TResult extends Object?>(TResult? Function( String kind,  String id,  String label,  String? sublabel,  String slug)?  $default,) {final _that = this;
switch (_that) {
case _SuggestionDto() when $default != null:
return $default(_that.kind,_that.id,_that.label,_that.sublabel,_that.slug);case _:
  return null;

}
}

}

/// @nodoc
@JsonSerializable()

class _SuggestionDto implements SuggestionDto {
  const _SuggestionDto({required this.kind, required this.id, required this.label, this.sublabel, this.slug = ''});
  factory _SuggestionDto.fromJson(Map<String, dynamic> json) => _$SuggestionDtoFromJson(json);

@override final  String kind;
@override final  String id;
@override final  String label;
@override final  String? sublabel;
@override@JsonKey() final  String slug;

/// Create a copy of SuggestionDto
/// with the given fields replaced by the non-null parameter values.
@override @JsonKey(includeFromJson: false, includeToJson: false)
@pragma('vm:prefer-inline')
_$SuggestionDtoCopyWith<_SuggestionDto> get copyWith => __$SuggestionDtoCopyWithImpl<_SuggestionDto>(this, _$identity);

@override
Map<String, dynamic> toJson() {
  return _$SuggestionDtoToJson(this, );
}

@override
bool operator ==(Object other) {
  return identical(this, other) || (other.runtimeType == runtimeType&&other is _SuggestionDto&&(identical(other.kind, kind) || other.kind == kind)&&(identical(other.id, id) || other.id == id)&&(identical(other.label, label) || other.label == label)&&(identical(other.sublabel, sublabel) || other.sublabel == sublabel)&&(identical(other.slug, slug) || other.slug == slug));
}

@JsonKey(includeFromJson: false, includeToJson: false)
@override
int get hashCode => Object.hash(runtimeType,kind,id,label,sublabel,slug);

@override
String toString() {
  return 'SuggestionDto(kind: $kind, id: $id, label: $label, sublabel: $sublabel, slug: $slug)';
}


}

/// @nodoc
abstract mixin class _$SuggestionDtoCopyWith<$Res> implements $SuggestionDtoCopyWith<$Res> {
  factory _$SuggestionDtoCopyWith(_SuggestionDto value, $Res Function(_SuggestionDto) _then) = __$SuggestionDtoCopyWithImpl;
@override @useResult
$Res call({
 String kind, String id, String label, String? sublabel, String slug
});




}
/// @nodoc
class __$SuggestionDtoCopyWithImpl<$Res>
    implements _$SuggestionDtoCopyWith<$Res> {
  __$SuggestionDtoCopyWithImpl(this._self, this._then);

  final _SuggestionDto _self;
  final $Res Function(_SuggestionDto) _then;

/// Create a copy of SuggestionDto
/// with the given fields replaced by the non-null parameter values.
@override @pragma('vm:prefer-inline') $Res call({Object? kind = null,Object? id = null,Object? label = null,Object? sublabel = freezed,Object? slug = null,}) {
  return _then(_SuggestionDto(
kind: null == kind ? _self.kind : kind // ignore: cast_nullable_to_non_nullable
as String,id: null == id ? _self.id : id // ignore: cast_nullable_to_non_nullable
as String,label: null == label ? _self.label : label // ignore: cast_nullable_to_non_nullable
as String,sublabel: freezed == sublabel ? _self.sublabel : sublabel // ignore: cast_nullable_to_non_nullable
as String?,slug: null == slug ? _self.slug : slug // ignore: cast_nullable_to_non_nullable
as String,
  ));
}


}


/// @nodoc
mixin _$AmenityDto {

 String get code; String get label; String get category; String? get icon;@JsonKey(name: 'is_filterable') bool get isFilterable;
/// Create a copy of AmenityDto
/// with the given fields replaced by the non-null parameter values.
@JsonKey(includeFromJson: false, includeToJson: false)
@pragma('vm:prefer-inline')
$AmenityDtoCopyWith<AmenityDto> get copyWith => _$AmenityDtoCopyWithImpl<AmenityDto>(this as AmenityDto, _$identity);

  /// Serializes this AmenityDto to a JSON map.
  Map<String, dynamic> toJson();


@override
bool operator ==(Object other) {
  return identical(this, other) || (other.runtimeType == runtimeType&&other is AmenityDto&&(identical(other.code, code) || other.code == code)&&(identical(other.label, label) || other.label == label)&&(identical(other.category, category) || other.category == category)&&(identical(other.icon, icon) || other.icon == icon)&&(identical(other.isFilterable, isFilterable) || other.isFilterable == isFilterable));
}

@JsonKey(includeFromJson: false, includeToJson: false)
@override
int get hashCode => Object.hash(runtimeType,code,label,category,icon,isFilterable);

@override
String toString() {
  return 'AmenityDto(code: $code, label: $label, category: $category, icon: $icon, isFilterable: $isFilterable)';
}


}

/// @nodoc
abstract mixin class $AmenityDtoCopyWith<$Res>  {
  factory $AmenityDtoCopyWith(AmenityDto value, $Res Function(AmenityDto) _then) = _$AmenityDtoCopyWithImpl;
@useResult
$Res call({
 String code, String label, String category, String? icon,@JsonKey(name: 'is_filterable') bool isFilterable
});




}
/// @nodoc
class _$AmenityDtoCopyWithImpl<$Res>
    implements $AmenityDtoCopyWith<$Res> {
  _$AmenityDtoCopyWithImpl(this._self, this._then);

  final AmenityDto _self;
  final $Res Function(AmenityDto) _then;

/// Create a copy of AmenityDto
/// with the given fields replaced by the non-null parameter values.
@pragma('vm:prefer-inline') @override $Res call({Object? code = null,Object? label = null,Object? category = null,Object? icon = freezed,Object? isFilterable = null,}) {
  return _then(_self.copyWith(
code: null == code ? _self.code : code // ignore: cast_nullable_to_non_nullable
as String,label: null == label ? _self.label : label // ignore: cast_nullable_to_non_nullable
as String,category: null == category ? _self.category : category // ignore: cast_nullable_to_non_nullable
as String,icon: freezed == icon ? _self.icon : icon // ignore: cast_nullable_to_non_nullable
as String?,isFilterable: null == isFilterable ? _self.isFilterable : isFilterable // ignore: cast_nullable_to_non_nullable
as bool,
  ));
}

}


/// Adds pattern-matching-related methods to [AmenityDto].
extension AmenityDtoPatterns on AmenityDto {
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

@optionalTypeArgs TResult maybeMap<TResult extends Object?>(TResult Function( _AmenityDto value)?  $default,{required TResult orElse(),}){
final _that = this;
switch (_that) {
case _AmenityDto() when $default != null:
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

@optionalTypeArgs TResult map<TResult extends Object?>(TResult Function( _AmenityDto value)  $default,){
final _that = this;
switch (_that) {
case _AmenityDto():
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

@optionalTypeArgs TResult? mapOrNull<TResult extends Object?>(TResult? Function( _AmenityDto value)?  $default,){
final _that = this;
switch (_that) {
case _AmenityDto() when $default != null:
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

@optionalTypeArgs TResult maybeWhen<TResult extends Object?>(TResult Function( String code,  String label,  String category,  String? icon, @JsonKey(name: 'is_filterable')  bool isFilterable)?  $default,{required TResult orElse(),}) {final _that = this;
switch (_that) {
case _AmenityDto() when $default != null:
return $default(_that.code,_that.label,_that.category,_that.icon,_that.isFilterable);case _:
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

@optionalTypeArgs TResult when<TResult extends Object?>(TResult Function( String code,  String label,  String category,  String? icon, @JsonKey(name: 'is_filterable')  bool isFilterable)  $default,) {final _that = this;
switch (_that) {
case _AmenityDto():
return $default(_that.code,_that.label,_that.category,_that.icon,_that.isFilterable);case _:
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

@optionalTypeArgs TResult? whenOrNull<TResult extends Object?>(TResult? Function( String code,  String label,  String category,  String? icon, @JsonKey(name: 'is_filterable')  bool isFilterable)?  $default,) {final _that = this;
switch (_that) {
case _AmenityDto() when $default != null:
return $default(_that.code,_that.label,_that.category,_that.icon,_that.isFilterable);case _:
  return null;

}
}

}

/// @nodoc
@JsonSerializable()

class _AmenityDto implements AmenityDto {
  const _AmenityDto({required this.code, required this.label, this.category = '', this.icon, @JsonKey(name: 'is_filterable') this.isFilterable = true});
  factory _AmenityDto.fromJson(Map<String, dynamic> json) => _$AmenityDtoFromJson(json);

@override final  String code;
@override final  String label;
@override@JsonKey() final  String category;
@override final  String? icon;
@override@JsonKey(name: 'is_filterable') final  bool isFilterable;

/// Create a copy of AmenityDto
/// with the given fields replaced by the non-null parameter values.
@override @JsonKey(includeFromJson: false, includeToJson: false)
@pragma('vm:prefer-inline')
_$AmenityDtoCopyWith<_AmenityDto> get copyWith => __$AmenityDtoCopyWithImpl<_AmenityDto>(this, _$identity);

@override
Map<String, dynamic> toJson() {
  return _$AmenityDtoToJson(this, );
}

@override
bool operator ==(Object other) {
  return identical(this, other) || (other.runtimeType == runtimeType&&other is _AmenityDto&&(identical(other.code, code) || other.code == code)&&(identical(other.label, label) || other.label == label)&&(identical(other.category, category) || other.category == category)&&(identical(other.icon, icon) || other.icon == icon)&&(identical(other.isFilterable, isFilterable) || other.isFilterable == isFilterable));
}

@JsonKey(includeFromJson: false, includeToJson: false)
@override
int get hashCode => Object.hash(runtimeType,code,label,category,icon,isFilterable);

@override
String toString() {
  return 'AmenityDto(code: $code, label: $label, category: $category, icon: $icon, isFilterable: $isFilterable)';
}


}

/// @nodoc
abstract mixin class _$AmenityDtoCopyWith<$Res> implements $AmenityDtoCopyWith<$Res> {
  factory _$AmenityDtoCopyWith(_AmenityDto value, $Res Function(_AmenityDto) _then) = __$AmenityDtoCopyWithImpl;
@override @useResult
$Res call({
 String code, String label, String category, String? icon,@JsonKey(name: 'is_filterable') bool isFilterable
});




}
/// @nodoc
class __$AmenityDtoCopyWithImpl<$Res>
    implements _$AmenityDtoCopyWith<$Res> {
  __$AmenityDtoCopyWithImpl(this._self, this._then);

  final _AmenityDto _self;
  final $Res Function(_AmenityDto) _then;

/// Create a copy of AmenityDto
/// with the given fields replaced by the non-null parameter values.
@override @pragma('vm:prefer-inline') $Res call({Object? code = null,Object? label = null,Object? category = null,Object? icon = freezed,Object? isFilterable = null,}) {
  return _then(_AmenityDto(
code: null == code ? _self.code : code // ignore: cast_nullable_to_non_nullable
as String,label: null == label ? _self.label : label // ignore: cast_nullable_to_non_nullable
as String,category: null == category ? _self.category : category // ignore: cast_nullable_to_non_nullable
as String,icon: freezed == icon ? _self.icon : icon // ignore: cast_nullable_to_non_nullable
as String?,isFilterable: null == isFilterable ? _self.isFilterable : isFilterable // ignore: cast_nullable_to_non_nullable
as bool,
  ));
}


}


/// @nodoc
mixin _$QuoteNightDto {

 String get date;@JsonKey(name: 'amount_minor') int get amountMinor; String get source;
/// Create a copy of QuoteNightDto
/// with the given fields replaced by the non-null parameter values.
@JsonKey(includeFromJson: false, includeToJson: false)
@pragma('vm:prefer-inline')
$QuoteNightDtoCopyWith<QuoteNightDto> get copyWith => _$QuoteNightDtoCopyWithImpl<QuoteNightDto>(this as QuoteNightDto, _$identity);

  /// Serializes this QuoteNightDto to a JSON map.
  Map<String, dynamic> toJson();


@override
bool operator ==(Object other) {
  return identical(this, other) || (other.runtimeType == runtimeType&&other is QuoteNightDto&&(identical(other.date, date) || other.date == date)&&(identical(other.amountMinor, amountMinor) || other.amountMinor == amountMinor)&&(identical(other.source, source) || other.source == source));
}

@JsonKey(includeFromJson: false, includeToJson: false)
@override
int get hashCode => Object.hash(runtimeType,date,amountMinor,source);

@override
String toString() {
  return 'QuoteNightDto(date: $date, amountMinor: $amountMinor, source: $source)';
}


}

/// @nodoc
abstract mixin class $QuoteNightDtoCopyWith<$Res>  {
  factory $QuoteNightDtoCopyWith(QuoteNightDto value, $Res Function(QuoteNightDto) _then) = _$QuoteNightDtoCopyWithImpl;
@useResult
$Res call({
 String date,@JsonKey(name: 'amount_minor') int amountMinor, String source
});




}
/// @nodoc
class _$QuoteNightDtoCopyWithImpl<$Res>
    implements $QuoteNightDtoCopyWith<$Res> {
  _$QuoteNightDtoCopyWithImpl(this._self, this._then);

  final QuoteNightDto _self;
  final $Res Function(QuoteNightDto) _then;

/// Create a copy of QuoteNightDto
/// with the given fields replaced by the non-null parameter values.
@pragma('vm:prefer-inline') @override $Res call({Object? date = null,Object? amountMinor = null,Object? source = null,}) {
  return _then(_self.copyWith(
date: null == date ? _self.date : date // ignore: cast_nullable_to_non_nullable
as String,amountMinor: null == amountMinor ? _self.amountMinor : amountMinor // ignore: cast_nullable_to_non_nullable
as int,source: null == source ? _self.source : source // ignore: cast_nullable_to_non_nullable
as String,
  ));
}

}


/// Adds pattern-matching-related methods to [QuoteNightDto].
extension QuoteNightDtoPatterns on QuoteNightDto {
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

@optionalTypeArgs TResult maybeMap<TResult extends Object?>(TResult Function( _QuoteNightDto value)?  $default,{required TResult orElse(),}){
final _that = this;
switch (_that) {
case _QuoteNightDto() when $default != null:
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

@optionalTypeArgs TResult map<TResult extends Object?>(TResult Function( _QuoteNightDto value)  $default,){
final _that = this;
switch (_that) {
case _QuoteNightDto():
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

@optionalTypeArgs TResult? mapOrNull<TResult extends Object?>(TResult? Function( _QuoteNightDto value)?  $default,){
final _that = this;
switch (_that) {
case _QuoteNightDto() when $default != null:
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

@optionalTypeArgs TResult maybeWhen<TResult extends Object?>(TResult Function( String date, @JsonKey(name: 'amount_minor')  int amountMinor,  String source)?  $default,{required TResult orElse(),}) {final _that = this;
switch (_that) {
case _QuoteNightDto() when $default != null:
return $default(_that.date,_that.amountMinor,_that.source);case _:
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

@optionalTypeArgs TResult when<TResult extends Object?>(TResult Function( String date, @JsonKey(name: 'amount_minor')  int amountMinor,  String source)  $default,) {final _that = this;
switch (_that) {
case _QuoteNightDto():
return $default(_that.date,_that.amountMinor,_that.source);case _:
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

@optionalTypeArgs TResult? whenOrNull<TResult extends Object?>(TResult? Function( String date, @JsonKey(name: 'amount_minor')  int amountMinor,  String source)?  $default,) {final _that = this;
switch (_that) {
case _QuoteNightDto() when $default != null:
return $default(_that.date,_that.amountMinor,_that.source);case _:
  return null;

}
}

}

/// @nodoc
@JsonSerializable()

class _QuoteNightDto implements QuoteNightDto {
  const _QuoteNightDto({required this.date, @JsonKey(name: 'amount_minor') this.amountMinor = 0, this.source = ''});
  factory _QuoteNightDto.fromJson(Map<String, dynamic> json) => _$QuoteNightDtoFromJson(json);

@override final  String date;
@override@JsonKey(name: 'amount_minor') final  int amountMinor;
@override@JsonKey() final  String source;

/// Create a copy of QuoteNightDto
/// with the given fields replaced by the non-null parameter values.
@override @JsonKey(includeFromJson: false, includeToJson: false)
@pragma('vm:prefer-inline')
_$QuoteNightDtoCopyWith<_QuoteNightDto> get copyWith => __$QuoteNightDtoCopyWithImpl<_QuoteNightDto>(this, _$identity);

@override
Map<String, dynamic> toJson() {
  return _$QuoteNightDtoToJson(this, );
}

@override
bool operator ==(Object other) {
  return identical(this, other) || (other.runtimeType == runtimeType&&other is _QuoteNightDto&&(identical(other.date, date) || other.date == date)&&(identical(other.amountMinor, amountMinor) || other.amountMinor == amountMinor)&&(identical(other.source, source) || other.source == source));
}

@JsonKey(includeFromJson: false, includeToJson: false)
@override
int get hashCode => Object.hash(runtimeType,date,amountMinor,source);

@override
String toString() {
  return 'QuoteNightDto(date: $date, amountMinor: $amountMinor, source: $source)';
}


}

/// @nodoc
abstract mixin class _$QuoteNightDtoCopyWith<$Res> implements $QuoteNightDtoCopyWith<$Res> {
  factory _$QuoteNightDtoCopyWith(_QuoteNightDto value, $Res Function(_QuoteNightDto) _then) = __$QuoteNightDtoCopyWithImpl;
@override @useResult
$Res call({
 String date,@JsonKey(name: 'amount_minor') int amountMinor, String source
});




}
/// @nodoc
class __$QuoteNightDtoCopyWithImpl<$Res>
    implements _$QuoteNightDtoCopyWith<$Res> {
  __$QuoteNightDtoCopyWithImpl(this._self, this._then);

  final _QuoteNightDto _self;
  final $Res Function(_QuoteNightDto) _then;

/// Create a copy of QuoteNightDto
/// with the given fields replaced by the non-null parameter values.
@override @pragma('vm:prefer-inline') $Res call({Object? date = null,Object? amountMinor = null,Object? source = null,}) {
  return _then(_QuoteNightDto(
date: null == date ? _self.date : date // ignore: cast_nullable_to_non_nullable
as String,amountMinor: null == amountMinor ? _self.amountMinor : amountMinor // ignore: cast_nullable_to_non_nullable
as int,source: null == source ? _self.source : source // ignore: cast_nullable_to_non_nullable
as String,
  ));
}


}


/// @nodoc
mixin _$QuoteDto {

@JsonKey(name: 'room_type_id') String get roomTypeId; List<QuoteNightDto> get nights;@JsonKey(name: 'accommodation_minor') int get accommodationMinor;@JsonKey(name: 'extra_guest_minor') int get extraGuestMinor;@JsonKey(name: 'cleaning_fee_minor') int get cleaningFeeMinor;@JsonKey(name: 'tax_minor') int get taxMinor;@JsonKey(name: 'total_minor') int get totalMinor;@JsonKey(name: 'average_nightly_minor') int get averageNightlyMinor; String get currency;@JsonKey(name: 'is_available') bool get isAvailable;@JsonKey(name: 'unavailable_dates') List<String> get unavailableDates;
/// Create a copy of QuoteDto
/// with the given fields replaced by the non-null parameter values.
@JsonKey(includeFromJson: false, includeToJson: false)
@pragma('vm:prefer-inline')
$QuoteDtoCopyWith<QuoteDto> get copyWith => _$QuoteDtoCopyWithImpl<QuoteDto>(this as QuoteDto, _$identity);

  /// Serializes this QuoteDto to a JSON map.
  Map<String, dynamic> toJson();


@override
bool operator ==(Object other) {
  return identical(this, other) || (other.runtimeType == runtimeType&&other is QuoteDto&&(identical(other.roomTypeId, roomTypeId) || other.roomTypeId == roomTypeId)&&const DeepCollectionEquality().equals(other.nights, nights)&&(identical(other.accommodationMinor, accommodationMinor) || other.accommodationMinor == accommodationMinor)&&(identical(other.extraGuestMinor, extraGuestMinor) || other.extraGuestMinor == extraGuestMinor)&&(identical(other.cleaningFeeMinor, cleaningFeeMinor) || other.cleaningFeeMinor == cleaningFeeMinor)&&(identical(other.taxMinor, taxMinor) || other.taxMinor == taxMinor)&&(identical(other.totalMinor, totalMinor) || other.totalMinor == totalMinor)&&(identical(other.averageNightlyMinor, averageNightlyMinor) || other.averageNightlyMinor == averageNightlyMinor)&&(identical(other.currency, currency) || other.currency == currency)&&(identical(other.isAvailable, isAvailable) || other.isAvailable == isAvailable)&&const DeepCollectionEquality().equals(other.unavailableDates, unavailableDates));
}

@JsonKey(includeFromJson: false, includeToJson: false)
@override
int get hashCode => Object.hash(runtimeType,roomTypeId,const DeepCollectionEquality().hash(nights),accommodationMinor,extraGuestMinor,cleaningFeeMinor,taxMinor,totalMinor,averageNightlyMinor,currency,isAvailable,const DeepCollectionEquality().hash(unavailableDates));

@override
String toString() {
  return 'QuoteDto(roomTypeId: $roomTypeId, nights: $nights, accommodationMinor: $accommodationMinor, extraGuestMinor: $extraGuestMinor, cleaningFeeMinor: $cleaningFeeMinor, taxMinor: $taxMinor, totalMinor: $totalMinor, averageNightlyMinor: $averageNightlyMinor, currency: $currency, isAvailable: $isAvailable, unavailableDates: $unavailableDates)';
}


}

/// @nodoc
abstract mixin class $QuoteDtoCopyWith<$Res>  {
  factory $QuoteDtoCopyWith(QuoteDto value, $Res Function(QuoteDto) _then) = _$QuoteDtoCopyWithImpl;
@useResult
$Res call({
@JsonKey(name: 'room_type_id') String roomTypeId, List<QuoteNightDto> nights,@JsonKey(name: 'accommodation_minor') int accommodationMinor,@JsonKey(name: 'extra_guest_minor') int extraGuestMinor,@JsonKey(name: 'cleaning_fee_minor') int cleaningFeeMinor,@JsonKey(name: 'tax_minor') int taxMinor,@JsonKey(name: 'total_minor') int totalMinor,@JsonKey(name: 'average_nightly_minor') int averageNightlyMinor, String currency,@JsonKey(name: 'is_available') bool isAvailable,@JsonKey(name: 'unavailable_dates') List<String> unavailableDates
});




}
/// @nodoc
class _$QuoteDtoCopyWithImpl<$Res>
    implements $QuoteDtoCopyWith<$Res> {
  _$QuoteDtoCopyWithImpl(this._self, this._then);

  final QuoteDto _self;
  final $Res Function(QuoteDto) _then;

/// Create a copy of QuoteDto
/// with the given fields replaced by the non-null parameter values.
@pragma('vm:prefer-inline') @override $Res call({Object? roomTypeId = null,Object? nights = null,Object? accommodationMinor = null,Object? extraGuestMinor = null,Object? cleaningFeeMinor = null,Object? taxMinor = null,Object? totalMinor = null,Object? averageNightlyMinor = null,Object? currency = null,Object? isAvailable = null,Object? unavailableDates = null,}) {
  return _then(_self.copyWith(
roomTypeId: null == roomTypeId ? _self.roomTypeId : roomTypeId // ignore: cast_nullable_to_non_nullable
as String,nights: null == nights ? _self.nights : nights // ignore: cast_nullable_to_non_nullable
as List<QuoteNightDto>,accommodationMinor: null == accommodationMinor ? _self.accommodationMinor : accommodationMinor // ignore: cast_nullable_to_non_nullable
as int,extraGuestMinor: null == extraGuestMinor ? _self.extraGuestMinor : extraGuestMinor // ignore: cast_nullable_to_non_nullable
as int,cleaningFeeMinor: null == cleaningFeeMinor ? _self.cleaningFeeMinor : cleaningFeeMinor // ignore: cast_nullable_to_non_nullable
as int,taxMinor: null == taxMinor ? _self.taxMinor : taxMinor // ignore: cast_nullable_to_non_nullable
as int,totalMinor: null == totalMinor ? _self.totalMinor : totalMinor // ignore: cast_nullable_to_non_nullable
as int,averageNightlyMinor: null == averageNightlyMinor ? _self.averageNightlyMinor : averageNightlyMinor // ignore: cast_nullable_to_non_nullable
as int,currency: null == currency ? _self.currency : currency // ignore: cast_nullable_to_non_nullable
as String,isAvailable: null == isAvailable ? _self.isAvailable : isAvailable // ignore: cast_nullable_to_non_nullable
as bool,unavailableDates: null == unavailableDates ? _self.unavailableDates : unavailableDates // ignore: cast_nullable_to_non_nullable
as List<String>,
  ));
}

}


/// Adds pattern-matching-related methods to [QuoteDto].
extension QuoteDtoPatterns on QuoteDto {
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

@optionalTypeArgs TResult maybeMap<TResult extends Object?>(TResult Function( _QuoteDto value)?  $default,{required TResult orElse(),}){
final _that = this;
switch (_that) {
case _QuoteDto() when $default != null:
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

@optionalTypeArgs TResult map<TResult extends Object?>(TResult Function( _QuoteDto value)  $default,){
final _that = this;
switch (_that) {
case _QuoteDto():
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

@optionalTypeArgs TResult? mapOrNull<TResult extends Object?>(TResult? Function( _QuoteDto value)?  $default,){
final _that = this;
switch (_that) {
case _QuoteDto() when $default != null:
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

@optionalTypeArgs TResult maybeWhen<TResult extends Object?>(TResult Function(@JsonKey(name: 'room_type_id')  String roomTypeId,  List<QuoteNightDto> nights, @JsonKey(name: 'accommodation_minor')  int accommodationMinor, @JsonKey(name: 'extra_guest_minor')  int extraGuestMinor, @JsonKey(name: 'cleaning_fee_minor')  int cleaningFeeMinor, @JsonKey(name: 'tax_minor')  int taxMinor, @JsonKey(name: 'total_minor')  int totalMinor, @JsonKey(name: 'average_nightly_minor')  int averageNightlyMinor,  String currency, @JsonKey(name: 'is_available')  bool isAvailable, @JsonKey(name: 'unavailable_dates')  List<String> unavailableDates)?  $default,{required TResult orElse(),}) {final _that = this;
switch (_that) {
case _QuoteDto() when $default != null:
return $default(_that.roomTypeId,_that.nights,_that.accommodationMinor,_that.extraGuestMinor,_that.cleaningFeeMinor,_that.taxMinor,_that.totalMinor,_that.averageNightlyMinor,_that.currency,_that.isAvailable,_that.unavailableDates);case _:
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

@optionalTypeArgs TResult when<TResult extends Object?>(TResult Function(@JsonKey(name: 'room_type_id')  String roomTypeId,  List<QuoteNightDto> nights, @JsonKey(name: 'accommodation_minor')  int accommodationMinor, @JsonKey(name: 'extra_guest_minor')  int extraGuestMinor, @JsonKey(name: 'cleaning_fee_minor')  int cleaningFeeMinor, @JsonKey(name: 'tax_minor')  int taxMinor, @JsonKey(name: 'total_minor')  int totalMinor, @JsonKey(name: 'average_nightly_minor')  int averageNightlyMinor,  String currency, @JsonKey(name: 'is_available')  bool isAvailable, @JsonKey(name: 'unavailable_dates')  List<String> unavailableDates)  $default,) {final _that = this;
switch (_that) {
case _QuoteDto():
return $default(_that.roomTypeId,_that.nights,_that.accommodationMinor,_that.extraGuestMinor,_that.cleaningFeeMinor,_that.taxMinor,_that.totalMinor,_that.averageNightlyMinor,_that.currency,_that.isAvailable,_that.unavailableDates);case _:
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

@optionalTypeArgs TResult? whenOrNull<TResult extends Object?>(TResult? Function(@JsonKey(name: 'room_type_id')  String roomTypeId,  List<QuoteNightDto> nights, @JsonKey(name: 'accommodation_minor')  int accommodationMinor, @JsonKey(name: 'extra_guest_minor')  int extraGuestMinor, @JsonKey(name: 'cleaning_fee_minor')  int cleaningFeeMinor, @JsonKey(name: 'tax_minor')  int taxMinor, @JsonKey(name: 'total_minor')  int totalMinor, @JsonKey(name: 'average_nightly_minor')  int averageNightlyMinor,  String currency, @JsonKey(name: 'is_available')  bool isAvailable, @JsonKey(name: 'unavailable_dates')  List<String> unavailableDates)?  $default,) {final _that = this;
switch (_that) {
case _QuoteDto() when $default != null:
return $default(_that.roomTypeId,_that.nights,_that.accommodationMinor,_that.extraGuestMinor,_that.cleaningFeeMinor,_that.taxMinor,_that.totalMinor,_that.averageNightlyMinor,_that.currency,_that.isAvailable,_that.unavailableDates);case _:
  return null;

}
}

}

/// @nodoc
@JsonSerializable()

class _QuoteDto implements QuoteDto {
  const _QuoteDto({@JsonKey(name: 'room_type_id') this.roomTypeId = '', final  List<QuoteNightDto> nights = const <QuoteNightDto>[], @JsonKey(name: 'accommodation_minor') this.accommodationMinor = 0, @JsonKey(name: 'extra_guest_minor') this.extraGuestMinor = 0, @JsonKey(name: 'cleaning_fee_minor') this.cleaningFeeMinor = 0, @JsonKey(name: 'tax_minor') this.taxMinor = 0, @JsonKey(name: 'total_minor') this.totalMinor = 0, @JsonKey(name: 'average_nightly_minor') this.averageNightlyMinor = 0, this.currency = 'INR', @JsonKey(name: 'is_available') this.isAvailable = false, @JsonKey(name: 'unavailable_dates') final  List<String> unavailableDates = const <String>[]}): _nights = nights,_unavailableDates = unavailableDates;
  factory _QuoteDto.fromJson(Map<String, dynamic> json) => _$QuoteDtoFromJson(json);

@override@JsonKey(name: 'room_type_id') final  String roomTypeId;
 final  List<QuoteNightDto> _nights;
@override@JsonKey() List<QuoteNightDto> get nights {
  if (_nights is EqualUnmodifiableListView) return _nights;
  // ignore: implicit_dynamic_type
  return EqualUnmodifiableListView(_nights);
}

@override@JsonKey(name: 'accommodation_minor') final  int accommodationMinor;
@override@JsonKey(name: 'extra_guest_minor') final  int extraGuestMinor;
@override@JsonKey(name: 'cleaning_fee_minor') final  int cleaningFeeMinor;
@override@JsonKey(name: 'tax_minor') final  int taxMinor;
@override@JsonKey(name: 'total_minor') final  int totalMinor;
@override@JsonKey(name: 'average_nightly_minor') final  int averageNightlyMinor;
@override@JsonKey() final  String currency;
@override@JsonKey(name: 'is_available') final  bool isAvailable;
 final  List<String> _unavailableDates;
@override@JsonKey(name: 'unavailable_dates') List<String> get unavailableDates {
  if (_unavailableDates is EqualUnmodifiableListView) return _unavailableDates;
  // ignore: implicit_dynamic_type
  return EqualUnmodifiableListView(_unavailableDates);
}


/// Create a copy of QuoteDto
/// with the given fields replaced by the non-null parameter values.
@override @JsonKey(includeFromJson: false, includeToJson: false)
@pragma('vm:prefer-inline')
_$QuoteDtoCopyWith<_QuoteDto> get copyWith => __$QuoteDtoCopyWithImpl<_QuoteDto>(this, _$identity);

@override
Map<String, dynamic> toJson() {
  return _$QuoteDtoToJson(this, );
}

@override
bool operator ==(Object other) {
  return identical(this, other) || (other.runtimeType == runtimeType&&other is _QuoteDto&&(identical(other.roomTypeId, roomTypeId) || other.roomTypeId == roomTypeId)&&const DeepCollectionEquality().equals(other._nights, _nights)&&(identical(other.accommodationMinor, accommodationMinor) || other.accommodationMinor == accommodationMinor)&&(identical(other.extraGuestMinor, extraGuestMinor) || other.extraGuestMinor == extraGuestMinor)&&(identical(other.cleaningFeeMinor, cleaningFeeMinor) || other.cleaningFeeMinor == cleaningFeeMinor)&&(identical(other.taxMinor, taxMinor) || other.taxMinor == taxMinor)&&(identical(other.totalMinor, totalMinor) || other.totalMinor == totalMinor)&&(identical(other.averageNightlyMinor, averageNightlyMinor) || other.averageNightlyMinor == averageNightlyMinor)&&(identical(other.currency, currency) || other.currency == currency)&&(identical(other.isAvailable, isAvailable) || other.isAvailable == isAvailable)&&const DeepCollectionEquality().equals(other._unavailableDates, _unavailableDates));
}

@JsonKey(includeFromJson: false, includeToJson: false)
@override
int get hashCode => Object.hash(runtimeType,roomTypeId,const DeepCollectionEquality().hash(_nights),accommodationMinor,extraGuestMinor,cleaningFeeMinor,taxMinor,totalMinor,averageNightlyMinor,currency,isAvailable,const DeepCollectionEquality().hash(_unavailableDates));

@override
String toString() {
  return 'QuoteDto(roomTypeId: $roomTypeId, nights: $nights, accommodationMinor: $accommodationMinor, extraGuestMinor: $extraGuestMinor, cleaningFeeMinor: $cleaningFeeMinor, taxMinor: $taxMinor, totalMinor: $totalMinor, averageNightlyMinor: $averageNightlyMinor, currency: $currency, isAvailable: $isAvailable, unavailableDates: $unavailableDates)';
}


}

/// @nodoc
abstract mixin class _$QuoteDtoCopyWith<$Res> implements $QuoteDtoCopyWith<$Res> {
  factory _$QuoteDtoCopyWith(_QuoteDto value, $Res Function(_QuoteDto) _then) = __$QuoteDtoCopyWithImpl;
@override @useResult
$Res call({
@JsonKey(name: 'room_type_id') String roomTypeId, List<QuoteNightDto> nights,@JsonKey(name: 'accommodation_minor') int accommodationMinor,@JsonKey(name: 'extra_guest_minor') int extraGuestMinor,@JsonKey(name: 'cleaning_fee_minor') int cleaningFeeMinor,@JsonKey(name: 'tax_minor') int taxMinor,@JsonKey(name: 'total_minor') int totalMinor,@JsonKey(name: 'average_nightly_minor') int averageNightlyMinor, String currency,@JsonKey(name: 'is_available') bool isAvailable,@JsonKey(name: 'unavailable_dates') List<String> unavailableDates
});




}
/// @nodoc
class __$QuoteDtoCopyWithImpl<$Res>
    implements _$QuoteDtoCopyWith<$Res> {
  __$QuoteDtoCopyWithImpl(this._self, this._then);

  final _QuoteDto _self;
  final $Res Function(_QuoteDto) _then;

/// Create a copy of QuoteDto
/// with the given fields replaced by the non-null parameter values.
@override @pragma('vm:prefer-inline') $Res call({Object? roomTypeId = null,Object? nights = null,Object? accommodationMinor = null,Object? extraGuestMinor = null,Object? cleaningFeeMinor = null,Object? taxMinor = null,Object? totalMinor = null,Object? averageNightlyMinor = null,Object? currency = null,Object? isAvailable = null,Object? unavailableDates = null,}) {
  return _then(_QuoteDto(
roomTypeId: null == roomTypeId ? _self.roomTypeId : roomTypeId // ignore: cast_nullable_to_non_nullable
as String,nights: null == nights ? _self._nights : nights // ignore: cast_nullable_to_non_nullable
as List<QuoteNightDto>,accommodationMinor: null == accommodationMinor ? _self.accommodationMinor : accommodationMinor // ignore: cast_nullable_to_non_nullable
as int,extraGuestMinor: null == extraGuestMinor ? _self.extraGuestMinor : extraGuestMinor // ignore: cast_nullable_to_non_nullable
as int,cleaningFeeMinor: null == cleaningFeeMinor ? _self.cleaningFeeMinor : cleaningFeeMinor // ignore: cast_nullable_to_non_nullable
as int,taxMinor: null == taxMinor ? _self.taxMinor : taxMinor // ignore: cast_nullable_to_non_nullable
as int,totalMinor: null == totalMinor ? _self.totalMinor : totalMinor // ignore: cast_nullable_to_non_nullable
as int,averageNightlyMinor: null == averageNightlyMinor ? _self.averageNightlyMinor : averageNightlyMinor // ignore: cast_nullable_to_non_nullable
as int,currency: null == currency ? _self.currency : currency // ignore: cast_nullable_to_non_nullable
as String,isAvailable: null == isAvailable ? _self.isAvailable : isAvailable // ignore: cast_nullable_to_non_nullable
as bool,unavailableDates: null == unavailableDates ? _self._unavailableDates : unavailableDates // ignore: cast_nullable_to_non_nullable
as List<String>,
  ));
}


}


/// @nodoc
mixin _$CalendarDayDto {

 String get date;@JsonKey(name: 'is_blocked') bool get isBlocked;@JsonKey(name: 'units_available') int? get unitsAvailable;@JsonKey(name: 'rate_minor') int? get rateMinor;
/// Create a copy of CalendarDayDto
/// with the given fields replaced by the non-null parameter values.
@JsonKey(includeFromJson: false, includeToJson: false)
@pragma('vm:prefer-inline')
$CalendarDayDtoCopyWith<CalendarDayDto> get copyWith => _$CalendarDayDtoCopyWithImpl<CalendarDayDto>(this as CalendarDayDto, _$identity);

  /// Serializes this CalendarDayDto to a JSON map.
  Map<String, dynamic> toJson();


@override
bool operator ==(Object other) {
  return identical(this, other) || (other.runtimeType == runtimeType&&other is CalendarDayDto&&(identical(other.date, date) || other.date == date)&&(identical(other.isBlocked, isBlocked) || other.isBlocked == isBlocked)&&(identical(other.unitsAvailable, unitsAvailable) || other.unitsAvailable == unitsAvailable)&&(identical(other.rateMinor, rateMinor) || other.rateMinor == rateMinor));
}

@JsonKey(includeFromJson: false, includeToJson: false)
@override
int get hashCode => Object.hash(runtimeType,date,isBlocked,unitsAvailable,rateMinor);

@override
String toString() {
  return 'CalendarDayDto(date: $date, isBlocked: $isBlocked, unitsAvailable: $unitsAvailable, rateMinor: $rateMinor)';
}


}

/// @nodoc
abstract mixin class $CalendarDayDtoCopyWith<$Res>  {
  factory $CalendarDayDtoCopyWith(CalendarDayDto value, $Res Function(CalendarDayDto) _then) = _$CalendarDayDtoCopyWithImpl;
@useResult
$Res call({
 String date,@JsonKey(name: 'is_blocked') bool isBlocked,@JsonKey(name: 'units_available') int? unitsAvailable,@JsonKey(name: 'rate_minor') int? rateMinor
});




}
/// @nodoc
class _$CalendarDayDtoCopyWithImpl<$Res>
    implements $CalendarDayDtoCopyWith<$Res> {
  _$CalendarDayDtoCopyWithImpl(this._self, this._then);

  final CalendarDayDto _self;
  final $Res Function(CalendarDayDto) _then;

/// Create a copy of CalendarDayDto
/// with the given fields replaced by the non-null parameter values.
@pragma('vm:prefer-inline') @override $Res call({Object? date = null,Object? isBlocked = null,Object? unitsAvailable = freezed,Object? rateMinor = freezed,}) {
  return _then(_self.copyWith(
date: null == date ? _self.date : date // ignore: cast_nullable_to_non_nullable
as String,isBlocked: null == isBlocked ? _self.isBlocked : isBlocked // ignore: cast_nullable_to_non_nullable
as bool,unitsAvailable: freezed == unitsAvailable ? _self.unitsAvailable : unitsAvailable // ignore: cast_nullable_to_non_nullable
as int?,rateMinor: freezed == rateMinor ? _self.rateMinor : rateMinor // ignore: cast_nullable_to_non_nullable
as int?,
  ));
}

}


/// Adds pattern-matching-related methods to [CalendarDayDto].
extension CalendarDayDtoPatterns on CalendarDayDto {
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

@optionalTypeArgs TResult maybeMap<TResult extends Object?>(TResult Function( _CalendarDayDto value)?  $default,{required TResult orElse(),}){
final _that = this;
switch (_that) {
case _CalendarDayDto() when $default != null:
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

@optionalTypeArgs TResult map<TResult extends Object?>(TResult Function( _CalendarDayDto value)  $default,){
final _that = this;
switch (_that) {
case _CalendarDayDto():
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

@optionalTypeArgs TResult? mapOrNull<TResult extends Object?>(TResult? Function( _CalendarDayDto value)?  $default,){
final _that = this;
switch (_that) {
case _CalendarDayDto() when $default != null:
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

@optionalTypeArgs TResult maybeWhen<TResult extends Object?>(TResult Function( String date, @JsonKey(name: 'is_blocked')  bool isBlocked, @JsonKey(name: 'units_available')  int? unitsAvailable, @JsonKey(name: 'rate_minor')  int? rateMinor)?  $default,{required TResult orElse(),}) {final _that = this;
switch (_that) {
case _CalendarDayDto() when $default != null:
return $default(_that.date,_that.isBlocked,_that.unitsAvailable,_that.rateMinor);case _:
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

@optionalTypeArgs TResult when<TResult extends Object?>(TResult Function( String date, @JsonKey(name: 'is_blocked')  bool isBlocked, @JsonKey(name: 'units_available')  int? unitsAvailable, @JsonKey(name: 'rate_minor')  int? rateMinor)  $default,) {final _that = this;
switch (_that) {
case _CalendarDayDto():
return $default(_that.date,_that.isBlocked,_that.unitsAvailable,_that.rateMinor);case _:
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

@optionalTypeArgs TResult? whenOrNull<TResult extends Object?>(TResult? Function( String date, @JsonKey(name: 'is_blocked')  bool isBlocked, @JsonKey(name: 'units_available')  int? unitsAvailable, @JsonKey(name: 'rate_minor')  int? rateMinor)?  $default,) {final _that = this;
switch (_that) {
case _CalendarDayDto() when $default != null:
return $default(_that.date,_that.isBlocked,_that.unitsAvailable,_that.rateMinor);case _:
  return null;

}
}

}

/// @nodoc
@JsonSerializable()

class _CalendarDayDto implements CalendarDayDto {
  const _CalendarDayDto({required this.date, @JsonKey(name: 'is_blocked') this.isBlocked = false, @JsonKey(name: 'units_available') this.unitsAvailable, @JsonKey(name: 'rate_minor') this.rateMinor});
  factory _CalendarDayDto.fromJson(Map<String, dynamic> json) => _$CalendarDayDtoFromJson(json);

@override final  String date;
@override@JsonKey(name: 'is_blocked') final  bool isBlocked;
@override@JsonKey(name: 'units_available') final  int? unitsAvailable;
@override@JsonKey(name: 'rate_minor') final  int? rateMinor;

/// Create a copy of CalendarDayDto
/// with the given fields replaced by the non-null parameter values.
@override @JsonKey(includeFromJson: false, includeToJson: false)
@pragma('vm:prefer-inline')
_$CalendarDayDtoCopyWith<_CalendarDayDto> get copyWith => __$CalendarDayDtoCopyWithImpl<_CalendarDayDto>(this, _$identity);

@override
Map<String, dynamic> toJson() {
  return _$CalendarDayDtoToJson(this, );
}

@override
bool operator ==(Object other) {
  return identical(this, other) || (other.runtimeType == runtimeType&&other is _CalendarDayDto&&(identical(other.date, date) || other.date == date)&&(identical(other.isBlocked, isBlocked) || other.isBlocked == isBlocked)&&(identical(other.unitsAvailable, unitsAvailable) || other.unitsAvailable == unitsAvailable)&&(identical(other.rateMinor, rateMinor) || other.rateMinor == rateMinor));
}

@JsonKey(includeFromJson: false, includeToJson: false)
@override
int get hashCode => Object.hash(runtimeType,date,isBlocked,unitsAvailable,rateMinor);

@override
String toString() {
  return 'CalendarDayDto(date: $date, isBlocked: $isBlocked, unitsAvailable: $unitsAvailable, rateMinor: $rateMinor)';
}


}

/// @nodoc
abstract mixin class _$CalendarDayDtoCopyWith<$Res> implements $CalendarDayDtoCopyWith<$Res> {
  factory _$CalendarDayDtoCopyWith(_CalendarDayDto value, $Res Function(_CalendarDayDto) _then) = __$CalendarDayDtoCopyWithImpl;
@override @useResult
$Res call({
 String date,@JsonKey(name: 'is_blocked') bool isBlocked,@JsonKey(name: 'units_available') int? unitsAvailable,@JsonKey(name: 'rate_minor') int? rateMinor
});




}
/// @nodoc
class __$CalendarDayDtoCopyWithImpl<$Res>
    implements _$CalendarDayDtoCopyWith<$Res> {
  __$CalendarDayDtoCopyWithImpl(this._self, this._then);

  final _CalendarDayDto _self;
  final $Res Function(_CalendarDayDto) _then;

/// Create a copy of CalendarDayDto
/// with the given fields replaced by the non-null parameter values.
@override @pragma('vm:prefer-inline') $Res call({Object? date = null,Object? isBlocked = null,Object? unitsAvailable = freezed,Object? rateMinor = freezed,}) {
  return _then(_CalendarDayDto(
date: null == date ? _self.date : date // ignore: cast_nullable_to_non_nullable
as String,isBlocked: null == isBlocked ? _self.isBlocked : isBlocked // ignore: cast_nullable_to_non_nullable
as bool,unitsAvailable: freezed == unitsAvailable ? _self.unitsAvailable : unitsAvailable // ignore: cast_nullable_to_non_nullable
as int?,rateMinor: freezed == rateMinor ? _self.rateMinor : rateMinor // ignore: cast_nullable_to_non_nullable
as int?,
  ));
}


}


/// @nodoc
mixin _$CalendarDto {

@JsonKey(name: 'room_type_id') String get roomTypeId; String get currency; List<CalendarDayDto> get days;
/// Create a copy of CalendarDto
/// with the given fields replaced by the non-null parameter values.
@JsonKey(includeFromJson: false, includeToJson: false)
@pragma('vm:prefer-inline')
$CalendarDtoCopyWith<CalendarDto> get copyWith => _$CalendarDtoCopyWithImpl<CalendarDto>(this as CalendarDto, _$identity);

  /// Serializes this CalendarDto to a JSON map.
  Map<String, dynamic> toJson();


@override
bool operator ==(Object other) {
  return identical(this, other) || (other.runtimeType == runtimeType&&other is CalendarDto&&(identical(other.roomTypeId, roomTypeId) || other.roomTypeId == roomTypeId)&&(identical(other.currency, currency) || other.currency == currency)&&const DeepCollectionEquality().equals(other.days, days));
}

@JsonKey(includeFromJson: false, includeToJson: false)
@override
int get hashCode => Object.hash(runtimeType,roomTypeId,currency,const DeepCollectionEquality().hash(days));

@override
String toString() {
  return 'CalendarDto(roomTypeId: $roomTypeId, currency: $currency, days: $days)';
}


}

/// @nodoc
abstract mixin class $CalendarDtoCopyWith<$Res>  {
  factory $CalendarDtoCopyWith(CalendarDto value, $Res Function(CalendarDto) _then) = _$CalendarDtoCopyWithImpl;
@useResult
$Res call({
@JsonKey(name: 'room_type_id') String roomTypeId, String currency, List<CalendarDayDto> days
});




}
/// @nodoc
class _$CalendarDtoCopyWithImpl<$Res>
    implements $CalendarDtoCopyWith<$Res> {
  _$CalendarDtoCopyWithImpl(this._self, this._then);

  final CalendarDto _self;
  final $Res Function(CalendarDto) _then;

/// Create a copy of CalendarDto
/// with the given fields replaced by the non-null parameter values.
@pragma('vm:prefer-inline') @override $Res call({Object? roomTypeId = null,Object? currency = null,Object? days = null,}) {
  return _then(_self.copyWith(
roomTypeId: null == roomTypeId ? _self.roomTypeId : roomTypeId // ignore: cast_nullable_to_non_nullable
as String,currency: null == currency ? _self.currency : currency // ignore: cast_nullable_to_non_nullable
as String,days: null == days ? _self.days : days // ignore: cast_nullable_to_non_nullable
as List<CalendarDayDto>,
  ));
}

}


/// Adds pattern-matching-related methods to [CalendarDto].
extension CalendarDtoPatterns on CalendarDto {
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

@optionalTypeArgs TResult maybeMap<TResult extends Object?>(TResult Function( _CalendarDto value)?  $default,{required TResult orElse(),}){
final _that = this;
switch (_that) {
case _CalendarDto() when $default != null:
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

@optionalTypeArgs TResult map<TResult extends Object?>(TResult Function( _CalendarDto value)  $default,){
final _that = this;
switch (_that) {
case _CalendarDto():
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

@optionalTypeArgs TResult? mapOrNull<TResult extends Object?>(TResult? Function( _CalendarDto value)?  $default,){
final _that = this;
switch (_that) {
case _CalendarDto() when $default != null:
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

@optionalTypeArgs TResult maybeWhen<TResult extends Object?>(TResult Function(@JsonKey(name: 'room_type_id')  String roomTypeId,  String currency,  List<CalendarDayDto> days)?  $default,{required TResult orElse(),}) {final _that = this;
switch (_that) {
case _CalendarDto() when $default != null:
return $default(_that.roomTypeId,_that.currency,_that.days);case _:
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

@optionalTypeArgs TResult when<TResult extends Object?>(TResult Function(@JsonKey(name: 'room_type_id')  String roomTypeId,  String currency,  List<CalendarDayDto> days)  $default,) {final _that = this;
switch (_that) {
case _CalendarDto():
return $default(_that.roomTypeId,_that.currency,_that.days);case _:
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

@optionalTypeArgs TResult? whenOrNull<TResult extends Object?>(TResult? Function(@JsonKey(name: 'room_type_id')  String roomTypeId,  String currency,  List<CalendarDayDto> days)?  $default,) {final _that = this;
switch (_that) {
case _CalendarDto() when $default != null:
return $default(_that.roomTypeId,_that.currency,_that.days);case _:
  return null;

}
}

}

/// @nodoc
@JsonSerializable()

class _CalendarDto implements CalendarDto {
  const _CalendarDto({@JsonKey(name: 'room_type_id') this.roomTypeId = '', this.currency = 'INR', final  List<CalendarDayDto> days = const <CalendarDayDto>[]}): _days = days;
  factory _CalendarDto.fromJson(Map<String, dynamic> json) => _$CalendarDtoFromJson(json);

@override@JsonKey(name: 'room_type_id') final  String roomTypeId;
@override@JsonKey() final  String currency;
 final  List<CalendarDayDto> _days;
@override@JsonKey() List<CalendarDayDto> get days {
  if (_days is EqualUnmodifiableListView) return _days;
  // ignore: implicit_dynamic_type
  return EqualUnmodifiableListView(_days);
}


/// Create a copy of CalendarDto
/// with the given fields replaced by the non-null parameter values.
@override @JsonKey(includeFromJson: false, includeToJson: false)
@pragma('vm:prefer-inline')
_$CalendarDtoCopyWith<_CalendarDto> get copyWith => __$CalendarDtoCopyWithImpl<_CalendarDto>(this, _$identity);

@override
Map<String, dynamic> toJson() {
  return _$CalendarDtoToJson(this, );
}

@override
bool operator ==(Object other) {
  return identical(this, other) || (other.runtimeType == runtimeType&&other is _CalendarDto&&(identical(other.roomTypeId, roomTypeId) || other.roomTypeId == roomTypeId)&&(identical(other.currency, currency) || other.currency == currency)&&const DeepCollectionEquality().equals(other._days, _days));
}

@JsonKey(includeFromJson: false, includeToJson: false)
@override
int get hashCode => Object.hash(runtimeType,roomTypeId,currency,const DeepCollectionEquality().hash(_days));

@override
String toString() {
  return 'CalendarDto(roomTypeId: $roomTypeId, currency: $currency, days: $days)';
}


}

/// @nodoc
abstract mixin class _$CalendarDtoCopyWith<$Res> implements $CalendarDtoCopyWith<$Res> {
  factory _$CalendarDtoCopyWith(_CalendarDto value, $Res Function(_CalendarDto) _then) = __$CalendarDtoCopyWithImpl;
@override @useResult
$Res call({
@JsonKey(name: 'room_type_id') String roomTypeId, String currency, List<CalendarDayDto> days
});




}
/// @nodoc
class __$CalendarDtoCopyWithImpl<$Res>
    implements _$CalendarDtoCopyWith<$Res> {
  __$CalendarDtoCopyWithImpl(this._self, this._then);

  final _CalendarDto _self;
  final $Res Function(_CalendarDto) _then;

/// Create a copy of CalendarDto
/// with the given fields replaced by the non-null parameter values.
@override @pragma('vm:prefer-inline') $Res call({Object? roomTypeId = null,Object? currency = null,Object? days = null,}) {
  return _then(_CalendarDto(
roomTypeId: null == roomTypeId ? _self.roomTypeId : roomTypeId // ignore: cast_nullable_to_non_nullable
as String,currency: null == currency ? _self.currency : currency // ignore: cast_nullable_to_non_nullable
as String,days: null == days ? _self._days : days // ignore: cast_nullable_to_non_nullable
as List<CalendarDayDto>,
  ));
}


}

// dart format on
