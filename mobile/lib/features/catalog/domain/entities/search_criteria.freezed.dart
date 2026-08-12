// GENERATED CODE - DO NOT MODIFY BY HAND
// coverage:ignore-file
// ignore_for_file: type=lint
// ignore_for_file: unused_element, deprecated_member_use, deprecated_member_use_from_same_package, use_function_type_syntax_for_parameters, unnecessary_const, avoid_init_to_null, invalid_override_different_default_values_named, prefer_expression_function_bodies, annotate_overrides, invalid_annotation_target, unnecessary_question_mark

part of 'search_criteria.dart';

// **************************************************************************
// FreezedGenerator
// **************************************************************************

// dart format off
T _$identity<T>(T value) => value;
/// @nodoc
mixin _$SearchCriteria {

 String? get query; String? get cityId; IsoDate? get checkIn; IsoDate? get checkOut; int get adults; int get children; int get infants; int get rooms; List<String> get propertyTypes; List<String> get amenities; int? get minPriceMinor; int? get maxPriceMinor; double? get minRating; bool get instantBookingOnly; String? get cancellation; SearchSort get sort;
/// Create a copy of SearchCriteria
/// with the given fields replaced by the non-null parameter values.
@JsonKey(includeFromJson: false, includeToJson: false)
@pragma('vm:prefer-inline')
$SearchCriteriaCopyWith<SearchCriteria> get copyWith => _$SearchCriteriaCopyWithImpl<SearchCriteria>(this as SearchCriteria, _$identity);



@override
bool operator ==(Object other) {
  return identical(this, other) || (other.runtimeType == runtimeType&&other is SearchCriteria&&(identical(other.query, query) || other.query == query)&&(identical(other.cityId, cityId) || other.cityId == cityId)&&(identical(other.checkIn, checkIn) || other.checkIn == checkIn)&&(identical(other.checkOut, checkOut) || other.checkOut == checkOut)&&(identical(other.adults, adults) || other.adults == adults)&&(identical(other.children, children) || other.children == children)&&(identical(other.infants, infants) || other.infants == infants)&&(identical(other.rooms, rooms) || other.rooms == rooms)&&const DeepCollectionEquality().equals(other.propertyTypes, propertyTypes)&&const DeepCollectionEquality().equals(other.amenities, amenities)&&(identical(other.minPriceMinor, minPriceMinor) || other.minPriceMinor == minPriceMinor)&&(identical(other.maxPriceMinor, maxPriceMinor) || other.maxPriceMinor == maxPriceMinor)&&(identical(other.minRating, minRating) || other.minRating == minRating)&&(identical(other.instantBookingOnly, instantBookingOnly) || other.instantBookingOnly == instantBookingOnly)&&(identical(other.cancellation, cancellation) || other.cancellation == cancellation)&&(identical(other.sort, sort) || other.sort == sort));
}


@override
int get hashCode => Object.hash(runtimeType,query,cityId,checkIn,checkOut,adults,children,infants,rooms,const DeepCollectionEquality().hash(propertyTypes),const DeepCollectionEquality().hash(amenities),minPriceMinor,maxPriceMinor,minRating,instantBookingOnly,cancellation,sort);

@override
String toString() {
  return 'SearchCriteria(query: $query, cityId: $cityId, checkIn: $checkIn, checkOut: $checkOut, adults: $adults, children: $children, infants: $infants, rooms: $rooms, propertyTypes: $propertyTypes, amenities: $amenities, minPriceMinor: $minPriceMinor, maxPriceMinor: $maxPriceMinor, minRating: $minRating, instantBookingOnly: $instantBookingOnly, cancellation: $cancellation, sort: $sort)';
}


}

/// @nodoc
abstract mixin class $SearchCriteriaCopyWith<$Res>  {
  factory $SearchCriteriaCopyWith(SearchCriteria value, $Res Function(SearchCriteria) _then) = _$SearchCriteriaCopyWithImpl;
@useResult
$Res call({
 String? query, String? cityId, IsoDate? checkIn, IsoDate? checkOut, int adults, int children, int infants, int rooms, List<String> propertyTypes, List<String> amenities, int? minPriceMinor, int? maxPriceMinor, double? minRating, bool instantBookingOnly, String? cancellation, SearchSort sort
});




}
/// @nodoc
class _$SearchCriteriaCopyWithImpl<$Res>
    implements $SearchCriteriaCopyWith<$Res> {
  _$SearchCriteriaCopyWithImpl(this._self, this._then);

  final SearchCriteria _self;
  final $Res Function(SearchCriteria) _then;

/// Create a copy of SearchCriteria
/// with the given fields replaced by the non-null parameter values.
@pragma('vm:prefer-inline') @override $Res call({Object? query = freezed,Object? cityId = freezed,Object? checkIn = freezed,Object? checkOut = freezed,Object? adults = null,Object? children = null,Object? infants = null,Object? rooms = null,Object? propertyTypes = null,Object? amenities = null,Object? minPriceMinor = freezed,Object? maxPriceMinor = freezed,Object? minRating = freezed,Object? instantBookingOnly = null,Object? cancellation = freezed,Object? sort = null,}) {
  return _then(_self.copyWith(
query: freezed == query ? _self.query : query // ignore: cast_nullable_to_non_nullable
as String?,cityId: freezed == cityId ? _self.cityId : cityId // ignore: cast_nullable_to_non_nullable
as String?,checkIn: freezed == checkIn ? _self.checkIn : checkIn // ignore: cast_nullable_to_non_nullable
as IsoDate?,checkOut: freezed == checkOut ? _self.checkOut : checkOut // ignore: cast_nullable_to_non_nullable
as IsoDate?,adults: null == adults ? _self.adults : adults // ignore: cast_nullable_to_non_nullable
as int,children: null == children ? _self.children : children // ignore: cast_nullable_to_non_nullable
as int,infants: null == infants ? _self.infants : infants // ignore: cast_nullable_to_non_nullable
as int,rooms: null == rooms ? _self.rooms : rooms // ignore: cast_nullable_to_non_nullable
as int,propertyTypes: null == propertyTypes ? _self.propertyTypes : propertyTypes // ignore: cast_nullable_to_non_nullable
as List<String>,amenities: null == amenities ? _self.amenities : amenities // ignore: cast_nullable_to_non_nullable
as List<String>,minPriceMinor: freezed == minPriceMinor ? _self.minPriceMinor : minPriceMinor // ignore: cast_nullable_to_non_nullable
as int?,maxPriceMinor: freezed == maxPriceMinor ? _self.maxPriceMinor : maxPriceMinor // ignore: cast_nullable_to_non_nullable
as int?,minRating: freezed == minRating ? _self.minRating : minRating // ignore: cast_nullable_to_non_nullable
as double?,instantBookingOnly: null == instantBookingOnly ? _self.instantBookingOnly : instantBookingOnly // ignore: cast_nullable_to_non_nullable
as bool,cancellation: freezed == cancellation ? _self.cancellation : cancellation // ignore: cast_nullable_to_non_nullable
as String?,sort: null == sort ? _self.sort : sort // ignore: cast_nullable_to_non_nullable
as SearchSort,
  ));
}

}


/// Adds pattern-matching-related methods to [SearchCriteria].
extension SearchCriteriaPatterns on SearchCriteria {
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

@optionalTypeArgs TResult maybeMap<TResult extends Object?>(TResult Function( _SearchCriteria value)?  $default,{required TResult orElse(),}){
final _that = this;
switch (_that) {
case _SearchCriteria() when $default != null:
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

@optionalTypeArgs TResult map<TResult extends Object?>(TResult Function( _SearchCriteria value)  $default,){
final _that = this;
switch (_that) {
case _SearchCriteria():
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

@optionalTypeArgs TResult? mapOrNull<TResult extends Object?>(TResult? Function( _SearchCriteria value)?  $default,){
final _that = this;
switch (_that) {
case _SearchCriteria() when $default != null:
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

@optionalTypeArgs TResult maybeWhen<TResult extends Object?>(TResult Function( String? query,  String? cityId,  IsoDate? checkIn,  IsoDate? checkOut,  int adults,  int children,  int infants,  int rooms,  List<String> propertyTypes,  List<String> amenities,  int? minPriceMinor,  int? maxPriceMinor,  double? minRating,  bool instantBookingOnly,  String? cancellation,  SearchSort sort)?  $default,{required TResult orElse(),}) {final _that = this;
switch (_that) {
case _SearchCriteria() when $default != null:
return $default(_that.query,_that.cityId,_that.checkIn,_that.checkOut,_that.adults,_that.children,_that.infants,_that.rooms,_that.propertyTypes,_that.amenities,_that.minPriceMinor,_that.maxPriceMinor,_that.minRating,_that.instantBookingOnly,_that.cancellation,_that.sort);case _:
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

@optionalTypeArgs TResult when<TResult extends Object?>(TResult Function( String? query,  String? cityId,  IsoDate? checkIn,  IsoDate? checkOut,  int adults,  int children,  int infants,  int rooms,  List<String> propertyTypes,  List<String> amenities,  int? minPriceMinor,  int? maxPriceMinor,  double? minRating,  bool instantBookingOnly,  String? cancellation,  SearchSort sort)  $default,) {final _that = this;
switch (_that) {
case _SearchCriteria():
return $default(_that.query,_that.cityId,_that.checkIn,_that.checkOut,_that.adults,_that.children,_that.infants,_that.rooms,_that.propertyTypes,_that.amenities,_that.minPriceMinor,_that.maxPriceMinor,_that.minRating,_that.instantBookingOnly,_that.cancellation,_that.sort);case _:
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

@optionalTypeArgs TResult? whenOrNull<TResult extends Object?>(TResult? Function( String? query,  String? cityId,  IsoDate? checkIn,  IsoDate? checkOut,  int adults,  int children,  int infants,  int rooms,  List<String> propertyTypes,  List<String> amenities,  int? minPriceMinor,  int? maxPriceMinor,  double? minRating,  bool instantBookingOnly,  String? cancellation,  SearchSort sort)?  $default,) {final _that = this;
switch (_that) {
case _SearchCriteria() when $default != null:
return $default(_that.query,_that.cityId,_that.checkIn,_that.checkOut,_that.adults,_that.children,_that.infants,_that.rooms,_that.propertyTypes,_that.amenities,_that.minPriceMinor,_that.maxPriceMinor,_that.minRating,_that.instantBookingOnly,_that.cancellation,_that.sort);case _:
  return null;

}
}

}

/// @nodoc


class _SearchCriteria extends SearchCriteria {
  const _SearchCriteria({this.query, this.cityId, this.checkIn, this.checkOut, this.adults = 2, this.children = 0, this.infants = 0, this.rooms = 1, final  List<String> propertyTypes = const <String>[], final  List<String> amenities = const <String>[], this.minPriceMinor, this.maxPriceMinor, this.minRating, this.instantBookingOnly = false, this.cancellation, this.sort = SearchSort.relevance}): _propertyTypes = propertyTypes,_amenities = amenities,super._();
  

@override final  String? query;
@override final  String? cityId;
@override final  IsoDate? checkIn;
@override final  IsoDate? checkOut;
@override@JsonKey() final  int adults;
@override@JsonKey() final  int children;
@override@JsonKey() final  int infants;
@override@JsonKey() final  int rooms;
 final  List<String> _propertyTypes;
@override@JsonKey() List<String> get propertyTypes {
  if (_propertyTypes is EqualUnmodifiableListView) return _propertyTypes;
  // ignore: implicit_dynamic_type
  return EqualUnmodifiableListView(_propertyTypes);
}

 final  List<String> _amenities;
@override@JsonKey() List<String> get amenities {
  if (_amenities is EqualUnmodifiableListView) return _amenities;
  // ignore: implicit_dynamic_type
  return EqualUnmodifiableListView(_amenities);
}

@override final  int? minPriceMinor;
@override final  int? maxPriceMinor;
@override final  double? minRating;
@override@JsonKey() final  bool instantBookingOnly;
@override final  String? cancellation;
@override@JsonKey() final  SearchSort sort;

/// Create a copy of SearchCriteria
/// with the given fields replaced by the non-null parameter values.
@override @JsonKey(includeFromJson: false, includeToJson: false)
@pragma('vm:prefer-inline')
_$SearchCriteriaCopyWith<_SearchCriteria> get copyWith => __$SearchCriteriaCopyWithImpl<_SearchCriteria>(this, _$identity);



@override
bool operator ==(Object other) {
  return identical(this, other) || (other.runtimeType == runtimeType&&other is _SearchCriteria&&(identical(other.query, query) || other.query == query)&&(identical(other.cityId, cityId) || other.cityId == cityId)&&(identical(other.checkIn, checkIn) || other.checkIn == checkIn)&&(identical(other.checkOut, checkOut) || other.checkOut == checkOut)&&(identical(other.adults, adults) || other.adults == adults)&&(identical(other.children, children) || other.children == children)&&(identical(other.infants, infants) || other.infants == infants)&&(identical(other.rooms, rooms) || other.rooms == rooms)&&const DeepCollectionEquality().equals(other._propertyTypes, _propertyTypes)&&const DeepCollectionEquality().equals(other._amenities, _amenities)&&(identical(other.minPriceMinor, minPriceMinor) || other.minPriceMinor == minPriceMinor)&&(identical(other.maxPriceMinor, maxPriceMinor) || other.maxPriceMinor == maxPriceMinor)&&(identical(other.minRating, minRating) || other.minRating == minRating)&&(identical(other.instantBookingOnly, instantBookingOnly) || other.instantBookingOnly == instantBookingOnly)&&(identical(other.cancellation, cancellation) || other.cancellation == cancellation)&&(identical(other.sort, sort) || other.sort == sort));
}


@override
int get hashCode => Object.hash(runtimeType,query,cityId,checkIn,checkOut,adults,children,infants,rooms,const DeepCollectionEquality().hash(_propertyTypes),const DeepCollectionEquality().hash(_amenities),minPriceMinor,maxPriceMinor,minRating,instantBookingOnly,cancellation,sort);

@override
String toString() {
  return 'SearchCriteria(query: $query, cityId: $cityId, checkIn: $checkIn, checkOut: $checkOut, adults: $adults, children: $children, infants: $infants, rooms: $rooms, propertyTypes: $propertyTypes, amenities: $amenities, minPriceMinor: $minPriceMinor, maxPriceMinor: $maxPriceMinor, minRating: $minRating, instantBookingOnly: $instantBookingOnly, cancellation: $cancellation, sort: $sort)';
}


}

/// @nodoc
abstract mixin class _$SearchCriteriaCopyWith<$Res> implements $SearchCriteriaCopyWith<$Res> {
  factory _$SearchCriteriaCopyWith(_SearchCriteria value, $Res Function(_SearchCriteria) _then) = __$SearchCriteriaCopyWithImpl;
@override @useResult
$Res call({
 String? query, String? cityId, IsoDate? checkIn, IsoDate? checkOut, int adults, int children, int infants, int rooms, List<String> propertyTypes, List<String> amenities, int? minPriceMinor, int? maxPriceMinor, double? minRating, bool instantBookingOnly, String? cancellation, SearchSort sort
});




}
/// @nodoc
class __$SearchCriteriaCopyWithImpl<$Res>
    implements _$SearchCriteriaCopyWith<$Res> {
  __$SearchCriteriaCopyWithImpl(this._self, this._then);

  final _SearchCriteria _self;
  final $Res Function(_SearchCriteria) _then;

/// Create a copy of SearchCriteria
/// with the given fields replaced by the non-null parameter values.
@override @pragma('vm:prefer-inline') $Res call({Object? query = freezed,Object? cityId = freezed,Object? checkIn = freezed,Object? checkOut = freezed,Object? adults = null,Object? children = null,Object? infants = null,Object? rooms = null,Object? propertyTypes = null,Object? amenities = null,Object? minPriceMinor = freezed,Object? maxPriceMinor = freezed,Object? minRating = freezed,Object? instantBookingOnly = null,Object? cancellation = freezed,Object? sort = null,}) {
  return _then(_SearchCriteria(
query: freezed == query ? _self.query : query // ignore: cast_nullable_to_non_nullable
as String?,cityId: freezed == cityId ? _self.cityId : cityId // ignore: cast_nullable_to_non_nullable
as String?,checkIn: freezed == checkIn ? _self.checkIn : checkIn // ignore: cast_nullable_to_non_nullable
as IsoDate?,checkOut: freezed == checkOut ? _self.checkOut : checkOut // ignore: cast_nullable_to_non_nullable
as IsoDate?,adults: null == adults ? _self.adults : adults // ignore: cast_nullable_to_non_nullable
as int,children: null == children ? _self.children : children // ignore: cast_nullable_to_non_nullable
as int,infants: null == infants ? _self.infants : infants // ignore: cast_nullable_to_non_nullable
as int,rooms: null == rooms ? _self.rooms : rooms // ignore: cast_nullable_to_non_nullable
as int,propertyTypes: null == propertyTypes ? _self._propertyTypes : propertyTypes // ignore: cast_nullable_to_non_nullable
as List<String>,amenities: null == amenities ? _self._amenities : amenities // ignore: cast_nullable_to_non_nullable
as List<String>,minPriceMinor: freezed == minPriceMinor ? _self.minPriceMinor : minPriceMinor // ignore: cast_nullable_to_non_nullable
as int?,maxPriceMinor: freezed == maxPriceMinor ? _self.maxPriceMinor : maxPriceMinor // ignore: cast_nullable_to_non_nullable
as int?,minRating: freezed == minRating ? _self.minRating : minRating // ignore: cast_nullable_to_non_nullable
as double?,instantBookingOnly: null == instantBookingOnly ? _self.instantBookingOnly : instantBookingOnly // ignore: cast_nullable_to_non_nullable
as bool,cancellation: freezed == cancellation ? _self.cancellation : cancellation // ignore: cast_nullable_to_non_nullable
as String?,sort: null == sort ? _self.sort : sort // ignore: cast_nullable_to_non_nullable
as SearchSort,
  ));
}


}

// dart format on
